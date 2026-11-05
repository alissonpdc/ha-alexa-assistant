"""Tests for Alexa Native Expose."""
import pytest
from unittest.mock import MagicMock, patch

from custom_components.alexa_native_expose.const import DOMAIN, ASSISTANT_ALEXA
from custom_components.alexa_native_expose.expose import (
    NativeAlexaExposeManager,
    is_entity_exposed,
)


def test_is_entity_exposed_returns_true_when_helper_returns_true():
    """Verify is_entity_exposed returns True when exposed_entities says True."""
    hass = MagicMock()
    with patch(
        "custom_components.alexa_native_expose.expose.async_should_expose",
        return_value=True,
    ):
        result = is_entity_exposed(hass, "light.living_room")
        assert result is True


def test_is_entity_exposed_returns_false_when_helper_returns_false():
    """Verify is_entity_exposed returns False when exposed_entities says False."""
    hass = MagicMock()
    with patch(
        "custom_components.alexa_native_expose.expose.async_should_expose",
        return_value=False,
    ):
        result = is_entity_exposed(hass, "light.secret_lamp")
        assert result is False


def test_manager_patches_and_unpatches_alexa_config():
    """Verify NativeAlexaExposeManager patches AlexaConfig and restores it cleanly."""
    hass = MagicMock()

    class FakeAlexaConfig:
        def __init__(self):
            self.hass = hass

        def should_expose(self, entity_id: str) -> bool:
            return False

    fake_config = FakeAlexaConfig()
    manager = NativeAlexaExposeManager(hass)

    with patch(
        "custom_components.alexa_native_expose.expose.async_should_expose",
        side_effect=lambda h, assistant, ent_id: ent_id == "light.allowed",
    ):
        # Before patch
        assert fake_config.should_expose("light.allowed") is False

        # Apply patch to FakeAlexaConfig class
        manager.apply_patch_to_class(FakeAlexaConfig)
        assert fake_config.should_expose("light.allowed") is True
        assert fake_config.should_expose("light.blocked") is False

        # Remove patch
        manager.remove_patch_from_class(FakeAlexaConfig)
        assert fake_config.should_expose("light.allowed") is False
