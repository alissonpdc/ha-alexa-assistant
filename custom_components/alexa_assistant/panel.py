"""Custom panel registration for Alexa Assistant."""
import logging
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

PANEL_URL_PATH = "alexa-assistant"
PANEL_NAME = "alexa-assistant-panel"
PANEL_TITLE = "Alexa"
PANEL_ICON = "mdi:speaker-message"
FRONTEND_URL = "/alexa_assistant_panel"


async def async_register_alexa_panel(hass: Any) -> None:
    """Register Alexa panel and static paths with Home Assistant.

    Example:
        await async_register_alexa_panel(hass)
    """
    frontend_dir = Path(__file__).parent / "frontend"

    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths([
            StaticPathConfig(
                url_path=FRONTEND_URL,
                path=str(frontend_dir),
                cache_headers=False,
            )
        ])
    except Exception as err:
        _LOGGER.debug("Could not register static path: %s", err)

    try:
        from homeassistant.components.panel_custom import async_register_panel

        await async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name=PANEL_NAME,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            module_url=f"{FRONTEND_URL}/panel.js",
            require_admin=False,
        )
        _LOGGER.info("Registered Alexa Assistant panel in sidebar")
    except Exception as err:
        _LOGGER.warning("Could not register custom panel: %s", err)


async def async_unregister_alexa_panel(hass: Any) -> None:
    """Remove Alexa panel from sidebar.

    Example:
        await async_unregister_alexa_panel(hass)
    """
    try:
        from homeassistant.components.frontend import async_remove_panel

        async_remove_panel(hass, PANEL_URL_PATH)
        _LOGGER.info("Removed Alexa Assistant panel from sidebar")
    except Exception as err:
        _LOGGER.debug("Could not remove custom panel: %s", err)
