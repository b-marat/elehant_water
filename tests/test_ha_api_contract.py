"""Smoke tests for the Home Assistant APIs used by the integration."""

from __future__ import annotations

import importlib.metadata

from homeassistant.components import bluetooth


def test_homeassistant_version_contract() -> None:
    """The test environment uses the selected Home Assistant line."""
    assert importlib.metadata.version("homeassistant").startswith("2026.5.")


def test_bluetooth_api_contract() -> None:
    """The selected Bluetooth API is present in Home Assistant."""
    assert hasattr(bluetooth, "async_register_callback")
    assert hasattr(bluetooth, "async_scanner_count")
    assert hasattr(bluetooth, "BluetoothScanningMode")
    assert bluetooth.BluetoothScanningMode.PASSIVE
