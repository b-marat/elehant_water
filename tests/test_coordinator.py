"""Tests for Elehant runtime coordinator."""

from __future__ import annotations

from custom_components.elehant_water.const import (
    CONF_AVAILABILITY_ENABLED,
    CONF_AVAILABILITY_TIMEOUT_MINUTES,
    CHANNEL_TEMPERATURE,
    CHANNEL_VOLUME,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_METERS,
    CONF_METER_ID,
    MAX_UNKNOWN_PACKETS,
)
from custom_components.elehant_water.coordinator import ElehantWaterCoordinator
from custom_components.elehant_water.models import (
    ElehantChannel,
    ElehantPacketKind,
    ElehantReading,
)


class FakeHass:
    """Small hass fake for coordinator scheduling tests."""


def test_reading_matches_configured_address_suffix_meter_id() -> None:
    """Readings can match extended-fork IDs derived from BLE address suffix."""
    coordinator = ElehantWaterCoordinator(
        None,
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: "92728",
                    CONF_CHANNELS: [
                        {CONF_CHANNEL: CHANNEL_VOLUME},
                        {CONF_CHANNEL: CHANNEL_TEMPERATURE},
                    ],
                }
            ]
        },
    )
    reading = ElehantReading(
        meter_id="27192",
        alternate_meter_ids=("92728",),
        channel=ElehantChannel.VOLUME,
        raw_count=3791455,
        packet_kind=ElehantPacketKind.SINGLE_TARIFF,
        address="b0:01:02:01:6a:38",
        temperature_celsius=16.06,
    )

    assert coordinator.async_handle_reading(reading)
    assert coordinator.get_state("92728", CHANNEL_VOLUME).raw_count == 3791455
    assert coordinator.get_state("92728", CHANNEL_VOLUME).matched_by == "alias"
    assert (
        coordinator.get_state("92728", CHANNEL_TEMPERATURE).temperature_celsius == 16.06
    )


def test_parser_stats_name_channel_match_counters_explicitly() -> None:
    """Parser diagnostics make channel-level match counters explicit."""
    coordinator = ElehantWaterCoordinator(
        None,
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: "92728",
                    CONF_CHANNELS: [
                        {CONF_CHANNEL: CHANNEL_VOLUME},
                        {CONF_CHANNEL: CHANNEL_TEMPERATURE},
                    ],
                }
            ]
        },
    )
    reading = ElehantReading(
        meter_id="92728",
        channel=ElehantChannel.VOLUME,
        raw_count=3791455,
        packet_kind=ElehantPacketKind.SINGLE_TARIFF,
        address="b0:01:02:01:6a:38",
        manufacturer_meter_id="92728",
        temperature_celsius=16.06,
    )

    assert coordinator.async_handle_reading(reading)
    assert coordinator.parser_stats["channel_matches_by_manufacturer_meter_id"] == 2
    assert coordinator.parser_stats["channel_matches_by_address_id"] == 0


def test_channel_availability_uses_runtime_last_seen_timeout() -> None:
    """Availability follows HA entity availability semantics."""
    coordinator = ElehantWaterCoordinator(
        None,
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: "92728",
                    CONF_AVAILABILITY_ENABLED: True,
                    CONF_AVAILABILITY_TIMEOUT_MINUTES: 60,
                    CONF_CHANNELS: [{CONF_CHANNEL: CHANNEL_VOLUME}],
                }
            ]
        },
    )
    reading = ElehantReading(
        meter_id="92728",
        channel=ElehantChannel.VOLUME,
        raw_count=3791455,
        packet_kind=ElehantPacketKind.SINGLE_TARIFF,
        address="b0:01:02:01:6a:38",
        manufacturer_meter_id="92728",
    )

    assert coordinator.is_available("92728", CHANNEL_VOLUME)
    assert coordinator.async_handle_reading(reading)
    last_seen = coordinator.get_state("92728", CHANNEL_VOLUME).last_seen
    assert coordinator.is_available("92728", CHANNEL_VOLUME, now=last_seen + 3599)
    assert not coordinator.is_available("92728", CHANNEL_VOLUME, now=last_seen + 3601)


def test_availability_timeout_schedules_entity_refresh(monkeypatch) -> None:
    """A seen channel schedules a listener refresh when it becomes unavailable."""
    scheduled: list[dict[str, object]] = []

    def fake_async_call_later(hass, delay, action):
        scheduled.append({"hass": hass, "delay": delay, "action": action})
        return lambda: scheduled.append({"cancelled": True})

    monkeypatch.setattr(
        "custom_components.elehant_water.coordinator.async_call_later",
        fake_async_call_later,
    )
    hass = FakeHass()
    coordinator = ElehantWaterCoordinator(
        hass,
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: "92728",
                    CONF_AVAILABILITY_ENABLED: True,
                    CONF_AVAILABILITY_TIMEOUT_MINUTES: 1,
                    CONF_CHANNELS: [{CONF_CHANNEL: CHANNEL_VOLUME}],
                }
            ]
        },
    )
    listener_calls = 0

    def listener() -> None:
        nonlocal listener_calls
        listener_calls += 1

    coordinator.async_add_listener(listener)
    reading = ElehantReading(
        meter_id="92728",
        channel=ElehantChannel.VOLUME,
        raw_count=3791455,
        packet_kind=ElehantPacketKind.SINGLE_TARIFF,
        address="b0:01:02:01:6a:38",
        manufacturer_meter_id="92728",
    )

    assert coordinator.async_handle_reading(reading)
    assert len(scheduled) == 1
    assert scheduled[0]["hass"] is hass
    assert 1 <= scheduled[0]["delay"] <= 61
    assert listener_calls == 1

    scheduled[0]["action"](None)

    assert listener_calls == 2


