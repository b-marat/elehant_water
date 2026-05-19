"""Sensor platform for Elehant Water."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_NAME,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .config_flow import CONF_NAME_TEMP
from .const import (
    CHANNEL_TEMPERATURE,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_DEVICE_CLASS,
    CONF_LEGACY_ID,
    CONF_MEASUREMENT,
    CONF_METERS,
    CONF_METER_ID,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_WATER,
    DOMAIN,
    MANUFACTURER_ELEHANT_FALLBACK,
    MEASUREMENT_CELSIUS,
    MEASUREMENT_CUBIC_METERS,
    MEASUREMENT_LITERS,
)
from .coordinator import ElehantWaterCoordinator

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional("scan_duration"): cv.positive_int,
        vol.Optional("scan_interval"): vol.Any(cv.positive_int, cv.time_period),
        vol.Optional(CONF_MEASUREMENT, default=MEASUREMENT_LITERS): vol.In(
            [MEASUREMENT_LITERS, MEASUREMENT_CUBIC_METERS]
        ),
        vol.Required(CONF_DEVICES): [
            {
                vol.Required(CONF_ID): vol.Any(str, int),
                vol.Required(CONF_NAME): cv.string,
                vol.Optional(CONF_NAME_TEMP): cv.string,
            }
        ],
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Import legacy YAML platform configuration."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data=dict(config),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elehant Water sensors from a config entry."""
    coordinator: ElehantWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ElehantSensor] = []
    for meter in entry.data.get(CONF_METERS, []):
        meter_id = str(meter[CONF_METER_ID])
        for channel in meter.get(CONF_CHANNELS, []):
            entities.append(ElehantSensor(coordinator, meter_id, channel))
    async_add_entities(entities)


class ElehantSensor(SensorEntity):
    """Elehant sensor entity."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: ElehantWaterCoordinator,
        meter_id: str,
        channel_config: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.meter_id = str(meter_id)
        self.channel = str(channel_config[CONF_CHANNEL])
        self.legacy_id = str(channel_config[CONF_LEGACY_ID])
        self.measurement = str(channel_config.get(CONF_MEASUREMENT) or MEASUREMENT_LITERS)
        self._attr_name = str(channel_config[CONF_NAME])
        self._attr_unique_id = self._unique_id()
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.meter_id)},
            "manufacturer": MANUFACTURER_ELEHANT_FALLBACK,
            "name": f"Elehant {self.meter_id}",
        }
        self._attr_device_class = self._device_class(
            str(channel_config.get(CONF_DEVICE_CLASS) or DEVICE_CLASS_WATER)
        )
        self._remove_listener: Callable[[], None] | None = None

    def _unique_id(self) -> str:
        """Return a legacy-compatible unique ID."""
        if self.channel == CHANNEL_TEMPERATURE:
            return f"elehant_temp_{self.legacy_id}"
        return f"elehant_{self.legacy_id}"

    @staticmethod
    def _device_class(device_class: str) -> SensorDeviceClass | None:
        """Map stored device class strings to Home Assistant sensor device classes."""
        if device_class == DEVICE_CLASS_TEMPERATURE:
            return SensorDeviceClass.TEMPERATURE
        if device_class == DEVICE_CLASS_WATER:
            return SensorDeviceClass.WATER
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        if self.channel == CHANNEL_TEMPERATURE:
            return UnitOfTemperature.CELSIUS
        if self.measurement == MEASUREMENT_CUBIC_METERS:
            return UnitOfVolume.CUBIC_METERS
        return UnitOfVolume.LITERS

    @property
    def native_value(self) -> float | None:
        """Return the current sensor value."""
        state = self.coordinator.get_state(self.meter_id, self.channel)
        if state is None:
            return None
        if self.channel == CHANNEL_TEMPERATURE:
            return state.temperature_celsius
        if state.raw_count is None:
            return None
        if self.measurement == MEASUREMENT_CUBIC_METERS:
            return state.raw_count / 10000
        return state.raw_count / 10

    async def async_added_to_hass(self) -> None:
        """Register update listener."""
        self._remove_listener = self.coordinator.async_add_listener(
            self._handle_coordinator_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove update listener."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated coordinator data."""
        self.async_write_ha_state()
