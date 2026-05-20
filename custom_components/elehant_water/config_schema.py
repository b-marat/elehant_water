"""Config schema helpers for Elehant Water."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICES, CONF_ID, CONF_NAME

from .const import (
    CHANNEL_TARIFF_1,
    CHANNEL_TARIFF_2,
    CHANNEL_TEMPERATURE,
    CHANNEL_TOTAL,
    CHANNEL_VOLUME,
    CONF_AVAILABILITY_ENABLED,
    CONF_AVAILABILITY_TIMEOUT_MINUTES,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_DEVICE_CLASS,
    CONF_ENABLED,
    CONF_ID_SOURCE,
    CONF_IDENTITY_EVIDENCE,
    CONF_LEGACY_ID,
    CONF_LEGACY_METER_ID,
    CONF_MEASUREMENT,
    CONF_MEASUREMENT_GAS,
    CONF_MEASUREMENT_WATER,
    CONF_METERS,
    CONF_METER_ID,
    CONF_NAME_TEMP,
    CONF_STATE_CLASS,
    CONF_TYPE,
    CONF_WATER_TYPE,
    DEFAULT_AVAILABILITY_TIMEOUT_MINUTES,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_WATER,
    ID_SOURCE_DISCOVERY,
    ID_SOURCE_MANUAL,
    ID_SOURCE_YAML,
    MEASUREMENT_CELSIUS,
    MEASUREMENT_CUBIC_METERS,
    MEASUREMENT_LITERS,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from .parser import normalize_meter_id

DEVICE_TYPE_GAS = "gas"

VALID_CHANNELS = {
    CHANNEL_VOLUME,
    CHANNEL_TARIFF_1,
    CHANNEL_TARIFF_2,
    CHANNEL_TOTAL,
    CHANNEL_TEMPERATURE,
}


def channel_config(
    channel: str,
    legacy_id: str,
    name: str,
    measurement: str,
    device_class: str,
    state_class: str,
    enabled: bool = True,
    water_type: str | None = None,
) -> dict[str, Any]:
    """Build a normalized channel config fragment."""
    data: dict[str, Any] = {
        "channel_id": channel,
        CONF_CHANNEL: channel,
        CONF_LEGACY_ID: legacy_id,
        CONF_NAME: name,
        CONF_MEASUREMENT: measurement,
        CONF_DEVICE_CLASS: device_class,
        CONF_STATE_CLASS: state_class,
        CONF_ENABLED: enabled,
    }
    if water_type is not None:
        data[CONF_WATER_TYPE] = water_type
    return data


def normalize_channel_config(channel: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized channel config while preserving legacy fields."""
    channel_name = str(channel.get(CONF_CHANNEL) or channel.get("channel_id"))
    measurement = str(channel.get(CONF_MEASUREMENT) or MEASUREMENT_LITERS)
    device_class = str(channel.get(CONF_DEVICE_CLASS) or DEVICE_CLASS_WATER)
    if channel_name == CHANNEL_TEMPERATURE:
        measurement = MEASUREMENT_CELSIUS
        device_class = DEVICE_CLASS_TEMPERATURE
        state_class = STATE_CLASS_MEASUREMENT
    else:
        state_class = STATE_CLASS_TOTAL_INCREASING

    normalized: dict[str, Any] = {
        **channel,
        "channel_id": channel_name,
        CONF_CHANNEL: channel_name,
        CONF_NAME: str(channel.get(CONF_NAME) or channel_name),
        CONF_MEASUREMENT: measurement,
        CONF_DEVICE_CLASS: device_class,
        CONF_STATE_CLASS: str(channel.get(CONF_STATE_CLASS) or state_class),
        CONF_ENABLED: bool(channel.get(CONF_ENABLED, True)),
    }
    if CONF_LEGACY_ID in channel:
        normalized[CONF_LEGACY_ID] = str(channel[CONF_LEGACY_ID])
    return normalized


