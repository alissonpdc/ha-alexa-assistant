"""Tests for integration initialization."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.alexa_assistant import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.alexa_assistant.const import DOMAIN


async def test_async_setup_returns_true():
    """Verify async_setup initializes cleanly."""
    hass = MagicMock()
    result = await async_setup(hass, {})
    assert result is True


async def test_async_setup_entry_patches_and_stores_manager():
    """Verify async_setup_entry creates manager, attaches patch and registers panel."""
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock()
    entry.entry_id = "test_entry_123"

    with patch(
        "custom_components.alexa_assistant.NativeAlexaExposeManager"
    ) as mock_manager_cls, patch(
        "custom_components.alexa_assistant.async_register_alexa_panel"
    ) as mock_register_panel:
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert DOMAIN in hass.data
        assert hass.data[DOMAIN][entry.entry_id] is mock_manager
        mock_manager.start_listening.assert_called_once()
        mock_manager.patch_discovery_and_directives.assert_called_once()
        mock_register_panel.assert_awaited_once_with(hass)


async def test_async_unload_entry_cleans_up_manager():
    """Verify async_unload_entry stops listening, removes manager and panel."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_123"

    mock_manager = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: mock_manager}}

    with patch(
        "custom_components.alexa_assistant.async_unregister_alexa_panel"
    ) as mock_unregister_panel:
        result = await async_unload_entry(hass, entry)

        assert result is True
        assert entry.entry_id not in hass.data[DOMAIN]
        mock_manager.stop_listening.assert_called_once()
        mock_manager.unpatch_discovery_and_directives.assert_called_once()
        mock_unregister_panel.assert_awaited_once_with(hass)
