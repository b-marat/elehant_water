# Functional Improvements Backlog

## Purpose

This backlog describes follow-up work after the compatibility refactor. The current integration is working on Home Assistant `2026.5.x`, imports legacy YAML, receives real BLE advertisements, and preserves legacy entity IDs. Future work should improve usability, diagnostics, discovery, and long-term maintainability without breaking migrated installations.

## Current Baseline

Implemented and verified:

- Home Assistant config entry lifecycle.
- Legacy YAML import from the original integration format.
- Extended YAML import from a later abandoned fork:
  - `measurement_water`;
  - `measurement_gas`;
  - `type`;
  - `water_type`.
- Home Assistant Bluetooth callback runtime.
- Single-tariff volume readings from real BLE advertisements.
- Temperature extraction from single-tariff packets when temperature bytes are present.
- Compatibility with the canonical Elehant 24-bit meter identity:
  - `manufacturer_meter_id`: 3-byte device number from manufacturer payload;
  - `address_meter_id`: the same 3-byte device number parsed from the final BLE address bytes;
  - legacy 2-byte-looking IDs are treated as the same 24-bit identity with leading zero bytes omitted.
- Basic diagnostics for configured channels, latest readings, RSSI, `last_seen`, and unknown parsed IDs.
- Temporary options UI for importing YAML and editing normalized JSON.

Known constraints:

- Real two-tariff BLE samples are still unavailable.
- Real non-water Elehant samples are unavailable.
- Strict manufacturer-specific discovery signatures are not documented.
- The current options UI is serviceable but not suitable as the long-term user interface.
- Diagnostics currently expose useful debug data. Redaction is optional, not a hard architectural requirement.

## Backlog Principles

- Preserve legacy primary entity `unique_id` values by default.
- Do not rewrite entity registry IDs automatically.
- Do not create duplicate primary sensors by default.
- Prefer UI changes that are reversible and visible to the user.
- Treat YAML as migration input only, not as a long-term configuration source.
- Avoid claiming support for untested meter types.
- Keep packet parsing deterministic and covered by tests.
- Prefer conservative packet validation until more real samples exist.

## Decision Register

### D1. Canonical Meter Identity

Problem: old integrations and forks may have stored the same Elehant serial as a shorter decimal value when the leading byte was zero, while real Elehant packets use a 24-bit device number.

Research result:

- Public project `vooon/elehant-to-mqtt` documents Elehant SVD-15/SVT-15 packets with a 24-bit device number stored in manufacturer data and matching the final three bytes of the BLE address.
- The same project includes ESPHome code that derives the serial number from the lower 24 bits of the BLE address and compares it to the 24-bit number in manufacturer data.
- Its protocol notes also list gas-meter address prefixes and use the same 24-bit device-number concept for those samples.
- The user's low-number meter also fits this model: small serials are valid 24-bit values represented with leading zero bytes, so no separate 16-bit number exists.
- Sources:
  - https://github.com/vooon/elehant-to-mqtt/blob/master/docs/protocol.md
  - https://github.com/vooon/elehant-to-mqtt/blob/master/esphome/elehant_ble.h
  - https://github.com/vooon/elehant-to-mqtt/blob/master/src/ble.cpp

Options:

- Option A: use the 24-bit Elehant serial number as the canonical meter identity everywhere, normalizing shorter imported values by adding leading zero bytes where needed, while preserving legacy channel `unique_id` values.
- Option B: keep imported/configured IDs as canonical forever and store the 24-bit number only as an alias.
- Option C: keep shorter imported decimal values as-is.

Recommendation: Option A.

Reasoning:

- Public evidence and observed devices point to one real identity scheme: the 24-bit Elehant serial number.
- The old 2-byte-looking value is the same 24-bit identity with leading zero bytes omitted, not a separate 16-bit identifier.
- Compatibility still matters at the entity layer: existing Home Assistant `entity_id`, primary `unique_id`, automations, dashboards, and recorder history must not be rewritten automatically.

