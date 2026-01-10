"""Data update coordinator for Ivideon."""
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IvideonAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IvideonDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching Ivideon data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: IvideonAPI,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from API."""
        try:
            return await self.api.get_data()
        except ConfigEntryAuthFailed as err:
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
