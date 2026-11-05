"""Config flow for Alexa Native Expose."""
from typing import Any, Optional

try:
    from homeassistant import config_entries
    from homeassistant.data_entry_flow import FlowResult
except ImportError:
    class FakeConfigFlow:
        VERSION = 1

        def __init_subclass__(cls, domain: str = "", **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)

        def async_create_entry(
            self, title: str, data: dict[str, Any]
        ) -> dict[str, Any]:
            return {"type": "create_entry", "title": title, "data": data}

        def async_abort(self, reason: str) -> dict[str, Any]:
            return {"type": "abort", "reason": reason}

        def async_show_form(self, step_id: str) -> dict[str, Any]:
            return {"type": "form", "step_id": step_id}

        def _async_current_entries(self) -> list[Any]:
            return []

    class config_entries:
        ConfigFlow = FakeConfigFlow

    FlowResult = dict[str, Any]

from .const import DOMAIN


class AlexaNativeExposeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Alexa Native Expose."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial user step.

        Example:
            result = await flow.async_step_user({})
        """
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Alexa Native Expose", data={})

        return self.async_show_form(step_id="user")