Required implementation:

- Add explicit `meter_id`, `id_source`, and `identity_evidence` fields to normalized meter config.
- Store `meter_id` as the canonical 24-bit Elehant serial number.
- Normalize shorter imported values to the same 24-bit value by left-padding the byte representation with zeroes.
- Keep `legacy_id` on every channel for primary unique ID compatibility.
- Keep the originally imported text/number only in channel `legacy_id` or migration metadata when needed to preserve entity unique IDs.
- Store the ID source in diagnostics:
  - `configured_id`;
  - `address_meter_id`;
  - `manufacturer_meter_id`;
  - `matched_by`.
- In discovery, show the 24-bit serial number as the meter ID.
- Do not expose a 16-bit ID concept in the UI; show only the canonical 24-bit serial number.
- Add a migration action that can normalize existing config entries to the 24-bit identity without changing primary entity `unique_id` values.

Status: accepted. Use the 24-bit Elehant serial as the canonical meter identity; shorter imported values are the same identity with leading zero bytes omitted. Ready for identity-model implementation.

### D2. Long-Term Configuration UI

Options:

- Option A: build a full form-based options flow with one meter edited per step.
- Option B: keep JSON editing and add only validation/help text.
- Option C: use discovery as the primary UI and keep manual JSON as an advanced fallback.

Recommendation: hybrid of A and C.

Required implementation:

- Use discovery for adding newly seen meters.
- Use form-based options for editing existing meters.
- Keep normalized JSON only as an advanced troubleshooting fallback.

Status: accepted. Ready for UI implementation after D1 data model work.

### D3. Availability Behavior

Options:

- Option A: keep legacy behavior forever: sensors stay `unknown` until first value and keep last value after that.
- Option B: add optional availability timeout, disabled by default.
- Option C: enable availability timeout by default.

Recommendation: Option C with a conservative default timeout.

Reasoning:

- The option must remain configurable because BLE advertisements can be sparse.
- The default should still expose real operational problems: if no packet is received for more than one hour, the meter is stale enough to be shown as unavailable.
- Users who prefer legacy "keep last value forever" behavior can disable the timeout.
- Use Home Assistant's standard entity availability mechanics instead of inventing a separate unavailable sensor model.

Accepted default behavior:

- Availability timeout is stored explicitly in imported config entries during YAML migration.
- YAML migration default timeout: 60 minutes.
- Discovery flow proposes the same default timeout for newly added meters.
- Manual UI creation proposes the same default timeout.
- First-start behavior: a channel that has never been seen in the current runtime remains `unknown`; once seen, Home Assistant availability becomes false after `last_seen + timeout`.

Status: accepted. Ready for availability implementation.

### D4. Long-Term Statistics

Options:

- Option A: keep `state_class` disabled.
- Option B: add `state_class` as opt-in per volume channel.
- Option C: enable `total_increasing` by default for volume channels.

Recommendation: Option C for migrated and newly created channels.

Current HA observation:

- Live HA recorder metadata was inspected on `2026-05-19`.
- Current Elehant entity states do not expose `state_class` yet.
- Recorder already contains statistic IDs for the migrated entities:
  - volume sensors have `has_sum=true`, `unit_class=volume`, `statistics_unit_of_measurement=m3`;
  - temperature sensors have `has_mean=true`, `unit_class=temperature`, `statistics_unit_of_measurement=celsius`.

Proposed state classes:

- Volume channels: `total_increasing`.
- Temperature channels: `measurement`.

Reasoning:

- Volume readings are cumulative meter readings, not interval usage.
- Temperature is an instantaneous measurement.
- The proposed classes match existing recorder metadata shape and should preserve the already gathered statistics for the same entity IDs.
- Existing entity IDs and unique IDs must not change; only entity metadata should be added.

Status: accepted. Ready for statistics metadata implementation.

### D5. Diagnostics Detail

Decision: detailed diagnostics are the baseline.

Reasoning:

