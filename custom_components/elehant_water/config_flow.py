"""Config flow for Elehant Water."""

from __future__ import annotations

import json
from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICES, CONF_ID, CONF_NAME
import voluptuous as vol

from .const import (
    CHANNEL_TARIFF_1,
    CHANNEL_TARIFF_2,
    CHANNEL_TEMPERATURE,
    CHANNEL_VOLUME,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_DEVICE_CLASS,
    CONF_LEGACY_ID,
    CONF_MEASUREMENT,
    CONF_MEASUREMENT_GAS,
    CONF_MEASUREMENT_WATER,
    CONF_METERS,
    CONF_METER_ID,
    CONF_TYPE,
    CONF_WATER_TYPE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_WATER,
    DOMAIN,
    MEASUREMENT_CELSIUS,
    MEASUREMENT_LITERS,
)

CONF_NAME_TEMP = "name_temp"
DEVICE_TYPE_GAS = "gas"
VALID_CHANNELS = {
    CHANNEL_VOLUME,
    CHANNEL_TARIFF_1,
    CHANNEL_TARIFF_2,
    CHANNEL_TEMPERATURE,
}


def _channel(
    channel: str,
    legacy_id: str,
    name: str,
    measurement: str,
    device_class: str,
) -> dict[str, str]:
    return {
        CONF_CHANNEL: channel,
        CONF_LEGACY_ID: legacy_id,
        CONF_NAME: name,
        CONF_MEASUREMENT: measurement,
        CONF_DEVICE_CLASS: device_class,
    }


def normalize_legacy_yaml_config(config: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy YAML platform config to config entry data."""
    default_measurement = str(config.get(CONF_MEASUREMENT) or MEASUREMENT_LITERS)
    water_measurement = str(
        config.get(CONF_MEASUREMENT_WATER) or default_measurement
    )
    gas_measurement = str(config.get(CONF_MEASUREMENT_GAS) or default_measurement)
    meters: dict[str, dict[str, Any]] = {}

    for device in config.get(CONF_DEVICES, []):
        legacy_id = str(device[CONF_ID])
        name = str(device[CONF_NAME])
        device_type = device.get(CONF_TYPE)
        water_type = device.get(CONF_WATER_TYPE)
        measurement = (
            gas_measurement
            if str(device_type).lower() == DEVICE_TYPE_GAS
            else water_measurement
        )
        if "_" in legacy_id:
            meter_id, suffix = legacy_id.rsplit("_", 1)
            channel = CHANNEL_TARIFF_1 if suffix == "1" else CHANNEL_TARIFF_2
        else:
            meter_id = legacy_id
            channel = CHANNEL_VOLUME

        meter = meters.setdefault(meter_id, {CONF_METER_ID: meter_id, CONF_CHANNELS: []})
        if device_type is not None:
            meter[CONF_TYPE] = str(device_type)
        if water_type is not None:
            meter[CONF_WATER_TYPE] = str(water_type)
        meter[CONF_CHANNELS].append(
            _channel(channel, legacy_id, name, measurement, DEVICE_CLASS_WATER)
        )

        if CONF_NAME_TEMP in device:
            temp_channel = _channel(
                CHANNEL_TEMPERATURE,
                meter_id,
                str(device[CONF_NAME_TEMP]),
                MEASUREMENT_CELSIUS,
                DEVICE_CLASS_TEMPERATURE,
            )
            if not any(
                channel_data[CONF_CHANNEL] == CHANNEL_TEMPERATURE
                for channel_data in meter[CONF_CHANNELS]
            ):
                meter[CONF_CHANNELS].append(temp_channel)

    return {CONF_METERS: list(meters.values())}


def validate_meters_config(meters: Any) -> bool:
    """Validate normalized meter configuration shape."""
    if not isinstance(meters, list):
        return False

    seen_channels: set[tuple[str, str]] = set()
    for meter in meters:
        if not isinstance(meter, dict):
            return False
        meter_id = meter.get(CONF_METER_ID)
        channels = meter.get(CONF_CHANNELS)
        if meter_id is None or not isinstance(channels, list):
            return False
        meter_id = str(meter_id)
        for channel in channels:
            if not isinstance(channel, dict):
                return False
            channel_name = channel.get(CONF_CHANNEL)
            legacy_id = channel.get(CONF_LEGACY_ID)
            name = channel.get(CONF_NAME)
            if channel_name not in VALID_CHANNELS:
                return False
            if legacy_id is None or name is None:
                return False
            key = (meter_id, str(channel_name))
            if key in seen_channels:
                return False
            seen_channels.add(key)
    return True


def config_entry_has_meters(config_entry: config_entries.ConfigEntry) -> bool:
    """Return whether a config entry already contains meter configuration."""
    return bool(config_entry.data.get(CONF_METERS))


class ElehantWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Elehant Water config flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ElehantWaterOptionsFlow:
        """Create the options flow."""
        return ElehantWaterOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle manual setup."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Elehant Water",
                data={CONF_METERS: []},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    async def async_step_import(
        self,
        import_config: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Import legacy YAML configuration."""
        data = normalize_legacy_yaml_config(import_config)

        entries = self._async_current_entries()
        if entries:
            entry = entries[0]
            if not config_entry_has_meters(entry):
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, **data},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="imported_to_existing_entry")
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(title="Elehant Water", data=data)


class ElehantWaterOptionsFlow(config_entries.OptionsFlow):
    """Handle Elehant Water options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage normalized meter configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                meters = json.loads(user_input[CONF_METERS])
            except ValueError:
                errors["base"] = "invalid_json"
            else:
                if validate_meters_config(meters):
                    data = {**self.config_entry.data, CONF_METERS: meters}
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=data,
                    )
                    return self.async_create_entry(title="", data={})
                errors["base"] = "invalid_meters"

        default_meters = json.dumps(
            self.config_entry.data.get(CONF_METERS, []),
            ensure_ascii=False,
            indent=2,
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_METERS, default=default_meters): str}),
            errors=errors,
        )
