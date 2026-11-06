"""Persistent storage for Alexa Assistant."""
from __future__ import annotations

import logging
from typing import Any

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "alexa_assistant"
STORAGE_VERSION = 1


class AlexaAssistantStorage:
    """Manages persistent settings for Alexa Assistant."""

    def __init__(self, hass: Any) -> None:
        """Initialize storage manager."""
        self._hass = hass
        self._store: Any = None
        self._data: dict[str, Any] = {"excluded_default_names": []}
        self._loaded: bool = False

    async def async_load(self) -> None:
        """Load data from Home Assistant store."""
        if self._store is None:
            try:
                from homeassistant.helpers.storage import Store

                self._store = Store(self._hass, STORAGE_VERSION, STORAGE_KEY)
            except Exception as err:
                _LOGGER.debug("Could not initialize Store: %s", err)

        if self._store is not None:
            try:
                stored = await self._store.async_load()
                if isinstance(stored, dict):
                    self._data = stored
            except Exception as err:
                _LOGGER.debug("Could not load alexa_assistant storage: %s", err)
        self._loaded = True

    def is_default_name_excluded(self, entity_id: str) -> bool:
        """Check if an entity's default native name is excluded from Alexa."""
        excluded = self._data.get("excluded_default_names", [])
        if isinstance(excluded, list):
            return entity_id in excluded
        return False

    def get_excluded_default_names(self) -> list[str]:
        """Return list of entity IDs whose default name is excluded."""
        excluded = self._data.get("excluded_default_names", [])
        if isinstance(excluded, list):
            return list(excluded)
        return []

    async def async_set_default_name_excluded(self, entity_id: str, exclude: bool) -> None:
        """Set whether an entity's default name is excluded from Alexa."""
        raw = self._data.get("excluded_default_names", [])
        excluded: list[str] = list(raw) if isinstance(raw, list) else []

        if exclude and entity_id not in excluded:
            excluded.append(entity_id)
        elif not exclude and entity_id in excluded:
            excluded = [eid for eid in excluded if eid != entity_id]

        self._data["excluded_default_names"] = excluded

        if self._store is not None:
            try:
                await self._store.async_save(self._data)
            except Exception as err:
                _LOGGER.error("Failed to save alexa_assistant storage: %s", err)


def is_entity_default_name_excluded(hass: Any, entity_id: str) -> bool:
    """Return True if the entity's default name is excluded from Alexa."""
    data = getattr(hass, "data", None)
    if not isinstance(data, dict):
        return False
    domain_data = data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        return False
    storage = domain_data.get("storage")
    if storage is not None and hasattr(storage, "is_default_name_excluded"):
        return bool(storage.is_default_name_excluded(entity_id))
    return False