- Meter IDs, channel names, RSSI, and packet metadata are useful for field debugging.
- The project does not currently handle credentials, tokens, or other high-risk secrets in diagnostics.
- Redaction can be added later if real support cases show a privacy need.

Status: accepted. Keep diagnostics detailed by default.

## Implementation Contracts

These contracts make the backlog directly implementable. If implementation needs to diverge, update this section before changing code.

### Normalized Config Shape

Meter object:

- `meter_id`: required string; canonical Elehant serial number as decimal text, range `0..16777215`.
- `id_source`: required string enum:
  - `yaml`;
  - `manual`;
  - `discovery`;
  - `manufacturer`;
  - `address`;
  - `manufacturer_or_address`.
- `identity_evidence`: optional object for diagnostics and discovery confidence:
  - `manufacturer_meter_id`: optional decimal string;
  - `address_meter_id`: optional decimal string;
  - `matched_by`: optional string enum `manufacturer`, `address`, `both`, `configured`.
- `legacy_meter_id`: optional string; original imported meter ID text/number, used only for migration/debugging.
- `availability_enabled`: required boolean; default `true`.
- `availability_timeout_minutes`: required positive integer; default `60`.
- `channels`: required non-empty list of channel objects.

Channel object:

- `channel_id`: required stable string, unique inside the meter.
- `legacy_id`: optional string; source for preserving migrated entity unique IDs.
- `name`: required string.
- `measurement`: required unit string in the current implementation:
  - volume channels: `m3` or `l`;
  - temperature channels: `celsius`.
  - Historical note: earlier drafts used `measurement` for measurement kind and `unit` for display unit. The current release intentionally keeps the legacy-compatible field name `measurement` as the unit field to avoid an extra config migration during this release.
- `device_class`: required string:
  - volume channels currently use `water`;
  - temperature channels use `temperature`;
  - future non-water meters must not be claimed until samples exist.
- `measurement_kind`: not stored in the current release; it is derived from `channel_id` and `device_class`.
- `state_class`: required string:
  - volume: `total_increasing`;
  - temperature: `measurement`.
- `enabled`: optional boolean; default `true`.
- `water_type`: optional string; imported metadata such as `hot` or `cold`.

YAML migration defaults:

- If YAML has no availability settings, set `availability_enabled=true` and `availability_timeout_minutes=60`.
- Preserve imported display names and channel IDs where possible.
- Preserve channel-level `legacy_id` for every migrated entity.
- Normalize imported meter IDs to canonical decimal `meter_id`.

Discovery/manual creation defaults:

- `availability_enabled=true`.
- `availability_timeout_minutes=60`.
- Volume unit default: `m3`.
- Temperature unit default: `celsius`.
- Temperature channel is offered when the parser has seen temperature data for the candidate.

### Meter ID Normalization

- Internally, meter IDs are integers in range `0..0xFFFFFF`.
- Config stores meter IDs as decimal strings without leading zeroes.
- BLE address identity is parsed from the final three address bytes as a 24-bit big-endian integer.
- Manufacturer-data identity is parsed from the documented 24-bit little-endian field and converted to the same integer.
- Imported shorter decimal IDs are parsed as integers and accepted if they fit `0..0xFFFFFF`; conceptually they are the same 24-bit ID with leading zero bytes omitted.
- Do not introduce a separate 16-bit ID type.
- If address-derived and manufacturer-derived IDs both exist and differ, do not auto-discover the packet as a normal candidate; record it in diagnostics/parser statistics as an identity mismatch.

### Entity Unique ID Rules

- Existing migrated entity unique IDs must remain stable.
- For migrated channels with `legacy_id`, the primary entity unique ID uses `legacy_id` exactly as the compatibility refactor currently does.
- For new discovery/manual channels without `legacy_id`, the unique ID is derived from canonical `meter_id` and `channel_id`.
- Meter-level `legacy_meter_id` must never be used as the channel unique ID source.
- Config migration may change internal `meter_id`, but must not rewrite HA entity registry IDs automatically.

### Discovery Candidate Rules

