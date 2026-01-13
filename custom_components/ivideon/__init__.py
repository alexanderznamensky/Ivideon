"""The Ivideon integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .api import IvideonAPI
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
from .coordinator import IvideonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_UPDATE = "update"


async def async_handle_update_service(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the update service call."""
    _LOGGER.debug("Update service called")
    
    # Update all Ivideon coordinators
    for entry_id, coordinator in hass.data[DOMAIN].items():
        if isinstance(coordinator, IvideonDataUpdateCoordinator):
            _LOGGER.debug("Requesting refresh for entry %s", entry_id)
            await coordinator.async_request_refresh()


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

    # Register update service (only once for the domain)
    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_UPDATE,
            async_handle_update_service,
            schema=vol.Schema({}),
        )
        _LOGGER.debug("Registered %s.%s service", DOMAIN, SERVICE_UPDATE)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
