"""The Ivideon integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import IvideonAPI
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
from .coordinator import IvideonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ivideon from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create API client
    api = IvideonAPI(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )

    # Test authentication
    try:
        await api.ensure_auth()
    except ConfigEntryAuthFailed as err:
        raise ConfigEntryAuthFailed from err
    except Exception as err:
        _LOGGER.error("Failed to authenticate with Ivideon: %s", err)
        return False

    # Get scan interval from config (in minutes)
    scan_interval_minutes = entry.data.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
    )
    scan_interval = timedelta(minutes=scan_interval_minutes)

    # Create coordinator
    coordinator = IvideonDataUpdateCoordinator(hass, api, scan_interval)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
