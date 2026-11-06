"""Tests for Alexa Assistant storage."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.alexa_assistant.const import DOMAIN
from custom_components.alexa_assistant.storage import (
    AlexaAssistantStorage,
    is_entity_default_name_excluded,
)


@pytest.mark.asyncio
async def test_storage_loads_and_manages_excluded_default_names():
    """Verify AlexaAssistantStorage tracks and persists excluded default names."""
    hass = MagicMock()
    storage = AlexaAssistantStorage(hass)

    mock_store = MagicMock()
    mock_store.async_load = AsyncMock(return_value={"excluded_default_names": ["light.sala"]})
    mock_store.async_save = AsyncMock()
    storage._store = mock_store

    await storage.async_load()
    assert storage.is_default_name_excluded("light.sala") is True
    assert storage.is_default_name_excluded("light.quarto") is False

    # Exclude light.quarto
    await storage.async_set_default_name_excluded("light.quarto", True)
    assert storage.is_default_name_excluded("light.quarto") is True
    mock_store.async_save.assert_awaited()

    # Re-include light.sala
    await storage.async_set_default_name_excluded("light.sala", False)
    assert storage.is_default_name_excluded("light.sala") is False


def test_is_entity_default_name_excluded_helper():
    """Verify is_entity_default_name_excluded helper function."""
    hass = MagicMock()
    mock_storage = MagicMock()
    mock_storage.is_default_name_excluded.return_value = True
    hass.data = {DOMAIN: {"storage": mock_storage}}

    assert is_entity_default_name_excluded(hass, "light.teste") is True
    mock_storage.is_default_name_excluded.assert_called_once_with("light.teste")

    # If storage is missing, returns False
    hass.data = {}
    assert is_entity_default_name_excluded(hass, "light.teste") is False
