# Refactoring Plan

## Goal

Bring the Elehant Water Home Assistant custom integration to a modern, maintainable architecture without changing its core behavior: receive Elehant BLE advertisement packets and expose water meter and temperature sensors.

## Architectural Principles

- Keep the domain layer independent from Home Assistant.
- Keep BLE parsing deterministic and testable with no HA imports.
- Keep Home Assistant integration code as an adapter around the domain model.
- Preserve existing entity registry identity for all existing primary sensors.
- Use one config entry for the integration, containing a list of configured meters.
- Keep initial refactor behavior configured-only while preserving enough parsed packet data for future discovery.
- Track `last_seen` internally, but do not change primary sensor availability behavior in the initial refactor.
- Import legacy YAML names as default/suggested entity names and do not overwrite user-renamed entities.
- Prefer Home Assistant lifecycle hooks over custom loops, threads, sockets, or timers.
- Store the raw meter count in the domain model and calculate HA-facing values at the entity boundary.
- Preserve legacy `measurement: l/m3` behavior for migrated primary sensors.

## Target Responsibilities

- `parser.py`: parse BLE advertisement data, own legacy address-prefix matching, normalize address formats before matching, and return domain readings. No Home Assistant imports.
- `models.py`: define dataclasses and enums such as `ElehantReading`, `ElehantMeterId`, `ElehantChannel`, and `Tariff`.
- `coordinator.py`: integration-owned runtime coordinator that receives parsed readings, maintains latest state and `last_seen`, and notifies entities through listener callbacks.
- `sensor.py`: expose coordinator state as Home Assistant `SensorEntity` objects.
- `config_flow.py`: handle setup and options only, with no parser logic.
- `diagnostics.py`: expose redacted integration diagnostics.
- `const.py`: shared constants for domain and Home Assistant integration boundaries.

## Config Data Model

Use one config entry with a normalized list of physical meters and configured channels:

```python
{
    "meters": [
        {
            "meter_id": "31560",
            "channels": [
                {
                    "channel": "volume",
                    "legacy_id": "31560",
                    "name": "...",
                    "measurement": "l",
                    "device_class": "water",
                }
            ],
        },
        {
            "meter_id": "31562",
            "channels": [
                {
                    "channel": "tariff_1",
                    "legacy_id": "31562_1",
                    "name": "...",
                    "measurement": "l",
                    "device_class": "water",
                },
                {
                    "channel": "tariff_2",
                    "legacy_id": "31562_2",
                    "name": "...",
                    "measurement": "l",
                    "device_class": "water",
                },
                {
                    "channel": "temperature",
                    "legacy_id": "31562",
                    "name": "...",
                    "measurement": "celsius",
                    "device_class": "temperature",
                },
            ],
        },
    ]
}
```

Rules:

- `meter_id` is always the physical ID parsed from the advertisement payload, without legacy suffixes such as `_1` or `_2`.
- `channels` defines which HA entities should exist for the meter.
- Use `volume` as the default single-channel counter reading name for volume meters. This is not water-specific and can also cover other Elehant volume meters, such as gas meters.
- Do not add a separate `kind` field; single-tariff, two-tariff, temperature-capable, and future meter variants are represented by their configured channels.
- `legacy_id` preserves compatibility with old YAML IDs and old primary sensor unique IDs.
- `measurement` belongs to the channel, not the whole integration.
- `measurement` is a display/unit preference, not the raw protocol value.
- `device_class` belongs to the channel. Existing imported water meters default to `water`, while the model remains open for future non-water volume meter types.
- Do not hard-code the model as water-only; future Elehant meter types may use other measurement kinds.
- Temperature channels default to Celsius for current Elehant devices, but the model should not forbid other temperature units if a future device requires them.
- Keep the initial refactor scoped to the existing `elehant_water` domain and available water meter devices.
- Do not rename the integration domain or add untested support for non-water meters during the initial refactor.

## Phase 0: Compatibility Spike

- Identify the target Home Assistant Core and Python versions.
- Decision point: define the minimum supported Home Assistant Core version based on the Bluetooth and config entry APIs used by the implementation.
- Initial Phase 0 decision: target Home Assistant Core `2026.5.x` as the first tested/supported line.
- Record the selected minimum supported HA version in documentation and HACS metadata where appropriate.
- Confirm which Home Assistant Bluetooth APIs are available in the target version.
- Capture real Elehant BLE advertisement samples from a working environment if possible.
- If Bluetooth tools cannot export raw logs, transcribe Bluetooth LE Explorer screenshots into structured notes and sanitized fixtures.
- Verify which fields are available through `BluetoothServiceInfoBleak`:
  - address;
  - manufacturer data;
  - service data;
  - local name;
  - RSSI;
  - source/scanner information.
