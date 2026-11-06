"""WebSocket API handlers for Alexa Assistant."""
from __future__ import annotations

import logging
from typing import Any

try:
    from homeassistant.components import websocket_api
    from homeassistant.core import HomeAssistant, callback
    from homeassistant.helpers import entity_registry as er
except ImportError:
    websocket_api = None
    HomeAssistant = object
    callback = lambda f: f
    er = None

from .helpers import get_entity_alexa_aliases, get_entity_registry

_LOGGER = logging.getLogger(__name__)

WS_TYPE_GET_ALIASES = "alexa_assistant/aliases"


@callback
def ws_get_aliases(
    hass: Any,
    connection: Any,
    msg: dict[str, Any],
) -> None:
    """Return all configured Alexa voice aliases mapped by entity_id.

    Example WS response:
        {"id": 1, "type": "result", "success": true, "result": {"light.sala": ["Luz Sala", "Spot"]}}
    """
    registry = get_entity_registry(hass)
    result: dict[str, list[str]] = {}

    if registry is not None:
        for entity_id in getattr(registry, "entities", []):
            aliases = get_entity_alexa_aliases(hass, entity_id)
            if aliases:
                result[entity_id] = aliases

    connection.send_result(msg["id"], result)


def async_register_websocket_commands(hass: Any) -> None:
    """Register custom websocket commands for Alexa Assistant.

    Example:
        async_register_websocket_commands(hass)
    """
    if websocket_api is None:
        return

    try:
        command = websocket_api.websocket_command({
            "type": WS_TYPE_GET_ALIASES,
        })(ws_get_aliases)
        websocket_api.async_register_command(hass, command)
        _LOGGER.debug("Registered Alexa Assistant websocket command: %s", WS_TYPE_GET_ALIASES)
    except Exception as err:
        _LOGGER.debug("Could not register websocket command: %s", err)
