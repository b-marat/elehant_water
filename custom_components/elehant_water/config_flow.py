"""Config flow for Elehant Water."""

from __future__ import annotations

import json
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
import voluptuous as vol

from .config_schema import (
    ID_SOURCE_DISCOVERY,
    ID_SOURCE_MANUAL,
    config_entry_has_meters,
    new_meter_config,
    normalize_config_entry_data,
    normalize_legacy_yaml_config,
    validate_meters_config,
)
from .const import (
    CONF_AVAILABILITY_ENABLED,
    CONF_AVAILABILITY_TIMEOUT_MINUTES,
    CHANNEL_TEMPERATURE,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_ENABLED,
    CONF_IDENTITY_EVIDENCE,
    CONF_IMPORT_YAML,
    CONF_MEASUREMENT,
    CONF_METERS,
    CONF_METER_ID,
    DATA_LEGACY_YAML_CONFIG,
    DEFAULT_AVAILABILITY_TIMEOUT_MINUTES,
    DOMAIN,
    MEASUREMENT_CUBIC_METERS,
    MEASUREMENT_LITERS,
)
from .parser import normalize_meter_id

CONF_ADVANCED_JSON = "advanced_json"
CONF_DISCOVER_METERS = "discover_meters"
CONF_EDIT_METERS = "edit_meters"
CONF_ADD_MANUAL_METER = "add_manual_meter"
CONF_CANDIDATE_METER_ID = "candidate_meter_id"
CONF_METER_INDEX = "meter_index"
CONF_TEMPERATURE_ENABLED = "temperature_enabled"
CONF_VOLUME_UNIT = "volume_unit"


class ElehantWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Elehant Water config flow."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ElehantWaterOptionsFlow:
        """Create the options flow."""
        return ElehantWaterOptionsFlow()

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
                data=normalize_config_entry_data({CONF_METERS: []}),
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
                    data=normalize_config_entry_data({**entry.data, **data}),
                )
                if entry.state is ConfigEntryState.LOADED:
                    await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="imported_to_existing_entry")
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(title="Elehant Water", data=data)