- Determine whether Elehant packets can be reliably matched using Home Assistant Bluetooth matchers.
- Search for reliable Elehant BLE documentation or captured evidence for `manufacturer_id`, `manufacturer_data_start`, service UUIDs, or other stable signatures.
- Decision point: choose the Home Assistant Bluetooth subscription API based on evidence:
  - use `PassiveBluetoothProcessorCoordinator` if packet matching and data extraction fit HA's passive Bluetooth processor model;
  - use `bluetooth.async_register_callback` if a lower-level advertisement callback is simpler or more reliable.
- Initial Phase 0 decision: use `bluetooth.async_register_callback`.
- Use strict manifest Bluetooth matchers only if reliable Elehant signatures are confirmed.
- Initial Phase 0 decision: do not add speculative strict manifest Bluetooth matchers.
- If no reliable signatures are confirmed, keep the legacy-compatible address-prefix detection method:
  - `b0:01:02` for single-tariff packets;
  - `b0:03:02` for two-tariff tariff 1 packets;
  - `b0:04:02` for two-tariff tariff 2 packets.
- When using address-prefix detection in the initial refactor, validate only the minimum required payload length:
  - at least 12 bytes for volume readings;
  - at least 16 bytes for temperature readings.
- Keep address-prefix matching in a dedicated tested function that normalizes address case and format before matching.
- Regardless of the Bluetooth subscription API, keep the integration's update model as an integration-owned runtime coordinator with listener callbacks.
- Parser should accept manufacturer payloads both with and without the `FF-FF` company identifier prefix.
- Confirm which parsed fields are sufficient for future discovery flows, even though automatic discovery is not part of the initial refactor.
- Create golden BLE fixtures for parser tests before changing the transport layer.
- Use sanitized fixtures in the repository and allow private ignored fixtures for local debugging with real addresses.

## Phase 1: Stabilize Current Behavior

- Document the current Elehant BLE payload format.
- Document that two-tariff meters publish separate advertisement packets for tariff 1 and tariff 2.
- Extract packet parsing from `sensor.py` into a dedicated `parser.py` module.
- Add parser tests for:
  - single-tariff meters;
  - two-tariff meter tariff 1;
  - two-tariff meter tariff 2;
  - temperature extraction;
  - malformed or too-short payloads.
- Two-tariff parser tests may use synthetic fixtures derived from the existing implementation if no reliable real packet sample is available.
- Remove global runtime state such as `inf`, `measurement`, and `current_event_loop`.
- Replace global dictionaries with integration runtime data owned by a coordinator or manager object.
- Remove manual event loop creation and `run_forever`.
- Fix the current runtime bug where `current_event_loop(btctrl.stop_scan_request())` calls the loop object as a function.
- Document raw count conversion formulas for legacy liter and cubic meter display preferences.
- Keep compatibility with old `measurement: l/m3` only as an import or display preference, not as core domain logic.
- Replace deprecated Home Assistant constants with modern unit enums:
  - `UnitOfVolume.LITERS`;
  - `UnitOfVolume.CUBIC_METERS`;
  - `UnitOfTemperature.CELSIUS`.

## Phase 2: Replace Legacy Bluetooth Layer

- Remove `aioblescan` from `manifest.json`.
- Stop opening the Bluetooth adapter directly with raw HCI sockets.
- Use Home Assistant's shared Bluetooth stack instead.
- Add the required Bluetooth dependency to `manifest.json`, such as `bluetooth_adapters` according to the current HA developer docs.
- In the initial refactor, update only configured meters and ignore unknown Elehant meter IDs except for debug logging and diagnostics.
- Use a passive BLE architecture because Elehant meters publish their data in advertisements.
- Initial Phase 0 decision: use `bluetooth.async_register_callback` for the first refactor.
- Keep `PassiveBluetoothProcessorCoordinator` as a future simplification candidate after more packet samples and matcher confidence exist.
- Use `connectable=False`, since the integration only needs advertisement data.
- Ensure the integration works with local Bluetooth adapters and Bluetooth proxies supported by Home Assistant.

## Phase 3: Move To Config Entries

- Add `config_flow.py`.
- Add UI setup through Home Assistant Integrations.
- Use a single config entry for the integration.
- Store all configured meters inside that config entry.
- Prevent creating multiple config entries for the same integration unless a future use case requires it.
- Support old YAML configuration only as an import/migration path into a config entry.
- Do not maintain YAML as a parallel long-term configuration system.
- After import, manage configuration through the UI config entry and options flow.
- Add an options flow for editing:
  - configured meters;
  - names;
  - tariff configuration;
  - display units;
  - optional temperature sensors.
