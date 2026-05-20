"""Tests for Elehant repair issue helpers."""

from __future__ import annotations

from custom_components.elehant_water.const import (
    CHANNEL_VOLUME,
    CONF_CHANNEL,
    CONF_CHANNELS,
    CONF_METERS,
    CONF_METER_ID,
)
from custom_components.elehant_water.repairs import (
    ISSUE_DUPLICATE_METER_IDS,
    ISSUE_MALFORMED_CONFIG,
    ISSUE_METER_NEVER_SEEN_PREFIX,
    async_update_config_repair_issues,
    async_update_never_seen_repair_issues,
)


class FakeIssueRegistry:
    """Capture repair issue registry calls."""

    def __init__(self) -> None:
        self.created: list[tuple[str, str]] = []
        self.deleted: list[tuple[str, str]] = []
        self.issues: dict[tuple[str, str], object] = {}

    def async_create_issue(self, hass, domain, issue_id, **kwargs) -> None:
        """Capture issue creation."""
        self.created.append((domain, issue_id))

    def async_delete_issue(self, hass, domain, issue_id) -> None:
        """Capture issue deletion."""
        self.deleted.append((domain, issue_id))


def test_config_repair_issues_cover_malformed_and_duplicate_config(monkeypatch) -> None:
    """Static repair helpers create issues for malformed and duplicate configs."""
    registry = FakeIssueRegistry()
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.ir.async_create_issue",
        registry.async_create_issue,
    )
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.ir.async_delete_issue",
        registry.async_delete_issue,
    )
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.ir.async_get",
        lambda hass: registry,
    )

    async_update_config_repair_issues(
        object(),
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: "92728",
                    CONF_CHANNELS: [{CONF_CHANNEL: CHANNEL_VOLUME, "name": "A"}],
                },
                {
                    CONF_METER_ID: "92728",
                    CONF_CHANNELS: [{CONF_CHANNEL: CHANNEL_VOLUME, "name": "B"}],
                },
            ]
        },
    )
    async_update_config_repair_issues(object(), {CONF_METERS: [{CONF_METER_ID: "bad"}]})

    assert ("elehant_water", ISSUE_DUPLICATE_METER_IDS) in registry.created
    assert ("elehant_water", ISSUE_MALFORMED_CONFIG) in registry.created


def test_never_seen_repair_issue_tracks_unseen_meters(monkeypatch) -> None:
    """Runtime repair helper creates and clears never-seen meter issues."""
    registry = FakeIssueRegistry()
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.ir.async_create_issue",
        registry.async_create_issue,
    )
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.ir.async_delete_issue",
        registry.async_delete_issue,
    )
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.ir.async_get",
        lambda hass: registry,
    )
    config = {
        CONF_METERS: [
            {
                CONF_METER_ID: "92728",
                CONF_CHANNELS: [{CONF_CHANNEL: CHANNEL_VOLUME, "name": "Water"}],
            }
        ]
    }

    async_update_never_seen_repair_issues(object(), config, set())
    async_update_never_seen_repair_issues(
        object(),
        config,
        {("92728", CHANNEL_VOLUME)},
    )

    issue_id = f"{ISSUE_METER_NEVER_SEEN_PREFIX}_92728"
    assert ("elehant_water", issue_id) in registry.created
    assert ("elehant_water", issue_id) in registry.deleted


def test_never_seen_repair_issue_deletes_removed_meter_issues(monkeypatch) -> None:
    """Runtime repair helper removes stale never-seen issues for deleted meters."""
    registry = FakeIssueRegistry()
    stale_issue_id = f"{ISSUE_METER_NEVER_SEEN_PREFIX}_12345"
    current_issue_id = f"{ISSUE_METER_NEVER_SEEN_PREFIX}_92728"
    registry.issues = {
        ("elehant_water", stale_issue_id): object(),
        ("elehant_water", current_issue_id): object(),
        ("elehant_water", ISSUE_MALFORMED_CONFIG): object(),
        ("other_domain", f"{ISSUE_METER_NEVER_SEEN_PREFIX}_99999"): object(),
    }
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.ir.async_create_issue",
        registry.async_create_issue,
    )
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.ir.async_delete_issue",
        registry.async_delete_issue,
    )
    monkeypatch.setattr(
        "custom_components.elehant_water.repairs.ir.async_get",
        lambda hass: registry,
    )

    async_update_never_seen_repair_issues(
        object(),
        {
            CONF_METERS: [
                {
                    CONF_METER_ID: "92728",
                    CONF_CHANNELS: [{CONF_CHANNEL: CHANNEL_VOLUME, "name": "Water"}],
                }
            ]
        },
        set(),
    )

    assert ("elehant_water", stale_issue_id) in registry.deleted
    assert ("elehant_water", ISSUE_MALFORMED_CONFIG) not in registry.deleted
    assert (
        "other_domain",
        f"{ISSUE_METER_NEVER_SEEN_PREFIX}_99999",
    ) not in registry.deleted