- Candidate key: canonical 24-bit `meter_id`.
- Deduplicate candidates against configured canonical meter IDs.
- Expire candidates that have not been seen for a bounded time; implementation should choose a practical default and test expiry behavior.
- Store candidate evidence:
  - manufacturer meter ID;
  - address meter ID;
  - packet kind;
  - RSSI;
  - first seen;
  - last seen;
  - packet count;
  - whether temperature was observed.
- Discovery UI shows canonical `meter_id` read-only by default.
- Address/manufacturer evidence may be shown as details for debugging, not as competing ID choices.

### Availability Semantics

- Use Home Assistant's standard entity `available` property.
- Do not persist `last_seen` in the first implementation.
- Never-seen channels in the current runtime return `unknown` and remain available.
- Once a channel has been seen in the current runtime, it becomes unavailable when `now - last_seen > availability_timeout_minutes`.
- If availability is disabled, sensors preserve legacy behavior: keep the last known value and remain available.
- A fresh packet restores availability and updates the value.
- After Home Assistant restart, runtime `last_seen` starts empty; stale/unavailable decisions begin only after packets are observed in that runtime.

### Two-Tariff Total Sensor Guardrail

- Implement the optional two-tariff total sensor only if the current parser already exposes both tariff channel values reliably enough for synthetic tests.
- The total sensor must be disabled by default unless the user enables it.
- Do not expand two-tariff parser behavior based on assumptions without real samples.
- If implementation cannot satisfy the testable parser prerequisite, leave Task 7.1 documented but unimplemented and carry it forward with the next-release sample collection plan.

## Epic 1: Stabilize Post-Refactor UX

Goal: make the current working integration safe and comfortable for ordinary users.

### Task 1.1: Replace JSON-First Options UI

Scope:

- Replace the current JSON-first form with a user-facing options flow.
- Show a list of configured meters.
- Allow editing:
  - display name;
  - volume unit;
  - water type metadata, if present;
  - temperature channel enabled/disabled;
  - availability timeout.
- Keep JSON editor as advanced fallback.

Acceptance criteria:

- A user can inspect configured meters without reading JSON.
- A user can rename and change units from UI.
- Existing entity `unique_id` values do not change.
- Invalid edits are rejected with field-specific errors.
- Tests cover validation helpers.

Dependencies:

- D1.
- D2.

Priority: P0.

### Task 1.2: Improve Options Import UX

Scope:

- Keep "Import YAML configuration" available only when legacy YAML was detected.
- Show a clear message when no legacy YAML is loaded.
- After successful import, show how many meters and channels were imported.

Acceptance criteria:

- The import action is clearly labeled.
- No unlabeled controls appear.
- Importing does not overwrite non-empty config unless the user explicitly confirms.

Dependencies:

- D2.

Priority: P0.

### Task 1.3: README Troubleshooting Update

Scope:

- Document HACS custom repository installation.
- Document updating to a specific commit if HACS does not detect the latest commit immediately.
- Document YAML migration flow.
- Document that migrated YAML may be removed after successful import.
- Document common symptoms:
  - empty hub / no entities;
  - unknown meter IDs;
  - no Bluetooth scanner;
  - HACS restart required.

Acceptance criteria:

- README contains user-facing troubleshooting steps.
- The document does not expose real secrets or private IDs.

Dependencies: none.

Priority: P0.

## Epic 2: Meter Identity And Discovery

Goal: make meter identification explicit and robust before adding automatic discovery.

### Task 2.1: Formalize Meter Identity Model

Scope:

- Introduce normalized meter config:

```json
{
  "meter_id": "92728",
  "id_source": "manufacturer_or_address",
  "identity_evidence": {
    "manufacturer_meter_id": "92728",
    "address_meter_id": "92728"
  },
  "legacy_meter_id": "92728",
  "channels": [
    {
      "channel_id": "volume",
      "legacy_id": "92728",
      "name": "Cold Water",
      "measurement": "m3",
      "device_class": "water",
      "state_class": "total_increasing"
    },
    {
      "channel_id": "temperature",
      "legacy_id": "92728_temperature",
      "name": "Cold Water temperature",
      "measurement": "celsius",
      "device_class": "temperature",
      "state_class": "measurement"
    }
  ]
}
```

