# BLE Explorer Observations

## Sample: `docs/BLE_Expl_1.png`

Source: manually captured screenshot from Bluetooth LE Explorer.

Observed fields:

- Address: `B00102016A38`
- Normalized address: `B0:01:02:01:6A:38`
- Address type: `Public`
- Advertisement type: `NonConnectableUndirected`
- RSSI: `-78`
- Connectable: `False`
- Scannable: `False`
- Scan response: `False`
- Section type: `ManufacturerSpecificData (FF)`
- Section data:
  - `FF-FF-80-25-A0-01-02-01-38-6A-01-5F-DA-39-00-25-46-06-16`

Interpretation notes:

- The address confirms the legacy single-tariff prefix `B0:01:02`.
- The screenshot confirms that Elehant packets are non-connectable advertisements.
- The first two manufacturer data bytes appear to be the company identifier: `FF-FF`.
- If the old parser payload is interpreted as manufacturer data after the company identifier, the payload bytes are:
  - `80-25-A0-01-02-01-38-6A-01-5F-DA-39-00-25-46-06-16`
- Under that interpretation:
  - meter ID bytes at payload `[6:8]`: `38-6A`
  - meter ID little-endian: `27192`
  - raw count bytes at payload `[9:12]`: `5F-DA-39`
  - raw count little-endian: `3791455`
  - old liter value: `379145.5`
  - old cubic meter value: `379.1455`

Open questions:

- Confirm whether Home Assistant `BluetoothServiceInfoBleak.manufacturer_data` exposes the value with or without the company ID bytes.
- Confirm the same byte layout with at least one two-tariff packet.
- Confirm the meter ID and reading against a known physical meter display.
