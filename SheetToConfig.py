# -*- coding: utf-8 -*-
"""Compatibility launcher for the packaged SheetToConfig application."""

from sheet_to_config.app import SheetToConfigWindow, main

__all__ = ["SheetToConfigWindow", "main"]


if __name__ == "__main__":
    main()
