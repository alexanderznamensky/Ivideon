"""Config flow for Ivideon integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import IvideonAPI
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)


def get_user_schema(data: Optional[Dict[str, Any]] = None) -> vol.Schema:
    """Get user configuration schema."""
    data = data or {}
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=data.get(CONF_EMAIL, "")): str,
            vol.Required(CONF_PASSWORD, default=data.get(CONF_PASSWORD, "")): str,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        }
    )


class IvideonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ivideon."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Test credentials
                api = IvideonAPI(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                )
                await api.login()

                # Set unique ID based on user_id
                await self.async_set_unique_id(api.user_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Ivideon ({user_input[CONF_EMAIL]})",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                        ),
                    },
                )

            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=get_user_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle reconfiguration of the integration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors = {}

        if user_input is not None:
            try:
                # Test credentials
                api = IvideonAPI(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                )
                await api.login()

                # Update entry
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                        ),
                    },
                )

                # Reload entry to apply new settings
                await self.hass.config_entries.async_reload(entry.entry_id)

                return self.async_abort(reason="reconfigure_successful")

            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_user_schema(entry.data),
            errors=errors,
            description_placeholders={
                "email": entry.data.get(CONF_EMAIL, ""),
            },
        )
