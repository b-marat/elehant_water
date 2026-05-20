"""Parser for Elehant BLE advertisement data."""

from __future__ import annotations

from collections.abc import Mapping

from .models import ElehantChannel, ElehantPacketKind, ElehantReading

PREFIX_SINGLE_TARIFF = "b0:01:02"
PREFIX_TARIFF_1 = "b0:03:02"
PREFIX_TARIFF_2 = "b0:04:02"
PREFIX_ELEHANT_FAMILY = "b0"

COMPANY_ID_PREFIX = b"\xff\xff"

MIN_VOLUME_PAYLOAD_LEN = 13
MIN_TEMPERATURE_PAYLOAD_LEN = 16
MAX_METER_ID = 0xFFFFFF


def normalize_meter_id(value: str | int) -> str:
    """Normalize a meter ID to canonical decimal text for a 24-bit Elehant ID."""
    meter_id = int(str(value))
    if meter_id < 0 or meter_id > MAX_METER_ID:
        raise ValueError("meter ID must be in range 0..16777215")
    return str(meter_id)


def normalize_address(address: str) -> str:
    """Normalize a Bluetooth address to lower-case colon-separated form."""
    compact = "".join(char for char in address if char.isalnum()).lower()
    if len(compact) == 12:
        return ":".join(compact[index : index + 2] for index in range(0, 12, 2))
    return address.replace("-", ":").lower()


def packet_kind_from_address(address: str) -> ElehantPacketKind | None:
    """Return the Elehant packet kind identified by a legacy address prefix."""
    normalized = normalize_address(address)
    if normalized.startswith(PREFIX_SINGLE_TARIFF):
        return ElehantPacketKind.SINGLE_TARIFF
    if normalized.startswith(PREFIX_TARIFF_1):
        return ElehantPacketKind.TWO_TARIFF_1
    if normalized.startswith(PREFIX_TARIFF_2):
        return ElehantPacketKind.TWO_TARIFF_2
    return None


def looks_like_elehant_address(address: str) -> bool:
    """Return whether an address belongs to the broad Elehant prefix family."""
    return normalize_address(address).startswith(PREFIX_ELEHANT_FAMILY)


def meter_id_from_address_suffix(address: str) -> str | None:
    """Return the canonical meter ID encoded in the final three address bytes."""
    parts = normalize_address(address).split(":")
    if len(parts) != 6 or parts[0] != PREFIX_ELEHANT_FAMILY:
        return None
    try:
        return str(int("".join(parts[3:6]), 16))
    except ValueError:
        return None


def strip_company_id_prefix(payload: bytes) -> bytes:
    """Remove the company identifier prefix if a tool included it in payload bytes."""
    if payload.startswith(COMPANY_ID_PREFIX):
        return payload[len(COMPANY_ID_PREFIX) :]
    return payload


def meter_id_from_manufacturer_payload(payload: bytes) -> str | None:
    """Return the canonical meter ID encoded in manufacturer payload bytes."""
    payload = strip_company_id_prefix(payload)
    if len(payload) < 9:
        return None
    return str(int.from_bytes(payload[6:9], byteorder="little"))


def parse_manufacturer_payload(
    address: str,
    payload: bytes,
    rssi: int | None = None,
) -> ElehantReading | None:
    """Parse one Elehant manufacturer payload."""
    packet_kind = packet_kind_from_address(address)
    if packet_kind is None:
        return None

    payload = strip_company_id_prefix(payload)
    min_len = (
        MIN_VOLUME_PAYLOAD_LEN
        if packet_kind is ElehantPacketKind.SINGLE_TARIFF
        else MIN_TEMPERATURE_PAYLOAD_LEN
    )
    if len(payload) < min_len:
        return None

    manufacturer_meter_id = meter_id_from_manufacturer_payload(payload)
    if manufacturer_meter_id is None:
        return None
    address_meter_id = meter_id_from_address_suffix(address)
    identity_mismatch = (
        address_meter_id is not None and address_meter_id != manufacturer_meter_id
    )
    meter_id = manufacturer_meter_id
    alternate_meter_ids = (
        (address_meter_id,)
        if address_meter_id is not None and address_meter_id != meter_id
        else ()
    )
    raw_count = int.from_bytes(payload[9:13], byteorder="little")
    normalized_address = normalize_address(address)

    if packet_kind is ElehantPacketKind.SINGLE_TARIFF:
        temperature_celsius = None
        if len(payload) >= MIN_TEMPERATURE_PAYLOAD_LEN:
            temperature_celsius = int.from_bytes(payload[14:16], byteorder="little") / 100
        return ElehantReading(
            meter_id=meter_id,
            channel=ElehantChannel.VOLUME,
            raw_count=raw_count,
            packet_kind=packet_kind,
            address=normalized_address,
            rssi=rssi,
            temperature_celsius=temperature_celsius,
            alternate_meter_ids=alternate_meter_ids,
            manufacturer_meter_id=manufacturer_meter_id,
            address_meter_id=address_meter_id,
            identity_mismatch=identity_mismatch,
        )

    temperature_celsius = int.from_bytes(payload[14:16], byteorder="little") / 100
    channel = (
        ElehantChannel.TARIFF_1
        if packet_kind is ElehantPacketKind.TWO_TARIFF_1
        else ElehantChannel.TARIFF_2
    )
    return ElehantReading(
        meter_id=meter_id,
        channel=channel,
        raw_count=raw_count,
        packet_kind=packet_kind,
        address=normalized_address,
        rssi=rssi,
        temperature_celsius=temperature_celsius,
        alternate_meter_ids=alternate_meter_ids,
        manufacturer_meter_id=manufacturer_meter_id,
        address_meter_id=address_meter_id,
        identity_mismatch=identity_mismatch,
    )


def parse_manufacturer_data(
    address: str,
    manufacturer_data: Mapping[int, bytes],
    rssi: int | None = None,
) -> ElehantReading | None:
    """Parse manufacturer data from a Bluetooth advertisement."""
    for payload in manufacturer_data.values():
        reading = parse_manufacturer_payload(address, payload, rssi)
        if reading is not None:
            return reading
    return None
