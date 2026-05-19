"""Tests for Elehant config normalization helpers."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.elehant_water.config_flow import (
    ElehantWaterConfigFlow,
    ElehantWaterOptionsFlow,
    config_entry_has_meters,
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
    CONF_TYPE,
    CONF_WATER_TYPE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_WATER,
    MEASUREMENT_CELSIUS,
    MEASUREMENT_CUBIC_METERS,
)
from custom_components.elehant_water.sensor import PLATFORM_SCHEMA


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


def test_normalize_extended_legacy_yaml_config() -> None:
    """Extended legacy YAML options do not block migration."""
    data = normalize_legacy_yaml_config(
        {
            "measurement_water": MEASUREMENT_CUBIC_METERS,
            "measurement_gas": MEASUREMENT_CUBIC_METERS,
            "devices": [
                {
                    "id": 31560,
                    "name": "Hot water",
                    "type": "water",
                    "water_type": "hot",
                },
            ],
        }
    )

    channel = data[CONF_METERS][0][CONF_CHANNELS][0]
    assert channel[CONF_MEASUREMENT] == MEASUREMENT_CUBIC_METERS


def test_user_extended_fork_yaml_config_is_supported() -> None:
    """A known extended fork YAML format validates and imports."""
    config = {
        "platform": "elehant_water",
        "scan_duration": 10,
        "scan_interval": 600,
        "measurement_water": MEASUREMENT_CUBIC_METERS,
        "measurement_gas": MEASUREMENT_CUBIC_METERS,
        "devices": [
            {
                "id": 18674,
                "type": "water",
                "water_type": "hot",
                "name": "Вода Горячая",
                "name_temp": "Вода Горячая температура",
            },
            {
                "id": 92728,
                "type": "water",
                "water_type": "cold",
                "name": "Вода Холодная",
                "name_temp": "Вода Холодная температура",
            },
            {
                "id": 299,
                "type": "water",
                "water_type": "cold",
                "name": "Вода Холодная 299",
                "name_temp": "Вода Холодная температура 299",
            },
        ],
    }

    validated = PLATFORM_SCHEMA(config)
    data = normalize_legacy_yaml_config(validated)
    meters = {meter[CONF_METER_ID]: meter for meter in data[CONF_METERS]}

    assert set(meters) == {"18674", "92728", "299"}
    assert meters["18674"][CONF_TYPE] == "water"
    assert meters["18674"][CONF_WATER_TYPE] == "hot"
    assert meters["92728"][CONF_WATER_TYPE] == "cold"
    assert meters["299"][CONF_WATER_TYPE] == "cold"

    for meter in meters.values():
        channels = {channel[CONF_CHANNEL]: channel for channel in meter[CONF_CHANNELS]}
        assert set(channels) == {CHANNEL_VOLUME, CHANNEL_TEMPERATURE}
        assert channels[CHANNEL_VOLUME][CONF_MEASUREMENT] == MEASUREMENT_CUBIC_METERS
        assert channels[CHANNEL_TEMPERATURE][CONF_MEASUREMENT] == MEASUREMENT_CELSIUS


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


def test_config_entry_has_meters() -> None:
    """Empty manual entries can be distinguished from migrated entries."""
    assert not config_entry_has_meters(SimpleNamespace(data={CONF_METERS: []}))
    assert config_entry_has_meters(
        SimpleNamespace(
            data={
                CONF_METERS: [
                    {
                        CONF_METER_ID: "31560",
                        CONF_CHANNELS: [
                            {
                                CONF_CHANNEL: CHANNEL_VOLUME,
                                CONF_LEGACY_ID: "31560",
                                "name": "Single",
                            }
                        ],
                    }
                ]
            }
        )
    )


def test_options_flow_factory_uses_modern_base_class_contract() -> None:
    """Options flow must not assign the read-only config_entry property."""
    options_flow = ElehantWaterConfigFlow.async_get_options_flow(
        SimpleNamespace(data={CONF_METERS: []})
    )

    assert isinstance(options_flow, ElehantWaterOptionsFlow)
    assert "config_entry" not in options_flow.__dict__
