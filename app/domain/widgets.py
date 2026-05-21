from __future__ import annotations


class WidgetNotFoundError(RuntimeError):
    """Raised when a widget config lookup finds no matching record."""


class WidgetInactiveError(RuntimeError):
    """Raised when an inactive widget is accessed."""


class WidgetOriginDeniedError(RuntimeError):
    """Raised when a request origin is not in the widget's allowed_origins list."""
