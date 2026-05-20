"""Constants for the Elehant Water integration."""

from __future__ import annotations

DOMAIN = "elehant_water"

CONF_CHANNELS = "channels"
CONF_DEVICE_CLASS = "device_class"
CONF_ENABLED = "enabled"
CONF_ID_SOURCE = "id_source"
CONF_IDENTITY_EVIDENCE = "identity_evidence"
CONF_LEGACY_ID = "legacy_id"
CONF_LEGACY_METER_ID = "legacy_meter_id"
CONF_MEASUREMENT = "measurement"
CONF_METERS = "meters"
CONF_METER_ID = "meter_id"
CONF_NAME_TEMP = "name_temp"
CONF_CHANNEL = "channel"
CONF_AVAILABILITY_ENABLED = "availability_enabled"
CONF_AVAILABILITY_TIMEOUT_MINUTES = "availability_timeout_minutes"
CONF_MEASUREMENT_GAS = "measurement_gas"
CONF_MEASUREMENT_WATER = "measurement_water"
CONF_STATE_CLASS = "state_class"
CONF_TYPE = "type"
CONF_WATER_TYPE = "water_type"
CONF_IMPORT_YAML = "import_yaml"
DATA_LEGACY_YAML_CONFIG = "legacy_yaml_config"

DEFAULT_AVAILABILITY_TIMEOUT_MINUTES = 60
DEFAULT_DISCOVERY_CANDIDATE_TTL_SECONDS = 30 * 60
DEFAULT_NEVER_SEEN_REPAIR_GRACE_SECONDS = 60 * 60
MAX_UNKNOWN_PACKETS = 100

CHANNEL_VOLUME = "volume"
CHANNEL_TARIFF_1 = "tariff_1"
CHANNEL_TARIFF_2 = "tariff_2"
CHANNEL_TOTAL = "total"
CHANNEL_TEMPERATURE = "temperature"
DIAGNOSTIC_LAST_SEEN = "last_seen"
DIAGNOSTIC_RSSI = "rssi"
DIAGNOSTIC_PACKET_COUNT = "packet_count"
DIAGNOSTIC_MATCHED_BY = "matched_by"

MATCHED_BY_MANUFACTURER = "manufacturer"
MATCHED_BY_ADDRESS = "address"
MATCHED_BY_ALIAS = "alias"
MATCHED_BY_CONFIGURED = "configured"

DEVICE_CLASS_WATER = "water"
DEVICE_CLASS_TEMPERATURE = "temperature"

MEASUREMENT_LITERS = "l"
MEASUREMENT_CUBIC_METERS = "m3"
MEASUREMENT_CELSIUS = "celsius"

MANUFACTURER_ELEHANT_FALLBACK = "Elehant"

ID_SOURCE_YAML = "yaml"
ID_SOURCE_MANUAL = "manual"
ID_SOURCE_DISCOVERY = "discovery"
ID_SOURCE_MANUFACTURER = "manufacturer"
ID_SOURCE_ADDRESS = "address"
ID_SOURCE_MANUFACTURER_OR_ADDRESS = "manufacturer_or_address"

IDENTITY_EVIDENCE_MANUFACTURER_METER_ID = "manufacturer_meter_id"
IDENTITY_EVIDENCE_ADDRESS_METER_ID = "address_meter_id"
IDENTITY_EVIDENCE_MATCHED_BY = "matched_by"

STATE_CLASS_MEASUREMENT = "measurement"
STATE_CLASS_TOTAL_INCREASING = "total_increasing"
