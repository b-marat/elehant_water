"""Tests for the Elehant BLE parser."""

from __future__ import annotations

from custom_components.elehant_water.models import ElehantChannel, ElehantPacketKind
from custom_components.elehant_water.parser import (
    looks_like_elehant_address,
    meter_id_from_address_suffix,
    normalize_address,
    packet_kind_from_address,
    parse_manufacturer_data,
    parse_manufacturer_payload,
)

SINGLE_PAYLOAD_WITH_COMPANY = bytes.fromhex(
    "ffff8025a0010201386a015fda390025460616"
)
SINGLE_PAYLOAD = bytes.fromhex("8025a0010201386a015fda390025460616")


def test_normalize_address() -> None:
    """Addresses are normalized before prefix matching."""
    assert normalize_address("B00102016A38") == "b0:01:02:01:6a:38"
    assert normalize_address("B0-01-02-01-6A-38") == "b0:01:02:01:6a:38"
    assert normalize_address("b0:01:02:01:6a:38") == "b0:01:02:01:6a:38"


def test_packet_kind_from_address() -> None:
    """Legacy address prefixes identify Elehant packet kinds."""
    assert (
        packet_kind_from_address("B0:01:02:01:6A:38")
        is ElehantPacketKind.SINGLE_TARIFF
    )
    assert packet_kind_from_address("B0:03:02:01:6A:38") is ElehantPacketKind.TWO_TARIFF_1
    assert packet_kind_from_address("B0:04:02:01:6A:38") is ElehantPacketKind.TWO_TARIFF_2
    assert packet_kind_from_address("AA:01:02:01:6A:38") is None


def test_looks_like_elehant_address() -> None:
    """The broad runtime pre-filter uses only the first address byte."""
    assert looks_like_elehant_address("B0:99:88:01:6A:38")
    assert looks_like_elehant_address("B09988016A38")
    assert not looks_like_elehant_address("AF:01:02:01:6A:38")


def test_meter_id_from_address_suffix() -> None:
    """Extended forks may identify meters by the final three address bytes."""
    assert meter_id_from_address_suffix("B0:01:02:01:6A:38") == "92728"
    assert meter_id_from_address_suffix("B00102016A38") == "92728"
    assert meter_id_from_address_suffix("AF:01:02:01:6A:38") is None


def test_parse_single_tariff_payload_without_company_id() -> None:
    """The real single-tariff sample parses without the company ID prefix."""
    reading = parse_manufacturer_payload("B0:01:02:01:6A:38", SINGLE_PAYLOAD, -78)

    assert reading is not None
    assert reading.packet_kind is ElehantPacketKind.SINGLE_TARIFF
    assert reading.channel is ElehantChannel.VOLUME
    assert reading.meter_id == "27192"
    assert reading.raw_count == 3791455
    assert reading.rssi == -78
    assert reading.temperature_celsius == 16.06
    assert reading.alternate_meter_ids == ("92728",)


def test_parse_single_tariff_payload_with_company_id() -> None:
    """The parser accepts BLE Explorer style data with the company ID prefix."""
    reading = parse_manufacturer_payload(
        "B00102016A38",
        SINGLE_PAYLOAD_WITH_COMPANY,
        -78,
    )

    assert reading is not None
    assert reading.meter_id == "27192"
    assert reading.raw_count == 3791455


def test_parse_manufacturer_data() -> None:
    """Manufacturer data mappings from HA/Bleak are accepted."""
    reading = parse_manufacturer_data("B0:01:02:01:6A:38", {65535: SINGLE_PAYLOAD})

    assert reading is not None
    assert reading.meter_id == "27192"


def test_short_payload_is_ignored() -> None:
    """Payloads shorter than the old parser offsets are ignored."""
    assert parse_manufacturer_payload("B0:01:02:01:6A:38", b"\x01" * 11) is None
    assert parse_manufacturer_payload("B0:03:02:01:6A:38", b"\x01" * 15) is None


def test_two_tariff_routing_from_legacy_prefixes() -> None:
    """Two-tariff packets route to separate channels based on address prefix."""
    tariff_1 = parse_manufacturer_payload("B0:03:02:01:6A:38", SINGLE_PAYLOAD)
    tariff_2 = parse_manufacturer_payload("B0:04:02:01:6A:38", SINGLE_PAYLOAD)

    assert tariff_1 is not None
    assert tariff_1.packet_kind is ElehantPacketKind.TWO_TARIFF_1
    assert tariff_1.channel is ElehantChannel.TARIFF_1
    assert tariff_1.temperature_celsius == 16.06

    assert tariff_2 is not None
    assert tariff_2.packet_kind is ElehantPacketKind.TWO_TARIFF_2
    assert tariff_2.channel is ElehantChannel.TARIFF_2
    assert tariff_2.temperature_celsius == 16.06
