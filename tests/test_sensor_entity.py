"""Tests for Elehant sensor entity behavior."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfTemperature, UnitOfVolume

from custom_components.elehant_water.const import (
    CHANNEL_TEMPERATURE,
    CHANNEL_VOLUME,
    CONF_CHANNEL,
    CONF_DEVICE_CLASS,
    CONF_LEGACY_ID,
    CONF_MEASUREMENT,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_WATER,
    MEASUREMENT_CELSIUS,
    MEASUREMENT_CUBIC_METERS,
)
from custom_components.elehant_water.sensor import ElehantSensor


class FakeCoordinator:
    """Small coordinator fake for entity tests."""

    def __init__(self, state: object) -> None:
        self.state = state

    def get_state(self, meter_id: str, channel: str) -> object:
        """Return stored state."""
        return self.state


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
        },
    )

    assert sensor.unique_id == "elehant_27192"
    assert sensor.name == "Water"
    assert sensor.device_class is SensorDeviceClass.WATER
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
        },
    )

    assert sensor.unique_id == "elehant_temp_31562"
    assert sensor.device_class is SensorDeviceClass.TEMPERATURE
    assert sensor.native_unit_of_measurement is UnitOfTemperature.CELSIUS
    assert sensor.native_value == 16.06
