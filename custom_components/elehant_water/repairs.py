"""Repair issue helpers for Elehant Water."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .config_schema import duplicate_meter_ids, validate_meters_config
from .const import (
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_METERS,
    CONF_METER_ID,
    DOMAIN,
)

ISSUE_NO_BLUETOOTH_SCANNER = "no_bluetooth_scanner"
ISSUE_MALFORMED_CONFIG = "malformed_config"
ISSUE_DUPLICATE_METER_IDS = "duplicate_meter_ids"
ISSUE_METER_NEVER_SEEN_PREFIX = "meter_never_seen"


def async_create_no_bluetooth_scanner_issue(hass: HomeAssistant) -> None:
    """Create a repair issue for missing Bluetooth scanners."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_NO_BLUETOOTH_SCANNER,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_NO_BLUETOOTH_SCANNER,
    )


def async_delete_no_bluetooth_scanner_issue(hass: HomeAssistant) -> None:
    """Delete the missing Bluetooth scanner repair issue."""
    ir.async_delete_issue(hass, DOMAIN, ISSUE_NO_BLUETOOTH_SCANNER)


def async_update_config_repair_issues(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> None:
    """Update repair issues for static config-entry problems."""
    meters = config.get(CONF_METERS, [])
    if not validate_meters_config(meters):
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_MALFORMED_CONFIG,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_MALFORMED_CONFIG,
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_MALFORMED_CONFIG)

    duplicates = duplicate_meter_ids(meters if isinstance(meters, list) else [])
    if duplicates:
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_DUPLICATE_METER_IDS,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_DUPLICATE_METER_IDS,
            translation_placeholders={"meter_ids": ", ".join(duplicates)},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_DUPLICATE_METER_IDS)


def async_update_never_seen_repair_issues(
    hass: HomeAssistant,
    config: dict[str, Any],
    seen_keys: set[tuple[str, str]],
) -> None:
    """Update repair issues for configured meters that have not been seen."""
    current_meter_ids = {
        str(meter[CONF_METER_ID])
        for meter in config.get(CONF_METERS, [])
        if isinstance(meter, dict) and CONF_METER_ID in meter
    }
    _async_delete_stale_never_seen_issues(hass, current_meter_ids)

    for meter in config.get(CONF_METERS, []):
        meter_id = str(meter[CONF_METER_ID])
        channel_names = {
            str(channel[CONF_CHANNEL])
            for channel in meter.get(CONF_CHANNELS, [])
            if CONF_CHANNEL in channel
        }
        if channel_names and all(
            (meter_id, channel_name) not in seen_keys for channel_name in channel_names
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"{ISSUE_METER_NEVER_SEEN_PREFIX}_{meter_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_METER_NEVER_SEEN_PREFIX,
                translation_placeholders={"meter_id": meter_id},
            )
        else:
            ir.async_delete_issue(
                hass,
                DOMAIN,
                f"{ISSUE_METER_NEVER_SEEN_PREFIX}_{meter_id}",
            )


def _async_delete_stale_never_seen_issues(
    hass: HomeAssistant,
    current_meter_ids: set[str],
) -> None:
    """Delete never-seen issues for meters no longer present in config."""
    issue_registry = ir.async_get(hass)
    prefix = f"{ISSUE_METER_NEVER_SEEN_PREFIX}_"
    stale_issue_ids = [
        issue_id
        for domain, issue_id in issue_registry.issues
        if domain == DOMAIN
        and issue_id.startswith(prefix)
        and issue_id.removeprefix(prefix) not in current_meter_ids
    ]
    for issue_id in stale_issue_ids:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