- Maintain backwards compatibility with existing config that lacks `identity_evidence`.
- Add config entry migration if needed.
- Normalize `meter_id` to the 24-bit Elehant serial number by treating shorter imported decimal values as the same number with leading zero bytes omitted.
- Preserve channel-level `legacy_id` values so entity unique IDs do not change.
- Treat meter-level `legacy_meter_id` only as migration/debug metadata, not as the source of channel unique IDs.
- Follow the normalized config, ID normalization, and unique ID contracts defined in `Implementation Contracts`.

Acceptance criteria:

- Existing imported entries continue to load.
- Coordinator matches readings by canonical 24-bit ID.
- Diagnostics shows which ID matched the last packet.
- Tests cover canonical 24-bit IDs, address-derived IDs, manufacturer-data IDs, and leading-zero normalization for imported short IDs.
- Tests confirm channel unique IDs continue to use channel-level `legacy_id`.
- Tests cover the config-entry migration from existing imported config to the normalized shape.

Dependencies:

- D1.

Priority: P0.

### Task 2.2: Unknown Packet Tracking

Scope:

- Track recently seen Elehant-like packets that did not match configured meters.
- Store enough data for discovery:
  - `manufacturer_meter_id`;
  - `address_meter_id`;
  - packet kind;
  - RSSI;
  - last seen;
  - count.
- Expire old candidates.
- Follow the discovery candidate rules defined in `Implementation Contracts`.

Acceptance criteria:

- Unknown packets do not create entities.
- Diagnostics shows summarized unknown candidates.
- Diagnostics include enough address/manufacturer evidence to debug discovery and identity matching.
- Identity mismatches are recorded for diagnostics and are not offered as normal discovery candidates.

Dependencies:

- Task 2.1.
- Task 5.1.

Priority: P1.

### Task 2.3: Discovery Flow

Scope:

- Offer discovered meters from recently seen unknown packets.
- Let the user confirm:
  - meter name;
  - canonical 24-bit meter ID, read-only by default;
  - volume unit;
  - water type metadata;
  - availability timeout, defaulting to the YAML migration default;
  - temperature channel.
- Avoid duplicates against configured canonical meter IDs.
- Follow the discovery/manual creation defaults defined in `Implementation Contracts`.

Acceptance criteria:

- Discovered meter can be added without YAML.
- Existing migrated meters are not duplicated.
- User sees the canonical 24-bit serial number, with address/manufacturer evidence available as details if useful.
- Tests cover duplicate prevention.
- Discovery candidates with conflicting address/manufacturer IDs are not offered as normal addable meters.

Dependencies:

- Task 2.1.
- Task 2.2.
- D1.
- D2.

Priority: P1.

## Epic 3: Availability And Diagnostics Entities

Goal: make operational state visible without changing legacy behavior unexpectedly.

### Task 3.1: Optional Availability Timeout

Scope:

- Add options:
  - availability enabled;
  - timeout minutes.
- Default: enabled.
- Default timeout: 60 minutes.
- Store the timeout explicitly during YAML migration.
- Offer the same default timeout in discovery/manual UI flows.
- Use Home Assistant's standard `available` entity property to mark sensors unavailable when no packet was seen for the configured timeout.
- Keep first-start behavior clear: never-seen channels remain `unknown` until the first packet is received in the current runtime.
- Follow the availability semantics defined in `Implementation Contracts`.

Acceptance criteria:

- Disabled timeout preserves legacy behavior.
- Enabled timeout marks stale channels unavailable after 60 minutes by default.
- User can change or disable the timeout from the options UI.
- Existing values recover automatically when a fresh packet is received.
- Migrated YAML entries contain an explicit timeout value.
- Discovery/manual creation offers the same timeout default.
- Tests cover stale and fresh states.
- Tests cover Home Assistant restart/current-runtime behavior without persisted `last_seen`.

