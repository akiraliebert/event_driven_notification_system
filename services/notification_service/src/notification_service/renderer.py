"""Jinja2 template rendering for notification content."""

from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

_env = SandboxedEnvironment(
    autoescape=True,
    undefined=StrictUndefined,
    keep_trailing_newline=False,
)


def render_template(template_str: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template string with the given context.

    Uses SandboxedEnvironment to prevent SSTI and StrictUndefined
    to raise on missing variables.
    All context values are converted to strings for safe template rendering.
    """
    str_context = {k: str(v) for k, v in context.items()}
    template = _env.from_string(template_str)
    return template.render(str_context)
