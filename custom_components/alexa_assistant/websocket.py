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

from .const import DOMAIN
from .helpers import get_entity_alexa_aliases, get_entity_registry, sanitize_alexa_name
from .storage import is_entity_default_name_excluded

_LOGGER = logging.getLogger(__name__)

WS_TYPE_GET_ALIASES = "alexa_assistant/aliases"
WS_TYPE_UPDATE_ALIASES = "alexa_assistant/update_aliases"


@callback
def ws_get_aliases(
    hass: Any,
    connection: Any,
    msg: dict[str, Any],
) -> None:
    """Return all configured Alexa voice aliases mapped by entity_id.

    Example WS response:
        {"id": 1, "type": "result", "success": true, "result": {"light.sala": {"aliases": ["Spot"], "exclude_default_name": false}}}
    """
    registry = get_entity_registry(hass)
    storage = hass.data.get(DOMAIN, {}).get("storage")
    result: dict[str, dict[str, Any]] = {}

    if registry is not None:
        for entity_id in getattr(registry, "entities", []):
            aliases = get_entity_alexa_aliases(hass, entity_id)
            is_excluded = is_entity_default_name_excluded(hass, entity_id)
            if aliases or is_excluded:
                result[entity_id] = {
                    "aliases": aliases,
                    "exclude_default_name": is_excluded,
                }

    connection.send_result(msg["id"], result)


async def ws_update_aliases(
    hass: Any,
    connection: Any,
    msg: dict[str, Any],
) -> None:
    """Update aliases and default name exclusion for an entity.

    Example WS request:
        {"id": 2, "type": "alexa_assistant/update_aliases", "entity_id": "light.sala", "aliases": ["Spot"], "exclude_default_name": true}
    """
    entity_id = msg.get("entity_id")
    aliases_raw = msg.get("aliases", [])
    exclude_default = bool(msg.get("exclude_default_name", False))

    if not entity_id or not isinstance(entity_id, str):
        connection.send_error(msg["id"], "invalid_format", "Missing entity_id")
        return

    if not isinstance(aliases_raw, list):
        connection.send_error(msg["id"], "invalid_format", "Aliases must be a list")
        return

    # Sanitize aliases
    sanitized_aliases: list[str] = []
    for a in aliases_raw:
        cleaned = sanitize_alexa_name(str(a) if a is not None else "")
        if cleaned and cleaned not in sanitized_aliases:
            sanitized_aliases.append(cleaned)

    # Validation: cannot remove the only voice name
    if exclude_default and len(sanitized_aliases) == 0:
        connection.send_error(msg["id"], "invalid_data", "Não é possível remover o único nome.")
        return

    # 1. Update persistent storage for exclude_default_name
    storage = hass.data.get(DOMAIN, {}).get("storage")
    if storage is not None:
        await storage.async_set_default_name_excluded(entity_id, exclude_default)

    # 2. Update Home Assistant EntityRegistry aliases
    registry = get_entity_registry(hass)
    if registry is not None and hasattr(registry, "async_update_entity"):
        try:
            registry.async_update_entity(entity_id, aliases=sanitized_aliases)
        except Exception as err:
            _LOGGER.warning("Could not update entity_registry aliases for %s: %s", entity_id, err)

    connection.send_result(
        msg["id"],
        {
            "success": True,
            "entity_id": entity_id,
            "aliases": sanitized_aliases,
            "exclude_default_name": exclude_default,
        },
    )


def async_register_websocket_commands(hass: Any) -> None:
    """Register custom websocket commands for Alexa Assistant.

    Example:
        async_register_websocket_commands(hass)
    """
    if websocket_api is None:
        return

    try:
        cmd_get = websocket_api.websocket_command({
            "type": WS_TYPE_GET_ALIASES,
        })(ws_get_aliases)
        websocket_api.async_register_command(hass, cmd_get)
        _LOGGER.debug("Registered Alexa Assistant websocket command: %s", WS_TYPE_GET_ALIASES)
    except Exception as err:
        _LOGGER.debug("Could not register %s: %s", WS_TYPE_GET_ALIASES, err)

    try:
        cmd_update = websocket_api.websocket_command({
            "type": WS_TYPE_UPDATE_ALIASES,
            "entity_id": str,
            "aliases": list,
            "exclude_default_name": bool,
        })(websocket_api.async_response(ws_update_aliases) if hasattr(websocket_api, "async_response") else ws_update_aliases)
        websocket_api.async_register_command(hass, cmd_update)
        _LOGGER.debug("Registered Alexa Assistant websocket command: %s", WS_TYPE_UPDATE_ALIASES)
    except Exception as err:
        _LOGGER.debug("Could not register %s: %s", WS_TYPE_UPDATE_ALIASES, err)