- Store configuration in config entries instead of relying on platform YAML only.
- Store the legacy `measurement` preference on imported measurement channels during YAML import.
- Store two-tariff meters in a normalized internal structure using the physical meter ID and tariff channels.
- Keep compatibility mappings for legacy YAML IDs such as `31562_1` and `31562_2`.
- During YAML import, create temperature entities only when the old configuration explicitly provided `name_temp`.
- Do not automatically add new temperature entities in the initial compatibility refactor.
- During YAML import, store old `name` and `name_temp` values as default/suggested names.
- After entities are created, do not force config names over Home Assistant entity registry names.

## Phase 4: Define Config Entry Lifecycle

- Implement `async_setup_entry`.
- Register Bluetooth callbacks or coordinator listeners during setup.
- Store runtime data under `hass.data[DOMAIN][entry.entry_id]`.
- Use the integration-owned runtime coordinator as the single source of latest parsed readings.
- Store `last_seen` timestamps for configured meters for diagnostics and future availability behavior.
- Register cleanup callbacks with `entry.async_on_unload`.
- Implement `async_unload_entry`.
- Ensure Bluetooth callbacks are always unregistered on unload.
- Ensure options updates trigger a clean reload when needed.
- Avoid dangling callbacks after reload, restart, or failed setup.
- Handle setup failure cleanly if Bluetooth is unavailable.

## Phase 5: Modernize Sensor Entities

- Replace `homeassistant.helpers.entity.Entity` with `homeassistant.components.sensor.SensorEntity`.
- Use `native_value` instead of `state`.
- Use `native_unit_of_measurement` instead of `unit_of_measurement`.
- Add correct device classes:
  - water/volume sensors: `SensorDeviceClass.WATER` or `SensorDeviceClass.VOLUME`;
  - temperature sensors: `SensorDeviceClass.TEMPERATURE`.
- Do not add `state_class` in the initial compatibility refactor.
- Keep state-class support as a follow-up enhancement after validating long-term statistics behavior for Elehant counters.
- Keep legacy-compatible unique IDs for primary sensors:
  - water sensor: `elehant_<id>`;
  - temperature sensor: `elehant_temp_<id>`.
- For two-tariff water sensors, keep legacy-compatible IDs such as `elehant_31562_1` and `elehant_31562_2`.
- Compute primary water sensor values from raw meter counts using the configured display unit preference.
- Use new descriptive unique ID formats only for new entity types that did not exist before, such as diagnostics or optional aggregate sensors.
- Add `device_info` so related entities are grouped under one Elehant device.
- Do not create duplicate primary sensors with both legacy and new unique IDs.

## Phase 6: Migration Strategy

- Treat migration as a first-class compatibility requirement.
- Preserve existing unique IDs for existing sensors whenever practical:
  - old water sensor: `elehant_<id>`;
  - old temperature sensor: `elehant_temp_<id>`.
- Treat these legacy-compatible unique IDs as canonical for primary water and temperature sensors.
- Create a mapping table for old YAML devices to new config entry devices.
- Map old two-tariff YAML IDs such as `31562_1` and `31562_2` to one physical meter ID with two tariff channels.
- Import old YAML config into config entries.
- Treat YAML import as a migration path only, not as ongoing parallel configuration.
- Import only the temperature sensors that existed in the old YAML configuration.
- Preserve imported names at first creation while respecting later UI renames stored in the entity registry.
- Preserve existing entity IDs and recorder history where possible.
- Use new unique ID formats only for newly introduced sensors, such as diagnostic or total sensors.
- Avoid automatic unique ID rewrites for existing primary sensors during the initial refactor.
- Add config entry migration versioning.
- Write migration notes for users whose setups cannot be migrated automatically.

## Phase 7: Restructure The Integration

Target structure:

```text
custom_components/elehant_water/
  __init__.py
  manifest.json
  const.py
  models.py
  config_flow.py
  sensor.py
  parser.py
  coordinator.py
  diagnostics.py
  translations/
    en.json
    ru.json
tests/
  test_parser.py
  fixtures/
    advertisements/
```

## Phase 8: Manifest And HACS Cleanup

