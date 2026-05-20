"""Elehant water meter integration."""

from __future__ import annotations

import logging
from typing import Any

from .const import (
    DATA_LEGACY_YAML_CONFIG,
    DEFAULT_NEVER_SEEN_REPAIR_GRACE_SECONDS,
    DOMAIN,
)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: Any, config: dict) -> bool:
    """Set up the integration."""
    hass.data.setdefault(DOMAIN, {})
    if legacy_config := _extract_legacy_yaml_config(config):
        hass.data[DOMAIN][DATA_LEGACY_YAML_CONFIG] = legacy_config
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=legacy_config,
        )
    return True


def _extract_legacy_yaml_config(config: dict[str, Any]) -> dict[str, Any] | None:
    """Extract legacy sensor platform config from full Home Assistant config."""
    sensor_config = config.get("sensor")
    if not isinstance(sensor_config, list):
        return None
    for platform_config in sensor_config:
        if not isinstance(platform_config, dict):
            continue
        if platform_config.get("platform") == DOMAIN:
            return dict(platform_config)
    return None


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up Elehant Water from a config entry."""
    from homeassistant.components import bluetooth
    from homeassistant.const import Platform
    from homeassistant.core import callback
    from homeassistant.exceptions import ConfigEntryNotReady
    from homeassistant.helpers.event import async_call_later

    from .config_flow import ElehantWaterConfigFlow
    from .config_schema import normalize_config_entry_data
    from .coordinator import ElehantWaterCoordinator
    from .repairs import (
        async_create_no_bluetooth_scanner_issue,
        async_delete_no_bluetooth_scanner_issue,
        async_update_config_repair_issues,
    )

    hass.data.setdefault(DOMAIN, {})

    try:
        normalized_data = normalize_config_entry_data(dict(entry.data))
    except (TypeError, ValueError) as err:
        async_update_config_repair_issues(hass, dict(entry.data))
        _LOGGER.error("Invalid Elehant Water config entry: %s", err)
        return False
    if normalized_data != entry.data or entry.version != ElehantWaterConfigFlow.VERSION:
        hass.config_entries.async_update_entry(
            entry,
            data=normalized_data,
            version=ElehantWaterConfigFlow.VERSION,
        )

    if bluetooth.async_scanner_count(hass, connectable=False) == 0:
        async_create_no_bluetooth_scanner_issue(hass)
        raise ConfigEntryNotReady("No Home Assistant Bluetooth scanners available")
    async_delete_no_bluetooth_scanner_issue(hass)

    coordinator = ElehantWaterCoordinator(hass, normalized_data)
    async_update_config_repair_issues(hass, normalized_data)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.async_on_unload(coordinator.async_shutdown)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(
        async_call_later(
            hass,
            DEFAULT_NEVER_SEEN_REPAIR_GRACE_SECONDS,
            lambda now: coordinator.async_update_repair_issues(),
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])

    @callback
    def _async_bluetooth_callback(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth advertisement."""
        coordinator.async_handle_bluetooth_service_info(service_info, change)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_bluetooth_callback,
            {"connectable": False},
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )
    return True


async def _async_update_listener(hass: Any, entry: Any) -> None:
    """Reload the entry when options or data are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Unload an Elehant Water config entry."""
    from homeassistant.const import Platform

    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_migrate_entry(hass: Any, entry: Any) -> bool:
    """Migrate an Elehant Water config entry."""
    from .config_flow import ElehantWaterConfigFlow
    from .config_schema import normalize_config_entry_data

    hass.config_entries.async_update_entry(
        entry,
        data=normalize_config_entry_data(dict(entry.data)),
        version=ElehantWaterConfigFlow.VERSION,
    )
    return True
