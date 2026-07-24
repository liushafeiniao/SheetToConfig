# -*- coding: utf-8 -*-
"""Compatibility launcher for the packaged SheetToConfig application."""

import sys

from sheet_to_config.app import SheetToConfigWindow, main

__all__ = ["SheetToConfigWindow", "main"]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--apply-update":
        from sheet_to_config.utils.updater import apply_update_from_cli

        raise SystemExit(apply_update_from_cli(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--cleanup-update":
        from sheet_to_config.utils.updater import cleanup_update_from_cli

        raise SystemExit(cleanup_update_from_cli(sys.argv[2:]))
    main()
