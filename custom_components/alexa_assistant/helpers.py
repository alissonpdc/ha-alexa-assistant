"""Helper utilities for sanitization and alias handling in Alexa Assistant."""
from __future__ import annotations

import copy
import re
from typing import Any

MAX_ALEXA_ALIASES: int = 5


def sanitize_alexa_name(name: str | None) -> str:
    """Sanitize name for Alexa: only letters, numbers, and single spaces.

    Example:
        sanitized = sanitize_alexa_name("Luz Sala (Teto)")
    """
    if not name:
        return ""
    # Strip underscores and any non-alphanumeric non-space character
    cleaned = re.sub(r"[^\w\s]|_", " ", str(name))
    return re.sub(r"\s+", " ", cleaned).strip()


def build_alias_endpoint(
    base_endpoint: dict[str, Any],
    alias: str,
    alias_index: int,
) -> dict[str, Any]:
    """Clone an endpoint dictionary for an alias with sanitized friendlyName.

    Example:
        alias_ep = build_alias_endpoint(base_ep, "Luz de Teto", 1)
    """
    sanitized_alias = sanitize_alexa_name(alias)
    alias_ep = copy.deepcopy(base_endpoint)
    base_id = base_endpoint.get("endpointId", "unknown")
    alias_ep["endpointId"] = f"{base_id}__alias_{alias_index}"
    alias_ep["friendlyName"] = sanitized_alias
    alias_ep["description"] = f"{sanitized_alias} via Home Assistant"
    return alias_ep


def get_entity_registry(hass: Any) -> Any:
    """Safely obtain entity registry helper.

    Example:
        registry = get_entity_registry(hass)
    """
    try:
        from homeassistant.helpers import entity_registry as er

        return er.async_get(hass)
    except Exception:
        return None


def get_entity_alexa_aliases(
    hass: Any,
    entity_id: str,
    max_aliases: int = MAX_ALEXA_ALIASES,
) -> list[str]:
    """Return up to max_aliases sanitized aliases for an entity.

    Example:
        aliases = get_entity_alexa_aliases(hass, "light.sala")
    """
    registry = get_entity_registry(hass)
    if registry is None:
        return []

    entry = registry.async_get(entity_id)
    if entry is None:
        return []

    raw_candidates: list[Any] = []
    if getattr(entry, "aliases_v2", None):
        raw_candidates.extend(entry.aliases_v2)
    if getattr(entry, "aliases", None):
        raw_candidates.extend(entry.aliases)

    result: list[str] = []
    for raw_alias in raw_candidates:
        if not isinstance(raw_alias, str) or not raw_alias.strip():
            continue
        cleaned = sanitize_alexa_name(raw_alias)
        if cleaned and cleaned not in result:
            result.append(cleaned)
        if len(result) >= max_aliases:
            break

    return result
