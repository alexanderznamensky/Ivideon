"""The Ivideon integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import IvideonAPI
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
from .coordinator import IvideonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_UPDATE: Final = "update"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Ivideon component."""
    
    async def handle_update_service(call: ServiceCall) -> None:
        """Handle the update service call."""
        _LOGGER.debug("Update service called")
        
        # Check if domain data exists
        if DOMAIN not in hass.data:
            _LOGGER.warning("No Ivideon integrations configured")
            return
        
        # Update all Ivideon coordinators
        updated_count = 0
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if isinstance(coordinator, IvideonDataUpdateCoordinator):
                try:
                    _LOGGER.debug("Requesting refresh for entry %s", entry_id)
                    await coordinator.async_request_refresh()
                    updated_count += 1
                except Exception as err:
                    _LOGGER.error("Failed to update entry %s: %s", entry_id, err)
        
        if updated_count > 0:
            _LOGGER.info("Successfully requested update for %d Ivideon integration(s)", updated_count)
        else:
            _LOGGER.warning("No Ivideon coordinators found to update")
    
    # Register the update service
    hass.services.async_register(DOMAIN, SERVICE_UPDATE, handle_update_service)
    _LOGGER.info("Registered %s.%s service", DOMAIN, SERVICE_UPDATE)
    
    return True


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
