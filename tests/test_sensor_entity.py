"""Tests for Elehant sensor entity behavior."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfVolume

from custom_components.elehant_water.const import (
    CHANNEL_TARIFF_1,
    CHANNEL_TARIFF_2,
    CHANNEL_TEMPERATURE,
    CHANNEL_TOTAL,
    CHANNEL_VOLUME,
    CONF_CHANNEL,
    CONF_DEVICE_CLASS,
    CONF_LEGACY_ID,
    CONF_MEASUREMENT,
    DIAGNOSTIC_LAST_SEEN,
    DIAGNOSTIC_MATCHED_BY,
    DIAGNOSTIC_PACKET_COUNT,
    DIAGNOSTIC_RSSI,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_WATER,
    MATCHED_BY_ADDRESS,
    MATCHED_BY_ALIAS,
    MATCHED_BY_CONFIGURED,
    MATCHED_BY_MANUFACTURER,
    MEASUREMENT_CELSIUS,
    MEASUREMENT_CUBIC_METERS,
    CONF_STATE_CLASS,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from custom_components.elehant_water.sensor import ElehantDiagnosticSensor, ElehantSensor


class FakeCoordinator:
    """Small coordinator fake for entity tests."""

    def __init__(self, state: object | dict[str, object]) -> None:
        self.state = state

    def get_state(self, meter_id: str, channel: str) -> object:
        """Return stored state."""
        if isinstance(self.state, dict):
            return self.state.get(channel)
        return self.state

    def is_available(self, meter_id: str, channel: str) -> bool:
        """Return availability."""
        return True


def test_volume_sensor_legacy_identity_and_value() -> None:
    """Volume sensors preserve legacy unique IDs and conversion behavior."""
    sensor = ElehantSensor(
        FakeCoordinator(SimpleNamespace(raw_count=3791455)),
        "27192",
        {
            CONF_CHANNEL: CHANNEL_VOLUME,
            CONF_LEGACY_ID: "27192",
            "name": "Water",
            CONF_MEASUREMENT: MEASUREMENT_CUBIC_METERS,
            CONF_DEVICE_CLASS: DEVICE_CLASS_WATER,
            CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
        },
    )

    assert sensor.unique_id == "elehant_27192"
    assert sensor.name == "Water"
    assert sensor.device_class is SensorDeviceClass.WATER
    assert sensor.state_class is SensorStateClass.TOTAL_INCREASING
    assert sensor.available
    assert sensor.native_unit_of_measurement is UnitOfVolume.CUBIC_METERS
    assert sensor.native_value == 379.1455


def test_temperature_sensor_legacy_identity_and_value() -> None:
    """Temperature sensors preserve legacy unique IDs."""
    sensor = ElehantSensor(
        FakeCoordinator(SimpleNamespace(temperature_celsius=16.06)),
        "31562",
        {
            CONF_CHANNEL: CHANNEL_TEMPERATURE,
            CONF_LEGACY_ID: "31562",
            "name": "Temperature",
            CONF_MEASUREMENT: MEASUREMENT_CELSIUS,
            CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            CONF_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        },
    )

    assert sensor.unique_id == "elehant_temp_31562"
    assert sensor.device_class is SensorDeviceClass.TEMPERATURE
    assert sensor.state_class is SensorStateClass.MEASUREMENT
    assert sensor.native_unit_of_measurement is UnitOfTemperature.CELSIUS
    assert sensor.native_value == 16.06


def test_new_sensor_identity_uses_canonical_meter_and_channel() -> None:
    """New non-migrated sensors derive unique IDs from canonical meter identity."""
    sensor = ElehantSensor(
        FakeCoordinator(SimpleNamespace(raw_count=1000)),
        "92728",
        {
            CONF_CHANNEL: CHANNEL_VOLUME,
            "name": "Water",
            CONF_MEASUREMENT: MEASUREMENT_CUBIC_METERS,
            CONF_DEVICE_CLASS: DEVICE_CLASS_WATER,
            CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
        },
    )

    assert sensor.unique_id == "elehant_92728_volume"


def test_synthetic_total_sensor_sums_two_tariff_channels() -> None:
    """Synthetic total sensors sum tariff channels without legacy identity churn."""
    sensor = ElehantSensor(
        FakeCoordinator(
            {
                CHANNEL_TARIFF_1: SimpleNamespace(raw_count=1000),
                CHANNEL_TARIFF_2: SimpleNamespace(raw_count=2500),
            }
        ),
        "92728",
        {
            CONF_CHANNEL: CHANNEL_TOTAL,
            "name": "Water total",
            CONF_MEASUREMENT: MEASUREMENT_CUBIC_METERS,
            CONF_DEVICE_CLASS: DEVICE_CLASS_WATER,
            CONF_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
            "_enabled_default": False,
        },
    )

    assert sensor.unique_id == "elehant_92728_total"
    assert sensor.entity_registry_enabled_default is False
    assert sensor.state_class is SensorStateClass.TOTAL_INCREASING
    assert sensor.native_unit_of_measurement is UnitOfVolume.CUBIC_METERS
    assert sensor.native_value == 0.35


def test_diagnostic_sensors_are_disabled_by_default_and_report_runtime_state() -> None:
    """Diagnostic sensors expose runtime metadata without cluttering default UI."""
    state = SimpleNamespace(
        last_seen=1700000000.0,
        rssi=-72,
        packet_count=3,
        matched_by="manufacturer",
    )

    last_seen = ElehantDiagnosticSensor(
        FakeCoordinator(state),
        "92728",
        {CONF_CHANNEL: CHANNEL_VOLUME, "name": "Water"},
        DIAGNOSTIC_LAST_SEEN,
    )
    rssi = ElehantDiagnosticSensor(
        FakeCoordinator(state),
        "92728",
        {CONF_CHANNEL: CHANNEL_VOLUME, "name": "Water"},
        DIAGNOSTIC_RSSI,
    )
    packet_count = ElehantDiagnosticSensor(
        FakeCoordinator(state),
        "92728",
        {CONF_CHANNEL: CHANNEL_VOLUME, "name": "Water"},
        DIAGNOSTIC_PACKET_COUNT,
    )
    matched_by = ElehantDiagnosticSensor(
        FakeCoordinator(state),
        "92728",
        {CONF_CHANNEL: CHANNEL_VOLUME, "name": "Water"},
        DIAGNOSTIC_MATCHED_BY,
    )

    assert last_seen.entity_category is EntityCategory.DIAGNOSTIC
    assert last_seen.entity_registry_enabled_default is False
    assert last_seen.device_class is SensorDeviceClass.TIMESTAMP
    assert last_seen.native_value.isoformat() == "2023-11-14T22:13:20+00:00"
    assert rssi.device_class is SensorDeviceClass.SIGNAL_STRENGTH
    assert rssi.native_value == -72
    assert packet_count.native_value == 3
    assert matched_by.device_class is SensorDeviceClass.ENUM
    assert matched_by.options == [
        MATCHED_BY_MANUFACTURER,
        MATCHED_BY_ADDRESS,
        MATCHED_BY_ALIAS,
        MATCHED_BY_CONFIGURED,
    ]
    assert matched_by.native_value == "manufacturer"
