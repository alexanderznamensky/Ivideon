"""Sensor platform for Ivideon."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_DOLLAR, CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_CAMERAS,
    ATTR_CURRENCY,
    ATTR_UPDATED,
    ATTR_USER_ID,
    DOMAIN,
    SENSOR_BALANCE,
    SENSOR_BONUS_BALANCE,
    SENSOR_CAMERAS_COUNT,
    SENSOR_NEXT_PAYMENT_AMOUNT,
    SENSOR_NEXT_PAYMENT_DATE,
    SENSOR_REAL_BALANCE,
)
from .coordinator import IvideonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CURRENCY_MAPPING = {
    "RUB": "RUB",
    "RUR": "RUB",
    "USD": CURRENCY_DOLLAR,
    "EUR": CURRENCY_EURO,
}

# Russian month names in genitive case (родительный падеж)
RUSSIAN_MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def day(num):
    last_two = num % 100
    last_digit = num % 10
    if last_two in range(11, 20) or last_digit == 0 or last_digit >= 5:
        return "дней"
    elif last_digit == 1:
        return "день"
    else:
        return "дня"


def normalize_currency(currency: Optional[str]) -> str:
    """Normalize currency code (RUR -> RUB)."""
    if not currency:
        return "RUB"
    return CURRENCY_MAPPING.get(currency.upper(), currency)


def _format_money(value: Any) -> Optional[float]:
    """Format a monetary value with 2 decimal places as float."""
    if value is None:
        return None

    try:
        return float(f"{float(value):.2f}")
    except (ValueError, TypeError):
        return None


def _format_balance(value: Any) -> Optional[float]:
    """Format Ivideon balance from kopecks to rubles with 2 decimal places."""
    if value is None:
        return None

    try:
        return float(f"{float(value) / 100.0:.2f}")
    except (ValueError, TypeError):
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ivideon sensors from a config entry."""
    coordinator: IvideonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        IvideonBalanceSensor(coordinator, entry),
        IvideonRealBalanceSensor(coordinator, entry),
        IvideonBonusBalanceSensor(coordinator, entry),
        IvideonNextPaymentDateSensor(coordinator, entry),
        IvideonNextPaymentAmountSensor(coordinator, entry),
        IvideonCamerasCountSensor(coordinator, entry),
    ]

    # Add individual camera sensors
    if coordinator.data:
        billing_data = coordinator.data.get("billing") or {}
        cameras = billing_data.get("cameras", [])
        
        for idx, camera in enumerate(cameras, start=1):
            entities.append(IvideonCameraSensor(coordinator, entry, camera, idx))

    async_add_entities(entities)


def format_russian_date(dt: datetime) -> str:
    """Format datetime in Russian format: '13 января 2026 г.'"""
    if not dt:
        return ""
    day = dt.day
    month = RUSSIAN_MONTHS.get(dt.month, "")
    year = dt.year
    return f"{day} {month} {year} г."


def get_days_until(target_date: datetime) -> int:
    """Calculate days until target date."""
    if not target_date:
        return 0
    
    now = dt_util.now()
    delta = target_date - now
    return max(0, delta.days)


