"""Tests for Elehant runtime coordinator."""

from __future__ import annotations

from custom_components.elehant_water.const import (
    CHANNEL_TEMPERATURE,
    CHANNEL_VOLUME,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_METERS,
    CONF_METER_ID,
)
from custom_components.elehant_water.coordinator import ElehantWaterCoordinator
from custom_components.elehant_water.models import (
    ElehantChannel,
    ElehantPacketKind,
    ElehantReading,
)


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
    assert (
        coordinator.get_state("92728", CHANNEL_TEMPERATURE).temperature_celsius == 16.06
    )
