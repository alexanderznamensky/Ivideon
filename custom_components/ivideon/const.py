"""Constants for the Ivideon integration."""
from datetime import timedelta

DOMAIN = "ivideon"

# Config
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_SCAN_INTERVAL_MINUTES = 60
DEFAULT_NAME = "Ivideon"

# API
OPENAPI_DEFAULT = "openapi-alpha-eu01.ivideon.com"
API4_DEFAULT = "eu01-api.ivideon.com"
AUTH_HOST = OPENAPI_DEFAULT
AUTH_PATH = "/auth/oauth/token"
AUTH_CLIENT_ID = "web-client"

CLIENT_VERSION = "61.0.1"
DEVICE_TYPE = "home-assistant"
DEVICE_INSTANCE_ID = "ha-integration"
TRUSTED_DEVICE = "true"

# Sensor types
SENSOR_BALANCE = "balance"
SENSOR_REAL_BALANCE = "real_balance"
SENSOR_BONUS_BALANCE = "bonus_balance"
SENSOR_NEXT_PAYMENT_DATE = "next_payment_date"
SENSOR_NEXT_PAYMENT_AMOUNT = "next_payment_amount"
SENSOR_CAMERAS_COUNT = "cameras_count"

# Attributes
ATTR_USER_ID = "user_id"
ATTR_CURRENCY = "currency"
ATTR_CAMERAS = "cameras"
ATTR_UPDATED = "last_updated"