- Add `iot_class`, likely `local_push` for BLE advertisement updates.
- Add an explicit `integration_type`.
- Add Home Assistant Bluetooth dependencies.
- Remove the legacy `aioblescan` requirement.
- Add Bluetooth discovery matchers if Elehant packets can be matched reliably.
- Do not add speculative Bluetooth matchers without confirmed Elehant BLE signatures.
- Review `hacs.json` and update metadata if needed.
- Document the minimum supported Home Assistant Core version selected during Phase 0.
- Fix README encoding and update installation instructions.

## Phase 9: Diagnostics And Logging

- Add focused debug logging for:
  - recognized Elehant advertisements;
  - unrecognized or invalid payloads;
  - configured counters not found in received packets;
  - successful sensor updates.
- Add `diagnostics.py`.
- Include diagnostic data such as:
  - configured counter IDs;
  - last packet timestamp;
  - last RSSI if available;
  - integration version.
- Expose `last_seen` through diagnostics, but keep primary sensor availability compatible with the legacy behavior.
- Avoid exposing sensitive data unnecessarily.
- Add setup diagnostics or repair guidance if no Home Assistant Bluetooth scanner is available.
- Do not add "meter not seen for a long time" repairs in the initial compatibility refactor; keep that behavior for a follow-up availability feature.

## Phase 10: Testing

- Add unit tests for parser behavior.
- Add golden fixture tests based on real BLE advertisements.
- Store fixtures as structured JSON containing:
  - address;
  - manufacturer data;
  - service data if present;
  - RSSI if relevant;
  - expected parsed reading.
- Sanitize public fixture addresses while preserving the meaningful Elehant address prefix.
- Allow private local fixtures with real addresses for debugging, excluded from version control.
- Add tests for sensor entity metadata:
  - device class;
  - unit;
  - unique ID.
- Add config flow tests.
- Add YAML import tests.
- Add malformed BLE packet tests.
- Add tests for minimum payload length validation.
- Add tests for address-prefix matching with different address casing and formatting.
- Use a phased testing strategy:
  - start with parser and domain tests that do not require a Home Assistant test harness;
  - add Home Assistant custom integration tests after the minimum HA version and Bluetooth API are selected.
- Validate against a recent Home Assistant Core test environment.

## Initial Refactor Acceptance Criteria

| Criterion | Verification | Level |
| --- | --- | --- |
| Integration loads on the selected minimum/current HA version. | Install in a HA dev/test instance and confirm there is no setup error in logs. | Manual or HA integration test |
| Old YAML is imported into one config entry. | Start HA with legacy YAML and verify one `elehant_water` config entry containing all configured meters. | HA integration test |
| The same primary entities are created. | Compare expected entities from YAML: `elehant_<id>`, two-tariff `elehant_<id>_1`/`elehant_<id>_2`, and `elehant_temp_<id>` only when `name_temp` existed. | HA integration test |
| Primary `unique_id` values are preserved. | Inspect entity registry or HA test registry entries. | HA integration test |
| Single-tariff packets update the matching volume sensor. | Feed a fixture advertisement through parser/coordinator and assert the target entity value. | Unit/HA integration test |
| Two-tariff packets update the matching tariff channel. | Feed `b0:03:02` and `b0:04:02` fixtures and assert tariff 1/tariff 2 routing. | Unit/HA integration test |
| BLE is handled through Home Assistant Bluetooth APIs. | Confirm there is no `aioblescan`, raw HCI socket, custom event loop, or manual scan loop left in the integration. | Code review/test |
| Unknown meter IDs do not create entities. | Feed an unknown but parseable Elehant packet and verify entity registry remains unchanged. | HA integration test |
| `last_seen` is tracked without changing availability behavior. | Feed a fixture packet and verify coordinator diagnostics contain a timestamp while primary entities keep legacy availability semantics. | Unit/HA integration test |
| Parser/domain tests pass. | Run the parser/domain test suite against sanitized fixtures. | Automated unit test |
| Real BLE behavior is smoke-tested separately. | Use the actual HA host, Bluetooth proxy, or local BLE tooling with real meters; this is not required for CI acceptance. | Manual hardware check |
| README and migration notes are updated. | Review documentation for minimum HA version, YAML import, limitations, and troubleshooting. | Documentation review |

## Recommended Work Order

1. Run the compatibility spike and collect real BLE advertisement fixtures.
2. Extract and test the BLE parser.
3. Add domain models and store raw meter counts.
4. Replace deprecated HA constants and sensor base classes.
5. Replace `aioblescan` with the selected HA Bluetooth API.
6. Introduce coordinator/runtime state.
7. Implement config entry lifecycle and cleanup.
8. Add config entries and YAML import.
9. Implement unique ID and entity migration strategy.
10. Add diagnostics and Bluetooth setup repair guidance.
11. Update docs and HACS metadata.
