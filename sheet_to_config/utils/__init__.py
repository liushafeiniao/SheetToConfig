# -*- coding: utf-8 -*-
"""GUI utility entry points, loaded lazily to keep exporter imports headless."""

from importlib import import_module


_EXPORTS = {
    'ProjectManager': ('.project_manager', 'ProjectManager'),
    'Project': ('.project_manager', 'Project'),
    'ExportHandler': ('.export_handler', 'ExportHandler'),
    'ExportHandlerAsync': ('.export_handler', 'ExportHandlerAsync'),
    'ImportHandler': ('.import_handler', 'ImportHandler'),
    'ImportHandlerAsync': ('.import_handler', 'ImportHandlerAsync'),
}


def __getattr__(name):
    """Resolve GUI helpers only when callers explicitly request them."""
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value

__all__ = [
    'ProjectManager',
    'Project',
    'ExportHandler',
    'ExportHandlerAsync',
    'ImportHandler',
    'ImportHandlerAsync'
]
