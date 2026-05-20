"""Runtime coordinator for Elehant Water readings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_AVAILABILITY_ENABLED,
    CONF_AVAILABILITY_TIMEOUT_MINUTES,
    CHANNEL_TEMPERATURE,
    CONF_CHANNEL,
    CONF_CHANNELS,
    DEFAULT_DISCOVERY_CANDIDATE_TTL_SECONDS,
    DEFAULT_NEVER_SEEN_REPAIR_GRACE_SECONDS,
    CONF_IDENTITY_EVIDENCE,
    CONF_ENABLED,
    CONF_METERS,
    CONF_METER_ID,
    MATCHED_BY_ADDRESS,
    MATCHED_BY_ALIAS,
    MATCHED_BY_CONFIGURED,
    MATCHED_BY_MANUFACTURER,
    MAX_UNKNOWN_PACKETS,
)
from .models import ElehantChannel, ElehantReading
from .parser import looks_like_elehant_address, parse_manufacturer_data
from .repairs import async_update_never_seen_repair_issues

_LOGGER = logging.getLogger(__name__)

ElehantChannelKey = tuple[str, str]


@dataclass
class ElehantChannelState:
    """Latest state for a configured Elehant channel."""

    raw_count: int | None = None
    temperature_celsius: float | None = None
    last_seen: float | None = None
    rssi: int | None = None
    packet_count: int = 0
    matched_by: str | None = None


@dataclass
class ElehantUnknownPacket:
    """Recently seen Elehant-like packet not matched to configured channels."""

    meter_id: str
    manufacturer_meter_id: str | None
    address_meter_id: str | None
    packet_kind: str
    rssi: int | None
    first_seen: float
    last_seen: float
    count: int = 1
    temperature_observed: bool = False


class ElehantWaterCoordinator:
    """Coordinate parsed BLE readings and Home Assistant entities."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.config = config
        self._started_at = time.time()
        self._listeners: list[Callable[[], None]] = []
        self._availability_refresh_unsub: dict[ElehantChannelKey, Callable[[], None]] = {}
        self._states: dict[ElehantChannelKey, ElehantChannelState] = {}
        self._configured_keys = self._build_configured_keys(config)
        self._meter_options = self._build_meter_options(config)
        self.unknown_packets: dict[str, ElehantUnknownPacket] = {}
        self.parser_stats: dict[str, int] = {
            "total_elehant_like_packets": 0,
            "parsed_packets": 0,
            "ignored_packets": 0,
            "unknown_meter_ids": 0,
            "channel_matches_by_manufacturer_meter_id": 0,
            "channel_matches_by_address_id": 0,
            "identity_mismatches": 0,
        }

    @staticmethod
    def _build_configured_keys(config: dict[str, Any]) -> set[ElehantChannelKey]:
        keys: set[ElehantChannelKey] = set()
        for meter in config.get(CONF_METERS, []):
            meter_id = str(meter[CONF_METER_ID])
            for channel in meter.get(CONF_CHANNELS, []):
                if channel.get(CONF_ENABLED, True):
                    keys.add((meter_id, str(channel[CONF_CHANNEL])))
        return keys

    @staticmethod
    def _build_meter_options(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
        options: dict[str, dict[str, Any]] = {}
        for meter in config.get(CONF_METERS, []):
            meter_id = str(meter[CONF_METER_ID])
            options[meter_id] = {
                CONF_AVAILABILITY_ENABLED: bool(
                    meter.get(CONF_AVAILABILITY_ENABLED, True)
                ),
                CONF_AVAILABILITY_TIMEOUT_MINUTES: int(
                    meter.get(CONF_AVAILABILITY_TIMEOUT_MINUTES, 60)
                ),
                CONF_IDENTITY_EVIDENCE: dict(meter.get(CONF_IDENTITY_EVIDENCE) or {}),
            }
        return options

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for state updates."""
        self._listeners.append(listener)

        @callback
        def _remove_listener() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove_listener

    @callback
    def _async_notify_listeners(self) -> None:
        """Notify registered listeners."""
        for listener in list(self._listeners):
            listener()

    @callback
    def async_handle_bluetooth_service_info(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth service info update."""
        if not looks_like_elehant_address(service_info.address):
            return

        self.parser_stats["total_elehant_like_packets"] += 1
        reading = parse_manufacturer_data(
            service_info.address,
            service_info.manufacturer_data,
            service_info.rssi,
        )
        if reading is None:
            self.parser_stats["ignored_packets"] += 1
            return

        self.parser_stats["parsed_packets"] += 1
        updated = self.async_handle_reading(reading)
        if updated:
            _LOGGER.debug("Updated Elehant reading: %s", reading)
        self.async_update_repair_issues()

    @callback
    def async_handle_reading(self, reading: ElehantReading) -> bool:
        """Store a parsed reading if it belongs to a configured channel."""
        now = time.time()
        self._prune_unknown_packets(now)
        updated = False
        if reading.identity_mismatch:
            self.parser_stats["identity_mismatches"] += 1
            self._track_unknown(reading, now)
            return False
        match = self._configured_meter_match(reading, reading.channel.value)

        if match is not None:
            meter_id, matched_by = match
            state = self._states.setdefault(
                (meter_id, reading.channel.value), ElehantChannelState()
            )
            state.raw_count = reading.raw_count
            state.last_seen = now
            state.rssi = reading.rssi
            state.packet_count += 1
            state.matched_by = matched_by
            self._async_schedule_availability_refresh(
                (meter_id, reading.channel.value), now
            )
            updated = True
        else:
            self._track_unknown(reading, now)
            self.parser_stats["unknown_meter_ids"] += 1
            _LOGGER.debug(
                "Ignoring Elehant reading for unconfigured meter/channel: %s/%s",
                reading.meter_id,
                reading.channel,
            )

        if reading.temperature_celsius is not None:
            temp_match = self._configured_meter_match(
                reading, ElehantChannel.TEMPERATURE.value
            )
            if temp_match is not None:
                temp_meter_id, temp_matched_by = temp_match
                state = self._states.setdefault(
                    (temp_meter_id, ElehantChannel.TEMPERATURE.value),
                    ElehantChannelState(),
                )
                state.temperature_celsius = reading.temperature_celsius
                state.last_seen = now
                state.rssi = reading.rssi
                state.packet_count += 1
                state.matched_by = temp_matched_by
                self._async_schedule_availability_refresh(
                    (temp_meter_id, ElehantChannel.TEMPERATURE.value), now
                )
                updated = True

        if updated:
            self._async_notify_listeners()
        return updated

    def _configured_meter_match(
        self,
        reading: ElehantReading,
        channel: str,
    ) -> tuple[str, str] | None:
        """Return the configured meter ID and match source for a parsed reading."""
        if (reading.meter_id, channel) in self._configured_keys:
            if reading.manufacturer_meter_id == reading.meter_id:
                self.parser_stats["channel_matches_by_manufacturer_meter_id"] += 1
                return reading.meter_id, MATCHED_BY_MANUFACTURER
            return reading.meter_id, MATCHED_BY_CONFIGURED
        if (
            reading.address_meter_id
            and (reading.address_meter_id, channel) in self._configured_keys
        ):
            self.parser_stats["channel_matches_by_address_id"] += 1
            return reading.address_meter_id, MATCHED_BY_ADDRESS
        for alternate_meter_id in reading.alternate_meter_ids:
            if (alternate_meter_id, channel) in self._configured_keys:
                return alternate_meter_id, MATCHED_BY_ALIAS
        return None

    def get_state(self, meter_id: str, channel: str) -> ElehantChannelState | None:
        """Return the latest state for a channel."""
        return self._states.get((str(meter_id), str(channel)))

    def async_update_repair_issues(self, now: float | None = None) -> None:
        """Update runtime repair issues."""
        if self.hass is None:
            return
        current_time = time.time() if now is None else now
        if (
            current_time - self._started_at
            < DEFAULT_NEVER_SEEN_REPAIR_GRACE_SECONDS
        ):
            return
        async_update_never_seen_repair_issues(
            self.hass,
            self.config,
            set(self._states),
        )

    def is_available(self, meter_id: str, channel: str, now: float | None = None) -> bool:
        """Return whether a channel is available according to HA entity semantics."""
        meter_id = str(meter_id)
        options = self._meter_options.get(meter_id, {})
        if not options.get(CONF_AVAILABILITY_ENABLED, True):
            return True
        state = self.get_state(meter_id, channel)
        if state is None or state.last_seen is None:
            return True
        timeout_seconds = int(options.get(CONF_AVAILABILITY_TIMEOUT_MINUTES, 60)) * 60
        return (time.time() if now is None else now) - state.last_seen <= timeout_seconds

    @callback
    def _async_schedule_availability_refresh(
        self,
        key: ElehantChannelKey,
        last_seen: float,
    ) -> None:
        """Schedule a state refresh when a channel crosses its availability timeout."""
        if self.hass is None:
            return

        meter_id, _channel = key
        options = self._meter_options.get(meter_id, {})
        if not options.get(CONF_AVAILABILITY_ENABLED, True):
            self._async_cancel_availability_refresh(key)
            return

        timeout_seconds = int(options.get(CONF_AVAILABILITY_TIMEOUT_MINUTES, 60)) * 60
        delay = max(1, last_seen + timeout_seconds - time.time() + 1)
        self._async_cancel_availability_refresh(key)

        @callback
        def _async_refresh_availability(now: Any) -> None:
            self._availability_refresh_unsub.pop(key, None)
            self._async_notify_listeners()

        self._availability_refresh_unsub[key] = async_call_later(
            self.hass,
            delay,
            _async_refresh_availability,
        )

    @callback
    def _async_cancel_availability_refresh(self, key: ElehantChannelKey) -> None:
        """Cancel a pending availability refresh for a channel."""
        if unsub := self._availability_refresh_unsub.pop(key, None):
            unsub()

    @callback
    def async_shutdown(self) -> None:
        """Cancel pending coordinator callbacks."""
        for unsub in self._availability_refresh_unsub.values():
            unsub()
        self._availability_refresh_unsub.clear()

    def recent_unknown_packets(
        self,
        now: float | None = None,
        ttl_seconds: int = DEFAULT_DISCOVERY_CANDIDATE_TTL_SECONDS,
    ) -> dict[str, ElehantUnknownPacket]:
        """Return unknown packets recent enough to be offered for discovery."""
        current_time = time.time() if now is None else now
        self._prune_unknown_packets(current_time)
        return {
            meter_id: candidate
            for meter_id, candidate in self.unknown_packets.items()
            if current_time - candidate.last_seen <= ttl_seconds
        }

    def _track_unknown(self, reading: ElehantReading, now: float) -> None:
        """Track an unmatched reading for diagnostics and discovery."""
        self._prune_unknown_packets(now)
        candidate = self.unknown_packets.get(reading.meter_id)
        if candidate is None:
            self.unknown_packets[reading.meter_id] = ElehantUnknownPacket(
                meter_id=reading.meter_id,
                manufacturer_meter_id=reading.manufacturer_meter_id,
                address_meter_id=reading.address_meter_id,
                packet_kind=reading.packet_kind.value,
                rssi=reading.rssi,
                first_seen=now,
                last_seen=now,
                temperature_observed=reading.temperature_celsius is not None,
            )
            self._prune_unknown_packets(now)
            return
        candidate.last_seen = now
        candidate.rssi = reading.rssi
        candidate.count += 1
        candidate.temperature_observed = (
            candidate.temperature_observed or reading.temperature_celsius is not None
        )
        self._prune_unknown_packets(now)

    def _prune_unknown_packets(self, now: float | None = None) -> None:
        """Keep unknown packet storage bounded in time and size."""
        current_time = time.time() if now is None else now
        expired = [
            meter_id
            for meter_id, candidate in self.unknown_packets.items()
            if current_time - candidate.last_seen > DEFAULT_DISCOVERY_CANDIDATE_TTL_SECONDS
        ]
        for meter_id in expired:
            self.unknown_packets.pop(meter_id, None)

        overflow = len(self.unknown_packets) - MAX_UNKNOWN_PACKETS
        if overflow <= 0:
            return
        oldest_meter_ids = sorted(
            self.unknown_packets,
            key=lambda meter_id: self.unknown_packets[meter_id].last_seen,
        )[:overflow]
        for meter_id in oldest_meter_ids:
            self.unknown_packets.pop(meter_id, None)

    def diagnostics(self) -> dict[str, Any]:
        """Return diagnostic coordinator state."""
        self.async_update_repair_issues()
        return {
            "configured_channels": [
                {"meter_id": meter_id, "channel": channel}
                for meter_id, channel in sorted(self._configured_keys)
            ],
            "latest": {
                f"{meter_id}/{channel}": {
                    "last_seen": state.last_seen,
                    "rssi": state.rssi,
                    "packet_count": state.packet_count,
                    "matched_by": state.matched_by,
                    "has_raw_count": state.raw_count is not None,
                    "has_temperature": state.temperature_celsius is not None,
                    "available": self.is_available(meter_id, channel),
                }
                for (meter_id, channel), state in self._states.items()
            },
            "unknown_packets": {
                meter_id: {
                    "manufacturer_meter_id": candidate.manufacturer_meter_id,
                    "address_meter_id": candidate.address_meter_id,
                    "packet_kind": candidate.packet_kind,
                    "rssi": candidate.rssi,
                    "first_seen": candidate.first_seen,
                    "last_seen": candidate.last_seen,
                    "count": candidate.count,
                    "temperature_observed": candidate.temperature_observed,
                    "discovery_candidate": meter_id in self.recent_unknown_packets(),
                }
                for meter_id, candidate in sorted(self.unknown_packets.items())
            },
            "parser_stats": dict(self.parser_stats),
        }
