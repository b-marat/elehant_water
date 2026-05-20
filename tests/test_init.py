"""Tests for Elehant integration setup helpers."""

from __future__ import annotations

import asyncio

from custom_components.elehant_water import async_setup_entry
from custom_components.elehant_water.const import (
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_METERS,
    CONF_METER_ID,
    DATA_LEGACY_YAML_CONFIG,
    DEFAULT_NEVER_SEEN_REPAIR_GRACE_SECONDS,
    DOMAIN,
)


class FakeConfigEntries:
    """Small config entries facade for setup tests."""

    def __init__(self) -> None:
        self.updated: list[tuple[object, dict[str, object]]] = []

    def async_update_entry(self, entry, **kwargs) -> None:
        """Capture config entry updates."""
        self.updated.append((entry, kwargs))

    async def async_forward_entry_setups(self, entry, platforms) -> None:
        """Pretend platform setup succeeded."""


class FakeHass:
    """Small hass fake for setup tests."""

    def __init__(self) -> None:
        self.config_entries = FakeConfigEntries()
        self.data = {DOMAIN: {DATA_LEGACY_YAML_CONFIG: {}}}


class FakeEntry:
    """Small config entry fake for setup tests."""

    entry_id = "entry-1"
    version = 1

    def __init__(self, data: dict[str, object]) -> None:
        self.data = data
        self.unload_callbacks: list[object] = []

    def add_update_listener(self, listener):
        """Return a fake listener unsubscribe callback."""
        return lambda: None

    def async_on_unload(self, callback) -> None:
        """Capture unload callbacks."""
        self.unload_callbacks.append(callback)


def test_setup_entry_schedules_never_seen_repair_check(monkeypatch) -> None:
    """Entry setup schedules a delayed never-seen repair update."""
    scheduled: dict[str, object] = {}
    repair_updates: list[object] = []

    def fake_async_call_later(hass, delay, action):
        scheduled["hass"] = hass
        scheduled["delay"] = delay
        scheduled["action"] = action
        return lambda: None

    monkeypatch.setattr(
        "homeassistant.components.bluetooth.async_scanner_count",
        lambda hass, connectable=False: 1,
    )
    monkeypatch.setattr(
        "homeassistant.components.bluetooth.async_register_callback",
        lambda *args, **kwargs: lambda: None,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.event.async_call_later",
        fake_async_call_later,
    )
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.async_delete_no_bluetooth_scanner_issue",
        lambda hass: None,
    )
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.async_update_config_repair_issues",
        lambda hass, config: None,
    )
    monkeypatch.setattr(
        "custom_components.elehant_water.coordinator.ElehantWaterCoordinator.async_update_repair_issues",
        lambda self: repair_updates.append(self),
    )

    hass = FakeHass()
    entry = FakeEntry(
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: "92728",
                    CONF_CHANNELS: [{CONF_CHANNEL: "volume", "name": "Water"}],
                }
            ]
        }
    )

    assert asyncio.run(async_setup_entry(hass, entry))

    assert scheduled["hass"] is hass
    assert scheduled["delay"] == DEFAULT_NEVER_SEEN_REPAIR_GRACE_SECONDS
    assert scheduled["action"] is not None
    assert scheduled["action"](None) is None
    assert repair_updates == [hass.data[DOMAIN][entry.entry_id]]
    assert len(entry.unload_callbacks) == 4