def new_meter_config(
    *,
    meter_id: str,
    id_source: str,
    name: str,
    volume_unit: str,
    temperature_enabled: bool,
    availability_enabled: bool,
    availability_timeout_minutes: int,
    identity_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build normalized config for a manually added or discovered meter."""
    channels = [
        channel_config(
            CHANNEL_VOLUME,
            "",
            name,
            volume_unit,
            DEVICE_CLASS_WATER,
            STATE_CLASS_TOTAL_INCREASING,
        )
    ]
    channels[0].pop(CONF_LEGACY_ID, None)
    if temperature_enabled:
        temp_channel = channel_config(
            CHANNEL_TEMPERATURE,
            "",
            f"{name} temperature",
            MEASUREMENT_CELSIUS,
            DEVICE_CLASS_TEMPERATURE,
            STATE_CLASS_MEASUREMENT,
        )
        temp_channel.pop(CONF_LEGACY_ID, None)
        channels.append(temp_channel)

    return normalize_config_entry_data(
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: normalize_meter_id(meter_id),
                    CONF_ID_SOURCE: id_source,
                    CONF_IDENTITY_EVIDENCE: identity_evidence or {},
                    CONF_AVAILABILITY_ENABLED: availability_enabled,
                    CONF_AVAILABILITY_TIMEOUT_MINUTES: availability_timeout_minutes,
                    CONF_CHANNELS: channels,
                }
            ]
        }
    )[CONF_METERS][0]


def normalize_config_entry_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize config entry data to the current shape."""
    meters: list[dict[str, Any]] = []
    for meter in data.get(CONF_METERS, []):
        raw_meter_id = str(meter.get(CONF_METER_ID))
        meter_id = normalize_meter_id(raw_meter_id)
        evidence = dict(meter.get(CONF_IDENTITY_EVIDENCE) or {})
        normalized_meter = {
            **meter,
            CONF_METER_ID: meter_id,
            CONF_ID_SOURCE: str(meter.get(CONF_ID_SOURCE) or ID_SOURCE_YAML),
            CONF_IDENTITY_EVIDENCE: evidence,
            CONF_LEGACY_METER_ID: str(meter.get(CONF_LEGACY_METER_ID) or raw_meter_id),
            CONF_AVAILABILITY_ENABLED: bool(
                meter.get(CONF_AVAILABILITY_ENABLED, True)
            ),
            CONF_AVAILABILITY_TIMEOUT_MINUTES: int(
                meter.get(
                    CONF_AVAILABILITY_TIMEOUT_MINUTES,
                    DEFAULT_AVAILABILITY_TIMEOUT_MINUTES,
                )
            ),
            CONF_CHANNELS: [
                normalize_channel_config(channel)
                for channel in meter.get(CONF_CHANNELS, [])
            ],
        }
        meters.append(normalized_meter)
    return {**data, CONF_METERS: meters}


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

        canonical_meter_id = normalize_meter_id(meter_id)
        meter = meters.setdefault(
            canonical_meter_id,
            {
                CONF_METER_ID: canonical_meter_id,
                CONF_LEGACY_METER_ID: meter_id,
                CONF_ID_SOURCE: ID_SOURCE_YAML,
                CONF_IDENTITY_EVIDENCE: {},
                CONF_AVAILABILITY_ENABLED: True,
                CONF_AVAILABILITY_TIMEOUT_MINUTES: DEFAULT_AVAILABILITY_TIMEOUT_MINUTES,
                CONF_CHANNELS: [],
            },
        )
        if device_type is not None:
            meter[CONF_TYPE] = str(device_type)
        if water_type is not None:
            meter[CONF_WATER_TYPE] = str(water_type)
        meter[CONF_CHANNELS].append(
            channel_config(
                channel,
                legacy_id,
                name,
                measurement,
                DEVICE_CLASS_WATER,
                STATE_CLASS_TOTAL_INCREASING,
                water_type=str(water_type) if water_type is not None else None,
            )
        )

        if CONF_NAME_TEMP in device:
            temp_channel = channel_config(
                CHANNEL_TEMPERATURE,
                meter_id,
                str(device[CONF_NAME_TEMP]),
                MEASUREMENT_CELSIUS,
                DEVICE_CLASS_TEMPERATURE,
                STATE_CLASS_MEASUREMENT,
            )
            if not any(
                channel_data[CONF_CHANNEL] == CHANNEL_TEMPERATURE
                for channel_data in meter[CONF_CHANNELS]
            ):
                meter[CONF_CHANNELS].append(temp_channel)

    return normalize_config_entry_data({CONF_METERS: list(meters.values())})


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
        try:
            meter_id = normalize_meter_id(meter_id)
        except (TypeError, ValueError):
            return False
        if not channels:
            return False
        timeout = meter.get(
            CONF_AVAILABILITY_TIMEOUT_MINUTES,
            DEFAULT_AVAILABILITY_TIMEOUT_MINUTES,
        )
        try:
            if int(timeout) <= 0:
                return False
        except (TypeError, ValueError):
            return False
        for channel in channels:
            if not isinstance(channel, dict):
                return False
            channel_name = channel.get(CONF_CHANNEL) or channel.get("channel_id")
            name = channel.get(CONF_NAME)
            if channel_name not in VALID_CHANNELS:
                return False
            if name is None:
                return False
            measurement = channel.get(CONF_MEASUREMENT)
            device_class = channel.get(CONF_DEVICE_CLASS)
            state_class = channel.get(CONF_STATE_CLASS)
            if channel_name == CHANNEL_TEMPERATURE:
                if measurement not in (None, MEASUREMENT_CELSIUS):
                    return False
                if device_class not in (None, DEVICE_CLASS_TEMPERATURE):
                    return False
                if state_class not in (None, STATE_CLASS_MEASUREMENT):
                    return False
            else:
                if measurement not in (None, MEASUREMENT_LITERS, MEASUREMENT_CUBIC_METERS):
                    return False
                if device_class not in (None, DEVICE_CLASS_WATER):
                    return False
                if state_class not in (None, STATE_CLASS_TOTAL_INCREASING):
                    return False
            key = (meter_id, str(channel_name))
            if key in seen_channels:
                return False
            seen_channels.add(key)
    return True


def config_entry_has_meters(config_entry: config_entries.ConfigEntry) -> bool:
    """Return whether a config entry already contains meter configuration."""
    return bool(config_entry.data.get(CONF_METERS))


def duplicate_meter_ids(meters: list[dict[str, Any]]) -> list[str]:
    """Return canonical meter IDs repeated in a meter list."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for meter in meters:
        try:
            meter_id = normalize_meter_id(meter.get(CONF_METER_ID))
        except (TypeError, ValueError):
            continue
        if meter_id in seen:
            duplicates.add(meter_id)
        seen.add(meter_id)
    return sorted(duplicates)


__all__ = [
    "ID_SOURCE_DISCOVERY",
    "ID_SOURCE_MANUAL",
    "channel_config",
    "config_entry_has_meters",
    "duplicate_meter_ids",
    "new_meter_config",
    "normalize_config_entry_data",
    "normalize_legacy_yaml_config",
    "validate_meters_config",
]