Dependencies:

- D3.

Priority: P1.

### Task 3.2: Diagnostic Entities

Scope:

- Add diagnostic entities disabled by default where appropriate:
  - last seen;
  - RSSI;
  - packet count;
  - matched ID source.
- Mark entities with `entity_category=diagnostic`.

Acceptance criteria:

- Diagnostic entities do not clutter default UI.
- They update from the same coordinator state as primary sensors.
- They can be enabled from HA entity settings.

Dependencies:

- Task 2.1.

Priority: P2.

### Task 3.3: Repair Warnings

Scope:

- Add repairs for:
  - no active Bluetooth scanner;
  - configured meter never seen;
  - duplicate canonical meter IDs;
  - malformed config entry.

Acceptance criteria:

- Repairs are actionable.
- Repairs do not spam on normal infrequent BLE advertising.

Dependencies:

- Task 3.1.
- Task 5.1.

Priority: P2.

## Epic 4: Statistics And Units

Goal: integrate better with HA history/statistics without damaging migrated behavior.

### Task 4.1: UI Unit Handling

Scope:

- Move unit changes from JSON to UI.
- Validate units per channel:
  - volume: `l` or `m3`;
  - temperature: `celsius`.
- Keep raw count internal.

Acceptance criteria:

- Unit changes reload the integration cleanly.
- Entity unique IDs remain stable.
- Native values continue to match legacy conversion formulas.

Dependencies:

- Task 1.1.

Priority: P1.

### Task 4.2: State Class Metadata

Scope:

- Add state class metadata for:
  - volume channels: `total_increasing`;
  - temperature channels: `measurement`.
- Preserve existing entity IDs and unique IDs.
- Enable these state classes by default because the user's existing recorder metadata already matches this shape.
- Do not add a user-facing option unless implementation testing shows a regression risk.

Acceptance criteria:

- State class metadata is added without changing unique IDs.
- Documentation explains recorder/statistics implications.
- Volume sensors expose `state_class=total_increasing`.
- Temperature sensors expose `state_class=measurement`.
- Existing recorder statistic IDs are not renamed.
- Existing HA statistics for `sensor.voda_*` continue to be visible after upgrade.
- Tests cover entity metadata.

Dependencies:

- D4.

Priority: P2.

## Epic 5: Diagnostics Export And Debuggability

Goal: make diagnostics useful for support and field debugging.

### Task 5.1: Improve Diagnostics Export

Scope:

- Export config data useful for debugging:
  - meter count;
  - channel count;
  - configured meter IDs;
  - address/manufacturer meter IDs;
  - channel types;
  - unit preferences.
- Export runtime:
  - last seen age;
  - RSSI;
  - packet counters;
  - parser counters.
- Include enough detail to debug identity matching and stale sensors.
- Avoid exporting credentials or unrelated Home Assistant secrets.

Acceptance criteria:

- Diagnostics are useful for identity, parser, and availability debugging.
- Diagnostics do not include credentials, tokens, or unrelated HA configuration.
- Tests cover diagnostics serialization helpers.

Dependencies:

- D5.

Priority: P0.

### Task 5.2: Parser Statistics

Scope:

- Track counts:
  - total Elehant-like packets;
  - parsed packets;
  - ignored short payloads;
  - unknown meter IDs;
  - matched by manufacturer meter ID;
  - matched by address ID;
  - config entries with imported IDs normalized by leading-zero padding.

Acceptance criteria:

- Statistics are visible in diagnostics.
- Statistics do not grow unbounded.

Dependencies:

- Task 5.1.

Priority: P1.

## Epic 6: BLE Packet Validation

Goal: reduce false positives without blocking real meters.

### Task 6.1: Moderate Validation

Scope:

- Validate:
  - payload length;
  - non-empty IDs;
  - raw count is non-negative;
  - temperature is within a plausible configurable range.
