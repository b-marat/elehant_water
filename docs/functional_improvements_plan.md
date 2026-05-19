# Functional Improvements Plan

## Scope

These improvements are intentionally separate from the compatibility refactor. They should be considered after the integration is stable on the current Home Assistant Bluetooth and entity APIs.

## Suggested Improvements

### UI Configuration

- Add full setup through Home Assistant Integrations.
- Allow users to add, rename, and remove meters from the UI.
- Add an options flow for changing units and diagnostic behavior.

### BLE Auto-Discovery

- Detect Elehant meters automatically from BLE advertisements.
- Offer discovered meters in the Home Assistant UI.
- Avoid creating duplicates for already configured counter IDs.
- Add a discovery flow for unknown Elehant meter IDs seen in BLE advertisements.
- Let users confirm the discovered meter name, tariff structure, and optional temperature sensor before adding it.
- Keep the initial compatibility refactor configured-only, then add discovery as a follow-up feature.

### BLE Packet Validation

- Add moderate payload validation after enough real samples have been collected.
- Validate reasonable field ranges to reduce noise and false positives:
  - non-empty physical meter ID;
  - non-negative raw count;
  - plausible temperature range;
  - packet type consistency with detected address prefix.
- Avoid inventing strict protocol checks unless Elehant protocol documentation or reliable reverse-engineered evidence is available.

### Better Availability

- Track `last_seen` for every configured meter.
- Mark sensors unavailable if no advertisement has been received for a configurable timeout.
- Add a repair warning when a configured meter has never been seen.

### Diagnostic Sensors

- Add optional diagnostic entities:
  - `last_seen`;
  - RSSI;
  - raw packet counter;
  - last successful update time.
- Mark these entities as diagnostic so they do not clutter the default UI.

### Two-Tariff Improvements

- Keep separate tariff sensors.
- Add an optional total consumption sensor for two-tariff meters.
- Make temperature sensor creation explicit and configurable.
- During future discovery flows, offer a temperature entity for two-tariff meters and create it disabled by default unless the user enables it.

### Unit Handling

- Prefer Home Assistant's native unit system where possible.
- Allow users to choose display units in the UI.
- Avoid custom unit conversion logic unless required for compatibility.
- Add configurable `state_class` support after validating Elehant long-term statistics behavior.
- Use sensible defaults when enabled, such as `total_increasing` for counter channels and `measurement` for temperature channels.

### Research Other Elehant Meter Types

- Research support for other Elehant meters, such as gas meters, only when devices or reliable BLE advertisement samples are available for testing.
- Do not claim support for untested meter types based only on model assumptions.
- Reuse the channel-based config model if future samples confirm compatible packet structures.

### Bluetooth Proxy Support

- Ensure the integration receives data from Home Assistant Bluetooth proxies.
- Document recommended Bluetooth proxy setup for weak signal areas.

### Repairs And User Guidance

- Add repair issues for common problems:
  - Bluetooth integration not loaded;
  - no active scanner;
  - meter not seen for a long time;
  - invalid or duplicate counter ID configuration.

### Diagnostics Export

- Provide a diagnostics download that includes:
  - integration version;
  - configured meters;
  - last seen timestamps;
  - availability state;
  - parser statistics.
- Redact MAC addresses unless the user explicitly needs them for troubleshooting.
- Redact or summarize config entry data instead of exposing full `entry.data`.
- Avoid exposing custom meter names, full meter IDs, or other home-layout details in diagnostics by default.

### Configuration Hardening

- Add stricter options-flow validation for normalized meter JSON.
- Validate allowed `measurement` values per channel.
- Validate allowed `device_class` values per channel.
- Report precise validation errors for malformed channels instead of a generic invalid config message.

### Code Cleanup

- Remove unused constants and declarations left from intermediate refactoring steps.
- Keep platform declarations consistent with the Home Assistant API style selected by the implementation.

### Optional Future Identity Migration

- Consider a future opt-in migration mode for moving primary sensors from legacy-compatible unique IDs to more descriptive unique IDs.
- Keep this out of the initial compatibility refactor.
- Make the migration explicit, reversible where possible, and well documented.
- Preserve existing `entity_id`, automations, dashboards, and recorder history during migration.
- Detect conflicts before changing any entity registry entries.
- Do not create duplicate primary sensors as the default migration path.

### Documentation

- Rewrite README in correct UTF-8.
- Add migration instructions from YAML to UI configuration.
- Add troubleshooting examples for common HA log errors.
- Document known Elehant packet formats.
- Add examples for single-tariff and two-tariff meters.

## Priority Recommendation

1. UI configuration and YAML migration.
2. BLE auto-discovery.
3. Availability and `last_seen`.
4. Diagnostic entities.
5. Two-tariff total sensor.
6. Repairs and diagnostics export.
