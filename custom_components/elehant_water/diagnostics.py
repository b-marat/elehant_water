"""Diagnostics support for Elehant Water."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    return {
        "entry": {
            "version": entry.version,
            "minor_version": entry.minor_version,
            "data": entry.data,
        },
        "runtime": coordinator.diagnostics() if coordinator is not None else None,
    }
