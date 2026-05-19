"""Tests for Elehant config normalization helpers."""

from __future__ import annotations

from custom_components.elehant_water.config_flow import (
    normalize_legacy_yaml_config,
    validate_meters_config,
)
from custom_components.elehant_water.const import (
    CHANNEL_TARIFF_1,
    CHANNEL_TARIFF_2,
    CHANNEL_TEMPERATURE,
    CHANNEL_VOLUME,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_LEGACY_ID,
    CONF_MEASUREMENT,
    CONF_METERS,
    CONF_METER_ID,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_WATER,
    MEASUREMENT_CELSIUS,
    MEASUREMENT_CUBIC_METERS,
)


def test_normalize_legacy_yaml_config() -> None:
    """Legacy YAML devices are normalized into physical meters and channels."""
    data = normalize_legacy_yaml_config(
        {
            "measurement": MEASUREMENT_CUBIC_METERS,
            "devices": [
                {"id": 31560, "name": "Single"},
                {"id": "31562_1", "name": "Tariff 1", "name_temp": "Temp"},
                {"id": "31562_2", "name": "Tariff 2"},
            ],
        }
    )

    meters = {meter[CONF_METER_ID]: meter for meter in data[CONF_METERS]}

    assert set(meters) == {"31560", "31562"}

    single_channels = meters["31560"][CONF_CHANNELS]
    assert single_channels == [
        {
            CONF_CHANNEL: CHANNEL_VOLUME,
            CONF_LEGACY_ID: "31560",
            "name": "Single",
            CONF_MEASUREMENT: MEASUREMENT_CUBIC_METERS,
            "device_class": DEVICE_CLASS_WATER,
        }
    ]

    tariff_channels = {
        channel[CONF_CHANNEL]: channel for channel in meters["31562"][CONF_CHANNELS]
    }
    assert set(tariff_channels) == {
        CHANNEL_TARIFF_1,
        CHANNEL_TARIFF_2,
        CHANNEL_TEMPERATURE,
    }
    assert tariff_channels[CHANNEL_TARIFF_1][CONF_LEGACY_ID] == "31562_1"
    assert tariff_channels[CHANNEL_TARIFF_2][CONF_LEGACY_ID] == "31562_2"
    assert tariff_channels[CHANNEL_TEMPERATURE][CONF_LEGACY_ID] == "31562"
    assert tariff_channels[CHANNEL_TEMPERATURE][CONF_MEASUREMENT] == MEASUREMENT_CELSIUS
    assert tariff_channels[CHANNEL_TEMPERATURE]["device_class"] == DEVICE_CLASS_TEMPERATURE


def test_validate_meters_config() -> None:
    """Normalized meter config validation catches broken option payloads."""
    valid = normalize_legacy_yaml_config(
        {"devices": [{"id": 31560, "name": "Single"}]}
    )[CONF_METERS]

    assert validate_meters_config(valid)
    assert not validate_meters_config({"not": "a list"})
    assert not validate_meters_config([{CONF_METER_ID: "31560"}])
    assert not validate_meters_config(
        [
            {
                CONF_METER_ID: "31560",
                CONF_CHANNELS: [
                    {
                        CONF_CHANNEL: "unknown",
                        CONF_LEGACY_ID: "31560",
                        "name": "Single",
                    }
                ],
            }
        ]
    )
