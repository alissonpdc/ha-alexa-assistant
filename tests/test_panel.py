"""Tests for custom panel registration and unregistration."""
import sys
from types import ModuleType
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.alexa_assistant.panel import (
    async_register_alexa_panel,
    async_unregister_alexa_panel,
)


@pytest.fixture(autouse=True)
def setup_mock_ha_modules():
    """Setup mock homeassistant modules in sys.modules."""
    mock_ha = ModuleType("homeassistant")
    mock_ha_comp = ModuleType("homeassistant.components")
    mock_panel_custom = ModuleType("homeassistant.components.panel_custom")
    mock_frontend = ModuleType("homeassistant.components.frontend")
    mock_http = ModuleType("homeassistant.components.http")

    mock_panel_custom.async_register_panel = AsyncMock()
    mock_frontend.async_remove_panel = MagicMock()
    mock_http.StaticPathConfig = MagicMock()

    sys.modules["homeassistant"] = mock_ha
    sys.modules["homeassistant.components"] = mock_ha_comp
    sys.modules["homeassistant.components.panel_custom"] = mock_panel_custom
    sys.modules["homeassistant.components.frontend"] = mock_frontend
    sys.modules["homeassistant.components.http"] = mock_http

    yield {
        "panel_custom": mock_panel_custom,
        "frontend": mock_frontend,
        "http": mock_http,
    }

    sys.modules.pop("homeassistant", None)
    sys.modules.pop("homeassistant.components", None)
    sys.modules.pop("homeassistant.components.panel_custom", None)
    sys.modules.pop("homeassistant.components.frontend", None)
    sys.modules.pop("homeassistant.components.http", None)


async def test_async_register_alexa_panel_registers_paths_and_panel(setup_mock_ha_modules):
    """Verify panel registration adds static paths and registers panel."""
    hass = MagicMock()
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    mock_reg = setup_mock_ha_modules["panel_custom"].async_register_panel

    await async_register_alexa_panel(hass)
    hass.http.async_register_static_paths.assert_called_once()
    mock_reg.assert_called_once()
    assert mock_reg.call_args[1]["frontend_url_path"] == "alexa-assistant"
    assert mock_reg.call_args[1]["sidebar_title"] == "Alexa"
    assert mock_reg.call_args[1]["sidebar_icon"] == "mdi:speaker-message"


def test_panel_js_contains_refined_ux_model():
    """Verify panel.js includes Model 3 elements and Home Assistant theme adaptation."""
    from pathlib import Path

    js_path = Path(__file__).parent.parent / "custom_components" / "alexa_assistant" / "frontend" / "panel.js"
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    # Assert new UX elements
    assert "area-sidebar" in content
    assert "filter-card" in content
    assert "setScopeExposure" in content
    assert "room-exposure-toggle-group" in content
    assert "data-btn-add-entity-id" in content

    # Assert Home Assistant theme variables for light/dark mode adaptation
    assert "var(--ha-card-background" in content
    assert "var(--card-background-color" in content
    assert "var(--primary-background-color" in content
    assert "var(--primary-text-color" in content
    assert "var(--secondary-text-color" in content
    assert "var(--divider-color" in content

    # Assert dynamic device types filtered by active area
    assert "areaScopedEntities" in content


async def test_async_unregister_alexa_panel_removes_panel(setup_mock_ha_modules):
    """Verify panel unregistration removes panel from frontend."""
    hass = MagicMock()
    mock_remove = setup_mock_ha_modules["frontend"].async_remove_panel

    await async_unregister_alexa_panel(hass)
    mock_remove.assert_called_once_with(hass, "alexa-assistant")
