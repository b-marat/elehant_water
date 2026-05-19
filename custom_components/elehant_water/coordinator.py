"""Runtime coordinator for Elehant Water readings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback

from .const import (
    CHANNEL_TEMPERATURE,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_METERS,
    CONF_METER_ID,
)
from .models import ElehantChannel, ElehantReading
from .parser import looks_like_elehant_address, parse_manufacturer_data

_LOGGER = logging.getLogger(__name__)

ElehantChannelKey = tuple[str, str]


@dataclass
class ElehantChannelState:
    """Latest state for a configured Elehant channel."""

    raw_count: int | None = None
    temperature_celsius: float | None = None
    last_seen: float | None = None
    rssi: int | None = None


class ElehantWaterCoordinator:
    """Coordinate parsed BLE readings and Home Assistant entities."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.config = config
        self._listeners: list[Callable[[], None]] = []
        self._states: dict[ElehantChannelKey, ElehantChannelState] = {}
        self._configured_keys = self._build_configured_keys(config)
        self.unknown_packets: dict[str, float] = {}

    @staticmethod
    def _build_configured_keys(config: dict[str, Any]) -> set[ElehantChannelKey]:
        keys: set[ElehantChannelKey] = set()
        for meter in config.get(CONF_METERS, []):
            meter_id = str(meter[CONF_METER_ID])
            for channel in meter.get(CONF_CHANNELS, []):
                keys.add((meter_id, str(channel[CONF_CHANNEL])))
        return keys

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

        reading = parse_manufacturer_data(
            service_info.address,
            service_info.manufacturer_data,
            service_info.rssi,
        )
        if reading is None:
            return

        updated = self.async_handle_reading(reading)
        if updated:
            _LOGGER.debug("Updated Elehant reading: %s", reading)

    @callback
    def async_handle_reading(self, reading: ElehantReading) -> bool:
        """Store a parsed reading if it belongs to a configured channel."""
        now = time.time()
        updated = False
        key = (reading.meter_id, reading.channel.value)

        if key in self._configured_keys:
            state = self._states.setdefault(key, ElehantChannelState())
            state.raw_count = reading.raw_count
            state.last_seen = now
            state.rssi = reading.rssi
            updated = True
        else:
            self.unknown_packets[reading.meter_id] = now
            _LOGGER.debug(
                "Ignoring Elehant reading for unconfigured meter/channel: %s/%s",
                reading.meter_id,
                reading.channel,
            )

        if reading.temperature_celsius is not None:
            temp_key = (reading.meter_id, ElehantChannel.TEMPERATURE.value)
            if temp_key in self._configured_keys:
                state = self._states.setdefault(temp_key, ElehantChannelState())
                state.temperature_celsius = reading.temperature_celsius
                state.last_seen = now
                state.rssi = reading.rssi
                updated = True

        if updated:
            self._async_notify_listeners()
        return updated

    def get_state(self, meter_id: str, channel: str) -> ElehantChannelState | None:
        """Return the latest state for a channel."""
        return self._states.get((str(meter_id), str(channel)))

    def diagnostics(self) -> dict[str, Any]:
        """Return diagnostic coordinator state."""
        return {
            "configured_channels": [
                {"meter_id": meter_id, "channel": channel}
                for meter_id, channel in sorted(self._configured_keys)
            ],
            "latest": {
                f"{meter_id}/{channel}": {
                    "last_seen": state.last_seen,
                    "rssi": state.rssi,
                    "has_raw_count": state.raw_count is not None,
                    "has_temperature": state.temperature_celsius is not None,
                }
                for (meter_id, channel), state in self._states.items()
            },
            "unknown_packet_meter_ids": sorted(self.unknown_packets),
        }
