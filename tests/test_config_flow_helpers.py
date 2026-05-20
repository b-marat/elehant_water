"""Tests for Elehant config normalization helpers."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from custom_components.elehant_water.config_flow import (
    ElehantWaterConfigFlow,
    ElehantWaterOptionsFlow,
)
from custom_components.elehant_water.config_schema import (
    config_entry_has_meters,
    normalize_legacy_yaml_config,
    validate_meters_config,
)
from custom_components.elehant_water.const import (
    CHANNEL_TOTAL,
    CHANNEL_TARIFF_1,
    CHANNEL_TARIFF_2,
    CHANNEL_TEMPERATURE,
    CHANNEL_VOLUME,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_AVAILABILITY_ENABLED,
    CONF_AVAILABILITY_TIMEOUT_MINUTES,
    CONF_DEVICE_CLASS,
    CONF_ENABLED,
    CONF_ID_SOURCE,
    CONF_IDENTITY_EVIDENCE,
    CONF_LEGACY_ID,
    CONF_LEGACY_METER_ID,
    CONF_MEASUREMENT,
    CONF_METERS,
    CONF_METER_ID,
    CONF_STATE_CLASS,
    CONF_TYPE,
    CONF_WATER_TYPE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_WATER,
    DOMAIN,
    ID_SOURCE_DISCOVERY,
    ID_SOURCE_MANUAL,
    MEASUREMENT_CELSIUS,
    MEASUREMENT_CUBIC_METERS,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from custom_components.elehant_water.sensor import PLATFORM_SCHEMA


class FakeConfigEntries:
    """Small config entries facade for options flow tests."""

    def __init__(self, entry: SimpleNamespace) -> None:
        self.entry = entry

    def async_get_known_entry(self, entry_id: str) -> SimpleNamespace:
        """Return the linked entry."""
        return self.entry

    def async_update_entry(
        self,
        entry: SimpleNamespace,
        *,
        data: dict | None = None,
        **kwargs: object,
    ) -> bool:
        """Apply config entry data updates."""
        if data is not None:
            entry.data = data
        return True

    async def async_reload(self, entry_id: str) -> None:
        """Pretend to reload an entry."""


class FakeHass:
    """Small Home Assistant facade for options flow tests."""

    def __init__(
        self,
        entry: SimpleNamespace,
        coordinator: object | None = None,
    ) -> None:
        self.config_entries = FakeConfigEntries(entry)
        self.data = {DOMAIN: {entry.entry_id: coordinator} if coordinator else {}}


class FakeDiscoveryCoordinator:
    """Coordinator facade exposing recent discovery candidates."""

    def __init__(self, candidates: dict[str, object]) -> None:
        self._candidates = candidates

    def recent_unknown_packets(self) -> dict[str, object]:
        """Return recent unknown packets."""
        return self._candidates


def make_options_flow(
    data: dict,
    coordinator: object | None = None,
) -> tuple[ElehantWaterOptionsFlow, SimpleNamespace]:
    """Create an initialized options flow for direct step tests."""
    entry = SimpleNamespace(entry_id="entry-id", data=data)
    flow = ElehantWaterOptionsFlow()
    flow.hass = FakeHass(entry, coordinator)
    flow.handler = entry.entry_id
    return flow, entry


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
    assert len(single_channels) == 1
    assert single_channels[0][CONF_CHANNEL] == CHANNEL_VOLUME
    assert single_channels[0][CONF_LEGACY_ID] == "31560"
    assert single_channels[0]["name"] == "Single"
    assert single_channels[0][CONF_MEASUREMENT] == MEASUREMENT_CUBIC_METERS
    assert single_channels[0]["device_class"] == DEVICE_CLASS_WATER
    assert single_channels[0][CONF_STATE_CLASS] == STATE_CLASS_TOTAL_INCREASING
    assert single_channels[0][CONF_ENABLED] is True
    assert meters["31560"][CONF_LEGACY_METER_ID] == "31560"
    assert meters["31560"][CONF_AVAILABILITY_ENABLED] is True
    assert meters["31560"][CONF_AVAILABILITY_TIMEOUT_MINUTES] == 60

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
    assert (
        tariff_channels[CHANNEL_TEMPERATURE][CONF_STATE_CLASS]
        == STATE_CLASS_MEASUREMENT
    )


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
    invalid_volume_measurement = normalize_legacy_yaml_config(
        {"devices": [{"id": 31560, "name": "Single"}]}
    )[CONF_METERS]
    invalid_volume_measurement[0][CONF_CHANNELS][0][CONF_MEASUREMENT] = "bad"
    assert not validate_meters_config(invalid_volume_measurement)

    invalid_volume_device_class = normalize_legacy_yaml_config(
        {"devices": [{"id": 31560, "name": "Single"}]}
    )[CONF_METERS]
    invalid_volume_device_class[0][CONF_CHANNELS][0][CONF_DEVICE_CLASS] = "gas"
    assert not validate_meters_config(invalid_volume_device_class)


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


def test_add_manual_meter_options_flow_creates_normalized_meter() -> None:
    """Manual add flow creates a normal config entry without JSON editing."""
    flow, entry = make_options_flow({CONF_METERS: []})

    result = asyncio.run(
        flow.async_step_add_manual_meter(
            {
                CONF_METER_ID: "92728",
                "name": "Cold water",
                "volume_unit": MEASUREMENT_CUBIC_METERS,
                "temperature_enabled": True,
                "availability_enabled": True,
                "availability_timeout_minutes": 60,
            }
        )
    )

    assert result["type"] == "create_entry"
    meter = entry.data[CONF_METERS][0]
    assert meter[CONF_METER_ID] == "92728"
    assert meter[CONF_ID_SOURCE] == ID_SOURCE_MANUAL
    assert meter[CONF_AVAILABILITY_TIMEOUT_MINUTES] == 60
    channels = {channel[CONF_CHANNEL]: channel for channel in meter[CONF_CHANNELS]}
    assert set(channels) == {CHANNEL_VOLUME, CHANNEL_TEMPERATURE}
    assert CONF_LEGACY_ID not in channels[CHANNEL_VOLUME]


def test_add_manual_meter_options_flow_rejects_bad_or_duplicate_id() -> None:
    """Manual add flow validates meter identity before saving."""
    data = normalize_legacy_yaml_config({"devices": [{"id": 92728, "name": "Cold"}]})
    flow, _entry = make_options_flow(data)

    bad_id = asyncio.run(
        flow.async_step_add_manual_meter(
            {
                CONF_METER_ID: "bad",
                "name": "Cold water",
                "volume_unit": MEASUREMENT_CUBIC_METERS,
                "temperature_enabled": True,
                "availability_enabled": True,
                "availability_timeout_minutes": 60,
            }
        )
    )
    assert bad_id["type"] == "form"
    assert bad_id["errors"][CONF_METER_ID] == "invalid_meter_id"

    duplicate = asyncio.run(
        flow.async_step_add_manual_meter(
            {
                CONF_METER_ID: "92728",
                "name": "Cold water",
                "volume_unit": MEASUREMENT_CUBIC_METERS,
                "temperature_enabled": True,
                "availability_enabled": True,
                "availability_timeout_minutes": 60,
            }
        )
    )
    assert duplicate["type"] == "form"
    assert duplicate["errors"][CONF_METER_ID] == "meter_already_configured"


def test_discovery_options_flow_uses_recent_candidates() -> None:
    """Discovery flow offers and imports only coordinator-provided recent candidates."""
    candidate = SimpleNamespace(
        manufacturer_meter_id="92728",
        address_meter_id="92728",
        temperature_observed=True,
    )
    flow, entry = make_options_flow(
        {CONF_METERS: []},
        FakeDiscoveryCoordinator({"92728": candidate}),
    )

    select = asyncio.run(flow.async_step_discover_meters())
    assert select["type"] == "form"

    add_form = asyncio.run(
        flow.async_step_discover_meters({"candidate_meter_id": "92728"})
    )
    assert add_form["type"] == "form"

    result = asyncio.run(
        flow.async_step_add_discovered_meter(
            {
                "name": "Cold water",
                "volume_unit": MEASUREMENT_CUBIC_METERS,
                "temperature_enabled": True,
                "availability_enabled": True,
                "availability_timeout_minutes": 60,
            }
        )
    )

    assert result["type"] == "create_entry"
    meter = entry.data[CONF_METERS][0]
    assert meter[CONF_METER_ID] == "92728"
    assert meter[CONF_ID_SOURCE] == ID_SOURCE_DISCOVERY
    assert meter[CONF_IDENTITY_EVIDENCE] == {
        "manufacturer_meter_id": "92728",
        "address_meter_id": "92728",
    }


def test_discovery_options_flow_aborts_without_recent_candidates() -> None:
    """Stale or absent discovery candidates are not offered."""
    flow, _entry = make_options_flow(
        {CONF_METERS: []},
        FakeDiscoveryCoordinator({}),
    )

    result = asyncio.run(flow.async_step_discover_meters())

    assert result["type"] == "abort"
    assert result["reason"] == "no_discovered_meters"