class ElehantWaterOptionsFlow(config_entries.OptionsFlow):
    """Handle Elehant Water options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                CONF_EDIT_METERS,
                CONF_ADD_MANUAL_METER,
                CONF_DISCOVER_METERS,
                CONF_IMPORT_YAML,
                CONF_ADVANCED_JSON,
            ],
        )

    async def async_step_import_yaml(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Import captured legacy YAML configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            legacy_config = self.hass.data.get(DOMAIN, {}).get(DATA_LEGACY_YAML_CONFIG)
            if legacy_config:
                data = normalize_legacy_yaml_config(legacy_config)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=normalize_config_entry_data({**self.config_entry.data, **data}),
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            errors["base"] = "no_yaml_config"

        return self.async_show_form(
            step_id="import_yaml",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_advanced_json(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage normalized meter configuration as JSON."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                meters = json.loads(user_input[CONF_METERS])
            except ValueError:
                errors["base"] = "invalid_json"
            else:
                if validate_meters_config(meters):
                    data = normalize_config_entry_data(
                        {**self.config_entry.data, CONF_METERS: meters}
                    )
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
            step_id="advanced_json",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_METERS, default=default_meters): str,
                }
            ),
            errors=errors,
        )

    async def async_step_edit_meters(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a meter to edit."""
        meters = self.config_entry.data.get(CONF_METERS, [])
        if not meters:
            return self.async_abort(reason="no_meters")

        if user_input is not None:
            self._meter_index = int(user_input[CONF_METER_INDEX])
            return await self.async_step_edit_meter()

        meter_options = {
            str(index): f"{meter.get(CONF_METER_ID)}"
            for index, meter in enumerate(meters)
        }
        return self.async_show_form(
            step_id="edit_meters",
            data_schema=vol.Schema(
                {vol.Required(CONF_METER_INDEX): vol.In(meter_options)}
            ),
        )

    async def async_step_edit_meter(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit common settings for one meter."""
        meters = list(self.config_entry.data.get(CONF_METERS, []))
        meter_index = getattr(self, "_meter_index", 0)
        meter = dict(meters[meter_index])
        channels = [dict(channel) for channel in meter.get(CONF_CHANNELS, [])]
        volume_channel = next(
            (
                channel
                for channel in channels
                if channel.get(CONF_CHANNEL) != CHANNEL_TEMPERATURE
            ),
            channels[0],
        )
        temperature_channel = next(
            (
                channel
                for channel in channels
                if channel.get(CONF_CHANNEL) == CHANNEL_TEMPERATURE
            ),
            None,
        )

        if user_input is not None:
            volume_channel[CONF_NAME] = str(user_input[CONF_NAME])
            volume_unit = str(user_input[CONF_VOLUME_UNIT])
            for channel in channels:
                if channel.get(CONF_CHANNEL) != CHANNEL_TEMPERATURE:
                    channel[CONF_MEASUREMENT] = volume_unit
            if temperature_channel is not None:
                temperature_channel[CONF_ENABLED] = bool(
                    user_input[CONF_TEMPERATURE_ENABLED]
                )
            meter[CONF_AVAILABILITY_ENABLED] = bool(
                user_input[CONF_AVAILABILITY_ENABLED]
            )
            meter[CONF_AVAILABILITY_TIMEOUT_MINUTES] = int(
                user_input[CONF_AVAILABILITY_TIMEOUT_MINUTES]
            )
            meter[CONF_CHANNELS] = channels
            meters[meter_index] = meter
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=normalize_config_entry_data(
                    {**self.config_entry.data, CONF_METERS: meters}
                ),
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="edit_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=volume_channel[CONF_NAME]): str,
                    vol.Required(
                        CONF_VOLUME_UNIT,
                        default=volume_channel.get(
                            CONF_MEASUREMENT, MEASUREMENT_CUBIC_METERS
                        ),
                    ): vol.In([MEASUREMENT_CUBIC_METERS, MEASUREMENT_LITERS]),
                    vol.Optional(
                        CONF_TEMPERATURE_ENABLED,
                        default=(
                            bool(temperature_channel.get(CONF_ENABLED, True))
                            if temperature_channel is not None
                            else False
                        ),
                    ): bool,
                    vol.Required(
                        CONF_AVAILABILITY_ENABLED,
                        default=meter.get(CONF_AVAILABILITY_ENABLED, True),
                    ): bool,
                    vol.Required(
                        CONF_AVAILABILITY_TIMEOUT_MINUTES,
                        default=meter.get(
                            CONF_AVAILABILITY_TIMEOUT_MINUTES,
                            DEFAULT_AVAILABILITY_TIMEOUT_MINUTES,
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
        )

    async def async_step_discover_meters(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select a recently seen unknown meter to add."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        candidates = coordinator.recent_unknown_packets() if coordinator else {}
        configured_meter_ids = {
            str(meter[CONF_METER_ID])
            for meter in self.config_entry.data.get(CONF_METERS, [])
        }
        candidate_options = {
            meter_id: meter_id
            for meter_id in sorted(candidates)
            if meter_id not in configured_meter_ids
        }
        if not candidate_options:
            return self.async_abort(reason="no_discovered_meters")

        if user_input is not None:
            self._candidate_meter_id = str(user_input[CONF_CANDIDATE_METER_ID])
            return await self.async_step_add_discovered_meter()

        return self.async_show_form(
            step_id="discover_meters",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CANDIDATE_METER_ID): vol.In(candidate_options),
                }
            ),
        )

    async def async_step_add_discovered_meter(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Add a discovered meter."""
        meter_id = str(getattr(self, "_candidate_meter_id"))
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        candidate = getattr(coordinator, "unknown_packets", {}).get(meter_id)
        temperature_observed = bool(
            getattr(candidate, "temperature_observed", False)
        )

        if user_input is not None:
            meters = list(self.config_entry.data.get(CONF_METERS, []))
            meters.append(
                new_meter_config(
                    meter_id=meter_id,
                    id_source=ID_SOURCE_DISCOVERY,
                    name=str(user_input[CONF_NAME]),
                    volume_unit=str(user_input[CONF_VOLUME_UNIT]),
                    temperature_enabled=bool(user_input[CONF_TEMPERATURE_ENABLED]),
                    availability_enabled=bool(user_input[CONF_AVAILABILITY_ENABLED]),
                    availability_timeout_minutes=int(
                        user_input[CONF_AVAILABILITY_TIMEOUT_MINUTES]
                    ),
                    identity_evidence={
                        "manufacturer_meter_id": getattr(
                            candidate, "manufacturer_meter_id", meter_id
                        ),
                        "address_meter_id": getattr(
                            candidate, "address_meter_id", meter_id
                        ),
                    },
                )
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=normalize_config_entry_data(
                    {**self.config_entry.data, CONF_METERS: meters}
                ),
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_discovered_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=f"Elehant {meter_id}"): str,
                    vol.Required(
                        CONF_VOLUME_UNIT,
                        default=MEASUREMENT_CUBIC_METERS,
                    ): vol.In([MEASUREMENT_CUBIC_METERS, MEASUREMENT_LITERS]),
                    vol.Optional(
                        CONF_TEMPERATURE_ENABLED,
                        default=temperature_observed,
                    ): bool,
                    vol.Required(
                        CONF_AVAILABILITY_ENABLED,
                        default=True,
                    ): bool,
                    vol.Required(
                        CONF_AVAILABILITY_TIMEOUT_MINUTES,
                        default=DEFAULT_AVAILABILITY_TIMEOUT_MINUTES,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
            description_placeholders={CONF_METER_ID: meter_id},
        )

    async def async_step_add_manual_meter(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Add a meter manually when discovery has not seen it yet."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                meter_id = normalize_meter_id(user_input[CONF_METER_ID])
            except (TypeError, ValueError):
                errors[CONF_METER_ID] = "invalid_meter_id"
            else:
                configured_meter_ids = {
                    str(meter[CONF_METER_ID])
                    for meter in self.config_entry.data.get(CONF_METERS, [])
                }
                if meter_id in configured_meter_ids:
                    errors[CONF_METER_ID] = "meter_already_configured"
                else:
                    meters = list(self.config_entry.data.get(CONF_METERS, []))
                    meters.append(
                        new_meter_config(
                            meter_id=meter_id,
                            id_source=ID_SOURCE_MANUAL,
                            name=str(user_input[CONF_NAME]),
                            volume_unit=str(user_input[CONF_VOLUME_UNIT]),
                            temperature_enabled=bool(
                                user_input[CONF_TEMPERATURE_ENABLED]
                            ),
                            availability_enabled=bool(
                                user_input[CONF_AVAILABILITY_ENABLED]
                            ),
                            availability_timeout_minutes=int(
                                user_input[CONF_AVAILABILITY_TIMEOUT_MINUTES]
                            ),
                        )
                    )
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=normalize_config_entry_data(
                            {**self.config_entry.data, CONF_METERS: meters}
                        ),
                    )
                    return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_manual_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_METER_ID): str,
                    vol.Required(CONF_NAME): str,
                    vol.Required(
                        CONF_VOLUME_UNIT,
                        default=MEASUREMENT_CUBIC_METERS,
                    ): vol.In([MEASUREMENT_CUBIC_METERS, MEASUREMENT_LITERS]),
                    vol.Optional(
                        CONF_TEMPERATURE_ENABLED,
                        default=True,
                    ): bool,
                    vol.Required(
                        CONF_AVAILABILITY_ENABLED,
                        default=True,
                    ): bool,
                    vol.Required(
                        CONF_AVAILABILITY_TIMEOUT_MINUTES,
                        default=DEFAULT_AVAILABILITY_TIMEOUT_MINUTES,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            ),
            errors=errors,
        )