- Do not reject real samples only because manufacturer ID is generic.

Acceptance criteria:

- Existing real samples still parse.
- Synthetic malformed packets are ignored.
- Parser tests cover every validation rule.

Dependencies:

- More real samples preferred.

Priority: P2.

### Task 6.2: Research Reliable BLE Signatures

Scope:

- Search for public or user-collected evidence for:
  - manufacturer ID;
  - stable payload prefix;
  - service UUIDs;
  - local name patterns.
- Do not add strict manifest matchers unless evidence is reliable.

Acceptance criteria:

- Research result is documented.
- Decision is either "add matcher" or "keep runtime filtering".

Dependencies: none.

Priority: P3.

## Epic 7: Two-Tariff And Other Meter Types

Goal: add features only when evidence is sufficient.

### Task 7.1: Two-Tariff Total Sensor

Scope:

- Add optional aggregate total sensor for two-tariff meters.
- Keep tariff sensors separate.
- Create total sensor disabled by default unless user enables it.
- Follow the two-tariff guardrail defined in `Implementation Contracts`.

Acceptance criteria:

- Total equals tariff 1 + tariff 2 in configured units.
- Missing tariff value yields `unknown` or unavailable according to configured behavior.
- If reliable parser data is unavailable, the task is explicitly deferred instead of implemented by assumption.

Dependencies:

- Real or reliable synthetic two-tariff tests.

Priority: P3.

## Single Release Implementation Plan

All planned improvements are delivered as one release. The phases below describe implementation order inside the release, not separate published versions.

### Architecture Review Remediation

The architecture review after implementation found several synchronization issues between the plan and the code. These are part of the current release and must be resolved before release readiness is claimed.

#### AR1: Align Unit/Measurement Terminology

Problem:

- The original implementation contract described `measurement` as a kind (`volume`/`temperature`) and `unit` as the unit (`m3`/`l`/`celsius`).
- The actual code, legacy YAML, options UI, and entity conversion use `measurement` as the unit field.

Current-release decision:

- Keep `measurement` as the persisted unit field for this release.
- Do not introduce `unit` or `measurement_kind` in code during this release.
- Treat channel kind as derived from `channel_id`, `device_class`, and sensor behavior.
- Update documentation, tests, and README wording so they no longer imply a separate stored `unit` field.

Acceptance criteria:

- The implementation contract matches the current config shape.
- README and examples use `measurement` only as the stored unit field.
- Advanced JSON validation continues to enforce `m3`/`l` for volume and `celsius` for temperature.
- No new config-entry migration is introduced only for terminology cleanup.

#### AR2: Complete Operational Polish In Current Release

Problem:

- Task 3.2 diagnostic entities and Task 3.3 repair warnings are still listed inside the current single-release plan.
- They were not moved to the next-release plan, so they must be implemented before this release is considered complete.

Current-release decision:

- Implement diagnostic entities in the current release:
  - last seen;
  - RSSI;
  - packet count;
  - matched ID source, if the runtime state can expose it cleanly.
- Mark diagnostic entities with `entity_category=diagnostic`.
- Keep diagnostic entities disabled by default unless a specific entity is harmless and clearly useful by default.
- Implement repairs in the current release for:
  - no active Bluetooth scanner;
  - configured meter never seen after a conservative grace period or after explicit diagnostics evidence;
  - duplicate canonical meter IDs;
  - malformed config entry.

Acceptance criteria:

- Diagnostic entities update from coordinator state and do not alter primary sensor unique IDs.
- Repairs are actionable and do not spam under normal sparse BLE advertising.
- Tests cover diagnostic entity metadata and repair issue creation helpers where practical.

#### AR3: Bound Unknown Packet Storage

Problem:

- Discovery candidates use TTL filtering, but `unknown_packets` itself can grow for the lifetime of the HA process.
- This conflicts with the parser-statistics acceptance criterion that statistics should not grow unbounded.

Current-release decision:

