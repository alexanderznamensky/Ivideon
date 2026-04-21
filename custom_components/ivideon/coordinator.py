"""Data update coordinator for Ivideon."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IvideonAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IvideonDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Ivideon data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: IvideonAPI,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            return await self.api.get_data()
        except ConfigEntryAuthFailed as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