def test_availability_timeout_reschedules_and_shutdown_cancels(monkeypatch) -> None:
    """A fresh packet replaces the old availability refresh and shutdown clears it."""
    cancelled = 0

    def fake_async_call_later(hass, delay, action):
        def cancel() -> None:
            nonlocal cancelled
            cancelled += 1

        return cancel

    monkeypatch.setattr(
        "custom_components.elehant_water.coordinator.async_call_later",
        fake_async_call_later,
    )
    coordinator = ElehantWaterCoordinator(
        FakeHass(),
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: "92728",
                    CONF_AVAILABILITY_ENABLED: True,
                    CONF_AVAILABILITY_TIMEOUT_MINUTES: 1,
                    CONF_CHANNELS: [{CONF_CHANNEL: CHANNEL_VOLUME}],
                }
            ]
        },
    )
    reading = ElehantReading(
        meter_id="92728",
        channel=ElehantChannel.VOLUME,
        raw_count=3791455,
        packet_kind=ElehantPacketKind.SINGLE_TARIFF,
        address="b0:01:02:01:6a:38",
        manufacturer_meter_id="92728",
    )

    assert coordinator.async_handle_reading(reading)
    assert coordinator.async_handle_reading(reading)
    assert cancelled == 1

    coordinator.async_shutdown()

    assert cancelled == 2


def test_identity_mismatch_is_tracked_as_unknown() -> None:
    """Conflicting address/manufacturer identities are not matched automatically."""
    coordinator = ElehantWaterCoordinator(
        None,
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: "92728",
                    CONF_CHANNELS: [{CONF_CHANNEL: CHANNEL_VOLUME}],
                }
            ]
        },
    )
    reading = ElehantReading(
        meter_id="92728",
        channel=ElehantChannel.VOLUME,
        raw_count=3791455,
        packet_kind=ElehantPacketKind.SINGLE_TARIFF,
        address="b0:01:02:01:6a:38",
        manufacturer_meter_id="92728",
        address_meter_id="123",
        identity_mismatch=True,
    )

    assert not coordinator.async_handle_reading(reading)
    assert "92728" in coordinator.unknown_packets
    assert coordinator.parser_stats["identity_mismatches"] == 1


def test_recent_unknown_packets_filters_stale_candidates() -> None:
    """Discovery candidates are limited to recently seen unknown packets."""
    coordinator = ElehantWaterCoordinator(None, {CONF_METERS: []})
    reading = ElehantReading(
        meter_id="92728",
        channel=ElehantChannel.VOLUME,
        raw_count=3791455,
        packet_kind=ElehantPacketKind.SINGLE_TARIFF,
        address="b0:01:02:01:6a:38",
        manufacturer_meter_id="92728",
    )

    assert not coordinator.async_handle_reading(reading)
    candidate = coordinator.unknown_packets["92728"]

    assert "92728" in coordinator.recent_unknown_packets(
        now=candidate.last_seen + 60,
        ttl_seconds=120,
    )
    assert "92728" not in coordinator.recent_unknown_packets(
        now=candidate.last_seen + 121,
        ttl_seconds=120,
    )


def test_unknown_packets_storage_is_bounded_by_size() -> None:
    """Unknown packet tracking keeps a hard cap in noisy environments."""
    coordinator = ElehantWaterCoordinator(None, {CONF_METERS: []})

    for meter_id in range(MAX_UNKNOWN_PACKETS + 10):
        reading = ElehantReading(
            meter_id=str(meter_id),
            channel=ElehantChannel.VOLUME,
            raw_count=1000,
            packet_kind=ElehantPacketKind.SINGLE_TARIFF,
            address=f"b0:01:02:00:00:{meter_id % 255:02x}",
            manufacturer_meter_id=str(meter_id),
        )
        assert not coordinator.async_handle_reading(reading)

    assert len(coordinator.unknown_packets) == MAX_UNKNOWN_PACKETS
    assert "0" not in coordinator.unknown_packets


def test_unknown_packets_storage_prunes_expired_candidates() -> None:
    """Expired unknown packets are removed from storage."""
    coordinator = ElehantWaterCoordinator(None, {CONF_METERS: []})
    reading = ElehantReading(
        meter_id="92728",
        channel=ElehantChannel.VOLUME,
        raw_count=3791455,
        packet_kind=ElehantPacketKind.SINGLE_TARIFF,
        address="b0:01:02:01:6a:38",
        manufacturer_meter_id="92728",
    )

    assert not coordinator.async_handle_reading(reading)
    candidate = coordinator.unknown_packets["92728"]
    coordinator._prune_unknown_packets(candidate.last_seen + 1801)

    assert "92728" not in coordinator.unknown_packets