- Add bounded storage for unknown packets in the coordinator.
- Use both:
  - TTL-based eviction for old unknown packets;
  - a maximum number of retained unknown packet records as a hard cap.
- Eviction must not affect already configured meter states.

Acceptance criteria:

- Old unknown packets are removed or ignored beyond the configured TTL.
- A noisy BLE environment cannot grow `unknown_packets` without bound.
- Diagnostics still show enough recent unknown data for discovery/debugging.
- Tests cover TTL eviction and max-size eviction.

#### AR4: Clarify Config Schema Ownership

Problem:

- Config normalization and validation live in `config_flow.py`, but are used by setup, sensor platform, tests, and options flow.

Current-release decision:

- Do not perform a broad file split unless needed for implementing AR1-AR3.
- Before release, either:
  - move normalization/validation helpers to a dedicated `config_schema.py`, or
  - explicitly document `config_flow.py` as temporary ownership for config schema helpers and add a next-step note.

Acceptance criteria:

- There is one clear owner module for normalized config shape.
- Future work on repairs/diagnostic entities does not need to import UI flow internals unnecessarily.

#### AR5: Keep Dual YAML Import Entry Points As Temporary Compatibility

Problem:

- Legacy YAML import can be triggered through both integration setup and sensor platform setup.
- This is a deliberate temporary measure kept during debugging of automatic conversion.

Current-release decision:

- Keep both entry points in the current release.
- Ensure duplicate imports are harmless and tests continue to cover current behavior.
- Document removal of the manual/platform-triggered import path in the next-release plan.

Acceptance criteria:

- Duplicate import attempts do not create duplicate config entries.
- README describes YAML as migration input only.
- Next-release plan contains an explicit task to remove the temporary manual/platform import path after migration behavior is stable.

### Phase 1: Foundations And Migration

- Task 1.2: improve options import UX.
- Task 2.1: formal meter identity model.
- Task 3.1: optional availability timeout.
- Task 4.2: state class metadata.
- Task 5.1: improve diagnostics export.
- Task 5.2: parser statistics.

Goal:

- Establish the final config shape.
- Normalize imported IDs to canonical 24-bit meter IDs.
- Preserve channel-level legacy IDs for entity unique ID compatibility.
- Write explicit availability timeout values during YAML migration.
- Add HA-native state class metadata and detailed diagnostics early.

### Phase 2: User-Facing Configuration

- Task 1.1: form-based options UI.
- Task 4.1: UI unit handling.

Goal:

- Replace JSON-first editing with a maintainable UI.
- Make units, channel settings, and availability timeout editable without breaking entity IDs.

### Phase 3: Discovery

- Task 2.2: unknown packet tracking.
- Task 2.3: discovery flow.

Goal:

- Track unknown Elehant-like packets internally.
- Offer new meters using the canonical 24-bit serial number and the same availability defaults as migration/manual creation.

### Phase 4: Operational Polish

- Task 3.2: diagnostic entities.
- Task 3.3: repair warnings.

Goal:

- Add optional diagnostic entities and actionable repairs on top of the now-stable runtime/config model.

### Phase 5: Advanced Features

- Task 7.1: two-tariff total sensor.

Goal:

- Add non-critical advanced behavior after the single-tariff path, migration, statistics, and discovery are stable.

## Definition Of Ready

A task is ready for implementation when:

- its dependencies are complete or explicitly waived;
- affected config data shape is defined;
- entity identity impact is documented;
- migration behavior is documented;
- test strategy is clear;
- user-visible strings are listed;
- diagnostics changes are reviewed to avoid exposing credentials or unrelated Home Assistant configuration.

## Definition Of Done

A task is done when:

- unit tests pass;
- HA API compatibility tests pass;
- existing migrated config still loads;
- README or docs are updated;
- diagnostics do not expose credentials, tokens, or unrelated Home Assistant configuration;
- no primary entity `unique_id` changes unexpectedly;
- manual HA smoke test is performed when BLE/runtime behavior changes.
