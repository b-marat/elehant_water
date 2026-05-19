"""Tests for Elehant integration setup helpers."""

from __future__ import annotations

from custom_components.elehant_water import _extract_legacy_yaml_config


def test_extract_legacy_yaml_config() -> None:
    """Legacy sensor platform config is extracted from full HA config."""
    config = {
        "sensor": [
            {"platform": "other", "name": "Other"},
            {
                "platform": "elehant_water",
                "measurement_water": "m3",
                "devices": [{"id": 18674, "name": "Hot water"}],
            },
        ]
    }

    legacy_config = _extract_legacy_yaml_config(config)

    assert legacy_config == config["sensor"][1]
    assert legacy_config is not config["sensor"][1]


def test_extract_legacy_yaml_config_returns_none_without_platform() -> None:
    """Missing or malformed sensor config is ignored."""
    assert _extract_legacy_yaml_config({}) is None
    assert _extract_legacy_yaml_config({"sensor": {"platform": "elehant_water"}}) is None
    assert _extract_legacy_yaml_config({"sensor": [{"platform": "other"}]}) is None
