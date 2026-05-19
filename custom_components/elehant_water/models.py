"""Domain models for Elehant BLE readings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ElehantChannel(StrEnum):
    """A normalized Elehant reading channel."""

    VOLUME = "volume"
    TARIFF_1 = "tariff_1"
    TARIFF_2 = "tariff_2"
    TEMPERATURE = "temperature"


class ElehantPacketKind(StrEnum):
    """Known Elehant advertisement packet kinds."""

    SINGLE_TARIFF = "single_tariff"
    TWO_TARIFF_1 = "two_tariff_1"
    TWO_TARIFF_2 = "two_tariff_2"


@dataclass(frozen=True)
class ElehantReading:
    """A parsed Elehant advertisement reading."""

    meter_id: str
    channel: ElehantChannel
    raw_count: int
    packet_kind: ElehantPacketKind
    address: str
    rssi: int | None = None
    temperature_celsius: float | None = None
