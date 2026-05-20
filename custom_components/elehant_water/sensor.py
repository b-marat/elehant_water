"""Sensor platform for Elehant Water."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_NAME,
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    CHANNEL_TARIFF_1,
    CHANNEL_TARIFF_2,
    CHANNEL_TEMPERATURE,
    CHANNEL_TOTAL,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_DEVICE_CLASS,
    CONF_ENABLED,
    CONF_LEGACY_ID,
    CONF_MEASUREMENT,
    CONF_MEASUREMENT_GAS,
    CONF_MEASUREMENT_WATER,
    CONF_METERS,
    CONF_METER_ID,
    CONF_NAME_TEMP,
    CONF_STATE_CLASS,
    CONF_TYPE,
    CONF_WATER_TYPE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_WATER,
    DIAGNOSTIC_LAST_SEEN,
    DIAGNOSTIC_MATCHED_BY,
    DIAGNOSTIC_PACKET_COUNT,
    DIAGNOSTIC_RSSI,
    DOMAIN,
    MANUFACTURER_ELEHANT_FALLBACK,
    MATCHED_BY_ADDRESS,
    MATCHED_BY_ALIAS,
    MATCHED_BY_CONFIGURED,
    MATCHED_BY_MANUFACTURER,
    MEASUREMENT_CELSIUS,
    MEASUREMENT_CUBIC_METERS,
    MEASUREMENT_LITERS,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from .coordinator import ElehantWaterCoordinator

LEGACY_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): vol.Any(str, int),
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_NAME_TEMP): cv.string,
        vol.Optional(CONF_TYPE): cv.string,
        vol.Optional(CONF_WATER_TYPE): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional("scan_duration"): cv.positive_int,
        vol.Optional("scan_interval"): vol.Any(cv.positive_int, cv.time_period),
        vol.Optional(CONF_MEASUREMENT, default=MEASUREMENT_LITERS): vol.In(
            [MEASUREMENT_LITERS, MEASUREMENT_CUBIC_METERS]
        ),
        vol.Optional(CONF_MEASUREMENT_WATER): vol.In(
            [MEASUREMENT_LITERS, MEASUREMENT_CUBIC_METERS]
        ),
        vol.Optional(CONF_MEASUREMENT_GAS): vol.In(
            [MEASUREMENT_LITERS, MEASUREMENT_CUBIC_METERS]
        ),
        vol.Required(CONF_DEVICES): [LEGACY_DEVICE_SCHEMA],
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
        channels = meter.get(CONF_CHANNELS, [])
        for channel in channels:
            if channel.get(CONF_ENABLED, True):
                entities.append(ElehantSensor(coordinator, meter_id, channel))
                entities.extend(
                    ElehantDiagnosticSensor(coordinator, meter_id, channel, diagnostic)
                    for diagnostic in (
                        DIAGNOSTIC_LAST_SEEN,
                        DIAGNOSTIC_RSSI,
                        DIAGNOSTIC_PACKET_COUNT,
                        DIAGNOSTIC_MATCHED_BY,
                    )
                )
        enabled_channel_names = {
            str(channel[CONF_CHANNEL])
            for channel in channels
            if channel.get(CONF_ENABLED, True)
        }
        if (
            {CHANNEL_TARIFF_1, CHANNEL_TARIFF_2}.issubset(enabled_channel_names)
            and CHANNEL_TOTAL not in enabled_channel_names
        ):
            tariff_channel = next(
                channel
                for channel in channels
                if channel[CONF_CHANNEL] == CHANNEL_TARIFF_1
            )
            entities.append(
                ElehantSensor(
                    coordinator,
                    meter_id,
                    {
                        CONF_CHANNEL: CHANNEL_TOTAL,
                        CONF_NAME: f"{tariff_channel[CONF_NAME]} total",
                        CONF_MEASUREMENT: tariff_channel.get(
                            CONF_MEASUREMENT, MEASUREMENT_LITERS
                        ),
                        CONF_DEVICE_CLASS: DEVICE_CLASS_WATER,
                        CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                        "_enabled_default": False,
                    },
                )
            )
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
        self.legacy_id = (
            str(channel_config[CONF_LEGACY_ID])
            if CONF_LEGACY_ID in channel_config
            else None
        )
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
        self._attr_state_class = self._state_class(
            str(channel_config.get(CONF_STATE_CLASS) or "")
        )
        if channel_config.get("_enabled_default") is False:
            self._attr_entity_registry_enabled_default = False
        self._remove_listener: Callable[[], None] | None = None

    def _unique_id(self) -> str:
        """Return a legacy-compatible unique ID."""
        if self.legacy_id is None:
            return f"elehant_{self.meter_id}_{self.channel}"
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

    @staticmethod
    def _state_class(state_class: str) -> SensorStateClass | None:
        """Map stored state class strings to Home Assistant sensor state classes."""
        if state_class == STATE_CLASS_TOTAL_INCREASING:
            return SensorStateClass.TOTAL_INCREASING
        if state_class == STATE_CLASS_MEASUREMENT:
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def available(self) -> bool:
        """Return whether the sensor is available."""
        if self.channel == CHANNEL_TOTAL:
            return self.coordinator.is_available(
                self.meter_id, CHANNEL_TARIFF_1
            ) and self.coordinator.is_available(self.meter_id, CHANNEL_TARIFF_2)
        return self.coordinator.is_available(self.meter_id, self.channel)

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
        if self.channel == CHANNEL_TOTAL:
            tariff_1 = self.coordinator.get_state(self.meter_id, CHANNEL_TARIFF_1)
            tariff_2 = self.coordinator.get_state(self.meter_id, CHANNEL_TARIFF_2)
            if (
                tariff_1 is None
                or tariff_2 is None
                or tariff_1.raw_count is None
                or tariff_2.raw_count is None
            ):
                return None
            raw_count = tariff_1.raw_count + tariff_2.raw_count
            if self.measurement == MEASUREMENT_CUBIC_METERS:
                return raw_count / 10000
            return raw_count / 10
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


class ElehantDiagnosticSensor(SensorEntity):
    """Diagnostic entity for an Elehant channel."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: ElehantWaterCoordinator,
        meter_id: str,
        channel_config: dict[str, Any],
        diagnostic: str,
    ) -> None:
        """Initialize the diagnostic sensor."""
        self.coordinator = coordinator
        self.meter_id = str(meter_id)
        self.channel = str(channel_config[CONF_CHANNEL])
        self.diagnostic = diagnostic
        base_name = str(channel_config[CONF_NAME])
        self._attr_name = f"{base_name} {diagnostic.replace('_', ' ')}"
        self._attr_unique_id = (
            f"elehant_{self.meter_id}_{self.channel}_{self.diagnostic}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.meter_id)},
            "manufacturer": MANUFACTURER_ELEHANT_FALLBACK,
            "name": f"Elehant {self.meter_id}",
        }
        if diagnostic == DIAGNOSTIC_LAST_SEEN:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif diagnostic == DIAGNOSTIC_RSSI:
            self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
            self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        elif diagnostic == DIAGNOSTIC_MATCHED_BY:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = [
                MATCHED_BY_MANUFACTURER,
                MATCHED_BY_ADDRESS,
                MATCHED_BY_ALIAS,
                MATCHED_BY_CONFIGURED,
            ]
        self._remove_listener: Callable[[], None] | None = None

    @property
    def available(self) -> bool:
        """Return whether diagnostic data is available."""
        return self.coordinator.get_state(self.meter_id, self.channel) is not None

    @property
    def native_value(self) -> int | str | datetime | None:
        """Return the diagnostic value."""
        state = self.coordinator.get_state(self.meter_id, self.channel)
        if state is None:
            return None
        if self.diagnostic == DIAGNOSTIC_LAST_SEEN:
            if state.last_seen is None:
                return None
            return datetime.fromtimestamp(state.last_seen, timezone.utc)
        if self.diagnostic == DIAGNOSTIC_RSSI:
            return state.rssi
        if self.diagnostic == DIAGNOSTIC_PACKET_COUNT:
            return state.packet_count
        if self.diagnostic == DIAGNOSTIC_MATCHED_BY:
            return state.matched_by
        return None

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