class IvideonSensorBase(CoordinatorEntity[IvideonDataUpdateCoordinator], SensorEntity):
    """Base class for Ivideon sensors."""

    _attr_force_update = True

    def __init__(
        self,
        coordinator: IvideonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.api.user_id)},
            "name": "Ivideon",
            "manufacturer": "Ivideon",
            "model": "Cloud Camera Service",
        }
        self._entry = entry

    def _base_state_attributes(self) -> Dict[str, Any]:
        """Return base attributes common to all entities."""
        if not self.coordinator.data:
            return {}

        return {
            ATTR_UPDATED: self.coordinator.data.get("updated_at"),
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None


class IvideonCameraSensor(IvideonSensorBase):
    """Sensor for individual camera payment status."""

    def __init__(
        self,
        coordinator: IvideonDataUpdateCoordinator,
        entry: ConfigEntry,
        camera_data: Dict[str, Any],
        camera_index: int,
    ) -> None:
        """Initialize the camera sensor."""
        super().__init__(coordinator, entry)
        self._camera_id = camera_data.get("camera_id")
        self._camera_index = camera_index
        self._camera_name = camera_data.get("camera_name", f"Камера {camera_index}")
        self._attr_unique_id = f"{coordinator.api.user_id}_camera_{self._camera_id}"
        # self._attr_name = f"Ivideon {camera_index}"
        self._attr_name = self._camera_name
        self._attr_icon = "mdi:camera"
        self._attr_entity_category = None

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        camera = self._get_camera_data()
        if not camera:
            return None

        expires_iso = camera.get("expires_iso")
        if not expires_iso:
            return "Нет данных"

        try:
            expires_dt = datetime.fromisoformat(expires_iso.replace("Z", "+00:00"))
            return f"оплачен до {format_russian_date(expires_dt)}"
        except (ValueError, AttributeError):
            return "Ошибка даты"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        camera = self._get_camera_data()
        if not camera:
            return {}

        expires_iso = camera.get("expires_iso")
        expires_dt = None
        due_date_str = ""
        days_left = 0
        message = ""

        if expires_iso:
            try:
                expires_dt = datetime.fromisoformat(expires_iso.replace("Z", "+00:00"))
                due_date_str = expires_dt.strftime("%d.%m.%Y")
                days_left = get_days_until(expires_dt)
                
                camera_name = camera.get("camera_name", "Камера")
                word = day(days_left)
                
                if days_left == 0:
                    message = f"Сегодня срок оплаты Ivideon / {camera_name}."
                elif days_left == 1:
                    message = f"Завтра срок оплаты Ivideon / {camera_name}."
                elif days_left <= 5:
                    message = f"Через {days_left} {word} нужно оплатить Ivideon / {camera_name}."
                elif days_left > 5:
                    message = f"Все в порядке! Оплачивать Ivideon / {camera_name} нужно через {days_left} {word}."
                else:
                    message = f"Просрочена оплата Ivideon / {camera_name}!!!"

            except (ValueError, AttributeError):
                pass

        return {
            **self._base_state_attributes(),
            "camera_name": camera.get("camera_name"),
            "camera_id": camera.get("camera_id"),
            "due_date": due_date_str,
            "message": message,
            "days_left": days_left,
            "price": _format_money(camera.get("cost")),
            "currency": normalize_currency(camera.get("currency")),
            "tariff_name": camera.get("tariff_name"),
            "tariff_id": camera.get("tariff_id"),
            "period": camera.get("period"),
            "payment_type": camera.get("payment_type"),
            "active": camera.get("active"),
            "expired": camera.get("expired"),
            "start_date": camera.get("start_iso"),
            "expires_date": expires_iso,
            "last_updated": self.coordinator.data.get("updated_at"),
        }

    def _get_camera_data(self) -> Optional[Dict[str, Any]]:
        """Get camera data from coordinator."""
        if not self.coordinator.data:
            return None

        billing_data = self.coordinator.data.get("billing") or {}
        cameras = billing_data.get("cameras", [])

        # Find camera by ID
        for camera in cameras:
            if camera.get("camera_id") == self._camera_id:
                return camera

        return None


class IvideonBalanceSensor(IvideonSensorBase):
    """Sensor for total balance."""

    _attr_name = "Balance"
    _attr_icon = "mdi:wallet"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: IvideonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{coordinator.api.user_id}_{SENSOR_BALANCE}"

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        balance_data = self.coordinator.data.get("balance") or {}
        response = balance_data.get("response") or {}
        balance = response.get("balance")

        if balance is None:
            return None

        return _format_balance(balance)

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement."""
        if not self.coordinator.data:
            return None

        balance_data = self.coordinator.data.get("balance") or {}
        response = balance_data.get("response") or {}
        currency = response.get("currency", "RUB")
        return CURRENCY_MAPPING.get(currency, currency)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        balance_data = self.coordinator.data.get("balance") or {}
        response = balance_data.get("response") or {}

        return {
            **self._base_state_attributes(),
            ATTR_USER_ID: self.coordinator.data.get("user_id"),
            "success": balance_data.get("success"),
            "balance": _format_balance(response.get("balance")),
            "real_balance": _format_balance(response.get("real_balance")),
            "bonus_balance": _format_balance(response.get("bonus_balance")),
            "currency": normalize_currency(response.get("currency")),
            "credit_limit": _format_balance(response.get("credit_limit")),
            "locked_balance": _format_balance(response.get("locked_balance")),
            ATTR_UPDATED: self.coordinator.data.get("updated_at"),
        }


class IvideonRealBalanceSensor(IvideonSensorBase):
    """Sensor for real balance (without bonuses)."""

    _attr_name = "Real Balance"
    _attr_icon = "mdi:cash"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IvideonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{coordinator.api.user_id}_{SENSOR_REAL_BALANCE}"

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        balance_data = self.coordinator.data.get("balance") or {}
        response = balance_data.get("response") or {}
        real_balance = response.get("real_balance")

        if real_balance is None:
            return None

        return _format_balance(real_balance)

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement."""
        if not self.coordinator.data:
            return None

        balance_data = self.coordinator.data.get("balance") or {}
        response = balance_data.get("response") or {}
        currency = response.get("currency", "RUB")
        return CURRENCY_MAPPING.get(currency, currency)


class IvideonBonusBalanceSensor(IvideonSensorBase):
    """Sensor for bonus balance."""

    _attr_name = "Bonus Balance"
    _attr_icon = "mdi:gift"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IvideonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{coordinator.api.user_id}_{SENSOR_BONUS_BALANCE}"

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        balance_data = self.coordinator.data.get("balance") or {}
        response = balance_data.get("response") or {}
        bonus_balance = response.get("bonus_balance")

        if bonus_balance is None:
            return None

        return _format_balance(bonus_balance)

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement."""
        if not self.coordinator.data:
            return None

        balance_data = self.coordinator.data.get("balance") or {}
        response = balance_data.get("response") or {}
        currency = response.get("currency", "RUB")
        return CURRENCY_MAPPING.get(currency, currency)


class IvideonNextPaymentDateSensor(IvideonSensorBase):
    """Sensor for next payment date."""

    _attr_name = "Next Payment Date"
    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: IvideonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{coordinator.api.user_id}_{SENSOR_NEXT_PAYMENT_DATE}"

    @property
    def native_value(self) -> Optional[datetime]:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        billing_data = self.coordinator.data.get("billing") or {}
        date_str = billing_data.get("nearest_payment_date")

        if not date_str:
            return None

        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        billing_data = self.coordinator.data.get("billing") or {}

        return {
            **self._base_state_attributes(),
            ATTR_CAMERAS: billing_data.get("cameras_count", 0),
            ATTR_CURRENCY: normalize_currency(billing_data.get("currency")),
        }


class IvideonNextPaymentAmountSensor(IvideonSensorBase):
    """Sensor for next payment amount."""

    _attr_name = "Next Payment Amount"
    _attr_icon = "mdi:cash-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: IvideonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{coordinator.api.user_id}_{SENSOR_NEXT_PAYMENT_AMOUNT}"

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        billing_data = self.coordinator.data.get("billing") or {}
        amount = billing_data.get("nearest_payment_amount_total")

        if amount is None:
            return None

        return _format_money(amount)

    @property
    def native_unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement."""
        if not self.coordinator.data:
            return None

        billing_data = self.coordinator.data.get("billing") or {}
        currency = billing_data.get("currency", "RUB")
        return CURRENCY_MAPPING.get(currency, currency)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        billing_data = self.coordinator.data.get("billing") or {}
        cameras = billing_data.get("cameras", [])

        # Get cameras that expire on next payment date
        next_date = billing_data.get("nearest_payment_date")
        cameras_due = [
            {
                "name": cam.get("camera_name"),
                "tariff": cam.get("tariff_name"),
                "cost": _format_money(cam.get("cost")),
            }
            for cam in cameras
            if cam.get("expires_iso") == next_date
        ]

        return {
            **self._base_state_attributes(),
            ATTR_CAMERAS: cameras_due,
            ATTR_CURRENCY: normalize_currency(billing_data.get("currency")),
        }


class IvideonCamerasCountSensor(IvideonSensorBase):
    """Sensor for total cameras count."""

    _attr_name = "Cameras Count"
    _attr_icon = "mdi:camera-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IvideonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{coordinator.api.user_id}_{SENSOR_CAMERAS_COUNT}"

    @property
    def native_value(self) -> Optional[int]:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        billing_data = self.coordinator.data.get("billing") or {}
        return billing_data.get("cameras_count", 0)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}

        billing_data = self.coordinator.data.get("billing") or {}
        cameras = billing_data.get("cameras", [])

        return {
            **self._base_state_attributes(),
            ATTR_CAMERAS: [
                {
                    "name": cam.get("camera_name"),
                    "id": cam.get("camera_id"),
                    "tariff": cam.get("tariff_name"),
                    "expires": cam.get("expires_iso"),
                    "cost": _format_money(cam.get("cost")),
                    "active": cam.get("active"),
                    "expired": cam.get("expired"),
                }
                for cam in cameras
            ]
        }
