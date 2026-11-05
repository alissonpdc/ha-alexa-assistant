"""Tests for integration initialization."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.alexa_native_expose import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.alexa_native_expose.const import DOMAIN


async def test_async_setup_returns_true():
    """Verify async_setup initializes cleanly."""
    hass = MagicMock()
    result = await async_setup(hass, {})
    assert result is True


async def test_async_setup_entry_patches_and_stores_manager():
    """Verify async_setup_entry creates manager and attaches patch."""
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock()
    entry.entry_id = "test_entry_123"

    with patch(
        "custom_components.alexa_native_expose.NativeAlexaExposeManager"
    ) as mock_manager_cls:
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert DOMAIN in hass.data
        assert hass.data[DOMAIN][entry.entry_id] is mock_manager
        mock_manager.start_listening.assert_called_once()


async def test_async_unload_entry_cleans_up_manager():
    """Verify async_unload_entry stops listening and removes manager."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_123"

    mock_manager = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: mock_manager}}

    result = await async_unload_entry(hass, entry)

    assert result is True
    assert entry.entry_id not in hass.data[DOMAIN]
    mock_manager.stop_listening.assert_called_once()
