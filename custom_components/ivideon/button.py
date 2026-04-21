"""Button platform for Ivideon."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IvideonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ivideon button from a config entry."""
    coordinator: IvideonDataUpdateCoordinator = entry.runtime_data or hass.data[DOMAIN][
        entry.entry_id
    ]

    async_add_entities([IvideonManualRefreshButton(coordinator)])


class IvideonManualRefreshButton(
    CoordinatorEntity[IvideonDataUpdateCoordinator], ButtonEntity
):
    """Button to manually refresh Ivideon data."""

    _attr_name = "Обновить Ivideon"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IvideonDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.api.user_id}_manual_refresh"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.api.user_id)},
            "name": "Ivideon",
            "manufacturer": "Ivideon",
            "model": "Cloud Camera Service",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_request_refresh()
