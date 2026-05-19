# Phase 0 Compatibility Spike Report

Date: 2026-05-19

## Inputs

- Existing integration code in `custom_components/elehant_water`.
- Home Assistant developer documentation checked on 2026-05-19.
- One real Elehant BLE sample captured via Bluetooth LE Explorer screenshot:
  - `docs/BLE_Expl_1.png`
  - transcribed in `docs/ble_samples/ble_explorer_observations.md`
  - sanitized fixture in `docs/ble_samples/single_tariff_b00102_sanitized.json`

## Confirmed From Home Assistant Documentation

- Config entries are the correct persistent configuration mechanism.
- Config entries support setup, unload, options/reconfigure, and migration through `async_migrate_entry`.
- Integrations with config flows must set `"config_flow": true` in `manifest.json`.
- Bluetooth discovery matchers in `manifest.json` can use:
  - `connectable`;
  - `local_name`;
  - `service_uuid`;
  - `service_data_uuid`;
  - `manufacturer_id`;
  - `manufacturer_data_start`.
- For devices that only need advertisement data, `connectable: false` should be used so Home Assistant can receive data from non-connectable Bluetooth controllers and proxies.
- `bluetooth.async_register_callback` can subscribe to Bluetooth discoveries using the same matcher format as the manifest, plus `address`.
- `PassiveBluetoothProcessorCoordinator` is intended for integrations whose primary updates arrive through Bluetooth advertisements and whose primary function is sensors, binary sensors, or events.

Sources:

- Home Assistant config entries: https://developers.home-assistant.io/docs/config_entries_index/
- Home Assistant config flow: https://developers.home-assistant.io/docs/core/integration/config_flow/
- Home Assistant Bluetooth overview: https://developers.home-assistant.io/docs/bluetooth/
- Home Assistant Bluetooth API: https://developers.home-assistant.io/docs/core/bluetooth/api/
- Home Assistant fetching Bluetooth data: https://developers.home-assistant.io/docs/core/bluetooth/bluetooth_fetching_data/
- Home Assistant manifest Bluetooth matchers: https://developers.home-assistant.io/docs/creating_integration_manifest/

## Confirmed From Real Elehant Sample

Sample: `docs/BLE_Expl_1.png`

- Address: `B00102016A38`
- Normalized address: `B0:01:02:01:6A:38`
- Address type: `Public`
- Advertisement type: `NonConnectableUndirected`
- Connectable: `False`
- Scannable: `False`
- Section type: `ManufacturerSpecificData (FF)`
- Section data:
  - `FF-FF-80-25-A0-01-02-01-38-6A-01-5F-DA-39-00-25-46-06-16`

Implications:

- The legacy address prefix `B0:01:02` is confirmed for at least one single-tariff Elehant water meter.
- The device advertises as non-connectable, so Home Assistant Bluetooth usage must set `connectable=False`.
- BLE Explorer presents manufacturer data with a `FF-FF` company identifier followed by the payload expected by the old parser.
- The parser must handle manufacturer payloads with or without the company identifier depending on how Home Assistant exposes `BluetoothServiceInfoBleak.manufacturer_data`.
- The old parser offsets are preserved for compatibility: meter ID is read from payload `[6:8]`, raw count from payload `[9:12]`, and two-tariff temperature from payload `[14:16]`.

## Local BLE Tooling Findings

- Windows has an Intel Bluetooth adapter and Bluetooth LE Explorer can see nearby BLE traffic.
- PowerShell WinRT `BluetoothLEAdvertisementWatcher` starts but did not receive advertisements in this environment.
- The local Windows/PowerShell watcher is not authoritative for Home Assistant behavior.
- Real BLE automation on this workstation should not be part of CI acceptance unless a reliable capture path is established later.

## Deferred Or Missing Evidence

- No real two-tariff packet sample has been captured yet.
- No official Elehant BLE protocol documentation was found.
- No reliable manufacturer/service signature beyond the observed `manufacturer_id=65535` and legacy address prefix has been confirmed.
- It is still unconfirmed whether Home Assistant exposes Elehant manufacturer data with or without the company identifier bytes in `BluetoothServiceInfoBleak.manufacturer_data`.

## Confirmed Architecture Decisions

### Minimum Supported Home Assistant Version

Decision: target the current Home Assistant Core line first, starting with 2026.5.x, and document that as the initial tested/supported version.

Rationale:

- The project goal is to restore compatibility with current HA/HAOS.
- The integration is small and currently broken on modern HA, so minimizing compatibility shims is more valuable than supporting older Core versions during the first refactor.
- Support can be widened later after tests pass against older versions.

### Bluetooth Subscription API

Decision: use `bluetooth.async_register_callback` for the initial refactor.

Rationale:

- The integration has a pre-existing list of configured meter IDs and should remain configured-only in the initial refactor.
- Elehant identification depends on address prefixes unless better signatures are confirmed.
- A custom integration-owned coordinator is already the chosen update model.
- `async_register_callback` is the most direct fit for receiving advertisements, filtering them through the parser, and updating configured channels.
- `PassiveBluetoothProcessorCoordinator` remains a future simplification candidate once more packet samples and matcher confidence exist.

### Bluetooth Matcher Policy

Decision: do not add speculative strict manifest Bluetooth matchers in the initial refactor.

Runtime subscription should use the broadest safe matcher available and then perform Elehant detection in the parser:

- Prefer address-prefix filtering if Home Assistant's matcher supports the observed addresses reliably.
- Otherwise subscribe broadly enough to receive non-connectable advertisements and filter inside the callback.
- Use `connectable=False`.

Rationale:

- Public Elehant BLE documentation was not found.
- The only confirmed signature is address-prefix based.
- `manufacturer_id=65535` is too generic to use alone as a discovery matcher.

### Parser Payload Handling

Decision: parser should accept manufacturer payload in either form:

- payload without company ID:
  - `80-25-A0-01-02-01-38-6A-01-5F-DA-39-00-25-46-06-16`
- payload with company ID prefix:
  - `FF-FF-80-25-A0-01-02-01-38-6A-01-5F-DA-39-00-25-46-06-16`

Rationale:

- BLE Explorer displays the company ID in the section data.
- Home Assistant/Bleak commonly expose `manufacturer_data` as `{company_id: payload_without_company_id}`.
- Accepting both forms makes the parser robust for fixtures and HA runtime.

### Validation Policy

Decision: keep initial validation minimal:

- address prefix must match a known packet kind;
- manufacturer payload must have the minimum length required by the old offsets;
- no speculative range validation yet.

Rationale:

- There is not enough protocol evidence for strict validation.
- Moderate validation remains a functional improvement after more samples are collected.

## Optional Evidence And Follow-Up

- A real two-tariff packet sample is useful but not required to start implementation.
- No two-tariff device is currently available for local capture.
- Internet samples may be researched, but they should not be treated as more authoritative than the existing integration code unless their origin is reliable.
- Initial two-tariff parser and routing behavior may be based on the existing code and covered with synthetic fixtures.
