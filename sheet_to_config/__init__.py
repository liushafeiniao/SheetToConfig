"""SheetToConfig application package."""

from importlib import import_module

from .version import __version__


def __getattr__(name):
    """Load the Qt application only when its public entry points are requested."""
    if name not in {"SheetToConfigWindow", "main"}:
        raise AttributeError(name)
    value = getattr(import_module(".app", __name__), name)
    globals()[name] = value
    return value


__all__ = ["SheetToConfigWindow", "__version__", "main"]
