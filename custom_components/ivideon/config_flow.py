"""Config flow for Ivideon integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlowWithReload
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import IvideonAPI
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)


def get_user_schema(data: dict[str, Any] | None = None) -> vol.Schema:
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


def get_options_schema(options: dict[str, Any] | None = None) -> vol.Schema:
    """Get options schema."""
    options = options or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        }
    )


class IvideonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ivideon."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return IvideonOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api = IvideonAPI(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                )
                await api.login()

                await self.async_set_unique_id(api.user_id)
                self._abort_if_unique_id_configured()

                scan_interval = user_input.get(
                    CONF_SCAN_INTERVAL,
                    DEFAULT_SCAN_INTERVAL_MINUTES,
                )

                return self.async_create_entry(
                    title=f"Ivideon ({user_input[CONF_EMAIL]})",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={CONF_SCAN_INTERVAL: scan_interval},
                )

            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pragma: no cover - defensive
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=get_user_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of the integration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}
        current_data = {
            CONF_EMAIL: entry.data.get(CONF_EMAIL, ""),
            CONF_PASSWORD: entry.data.get(CONF_PASSWORD, ""),
            CONF_SCAN_INTERVAL: entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
            ),
        }

        if user_input is not None:
            try:
                api = IvideonAPI(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                )
                await api.login()

                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        **entry.options,
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL,
                            DEFAULT_SCAN_INTERVAL_MINUTES,
                        ),
                    },
                )

                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pragma: no cover - defensive
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_user_schema(current_data),
            errors=errors,
            description_placeholders={
                "email": entry.data.get(CONF_EMAIL, ""),
            },
        )


class IvideonOptionsFlow(OptionsFlowWithReload):
    """Handle Ivideon options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(
                CONF_SCAN_INTERVAL,
                DEFAULT_SCAN_INTERVAL_MINUTES,
            ),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=get_options_schema(
                {CONF_SCAN_INTERVAL: current_interval}
            ),
        )
