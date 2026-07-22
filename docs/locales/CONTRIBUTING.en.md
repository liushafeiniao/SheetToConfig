<p align="right">
  <strong>English</strong> ·
  <a href="../../CONTRIBUTING.md">简体中文</a>
</p>

# Contributing Guide

Thanks for your interest in contributing to SheetToConfig. This document explains how to set up the development environment, submit code, and open pull requests.

## Project Layout

```
SheetToConfig.py        # PyQt application entry point
sheet_to_config/        # Application source package
  i18n/catalogs/        # Translation resources (JSON)
  utils/exporter/       # Export logic (JSON / Lua / Protobuf)
  assets/               # Static image assets
docs/                   # Documentation and localized READMEs
packaging/              # PyInstaller spec and packaging config
scripts/                # Build, test, and release tooling
tests/                  # unittest test suite
.github/workflows/      # CI and release workflows
```

## Development Setup

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe SheetToConfig.py
```

macOS:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
./scripts/run.sh
```

If the Windows console shows Unicode output issues, set `$env:PYTHONUTF8 = "1"` first.

## Common Commands

| Purpose | Command |
|---|---|
| Run the full test suite | `python scripts/run_tests.py` |
| Run a single test module | `python -m unittest tests.test_app_paths -v` |
| Syntax check | `python -m compileall -q .` |
| Validate release metadata | `python scripts/check_release.py --self-check` |
| Build the executable | `python scripts/build.py` (use `./scripts/build.sh` on macOS) |

Tests use the Python standard library `unittest` and run headless (offscreen), so no display is required.

## Code Style

- Target Python 3.12 with four-space indentation
- Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; `UPPER_SNAKE_CASE` for constants
- Add type annotations to new public helper functions
- Prefer `pathlib.Path` for filesystem operations
- Keep scripts single-purpose and under roughly 1,000 lines
- Maintain UI colors centrally in `styles.py` or `theme_config.py`; do not scatter hard-coded values
- The project has no enforced formatter or linter; follow the style and import order of neighboring code

## Testing Conventions

- Name test files `test_<feature>.py`, test classes `<Feature>Tests`, and test methods `test_<behavior>`
- Cover both the happy path and failure paths for every change
- Use temporary directories and mocks to isolate filesystem, OS, or GUI state
- CI runs the suite on Windows, Apple Silicon macOS, and Intel macOS; make sure tests pass locally before submitting

## Commit Convention

Commit messages follow Conventional Commits, for example:

```
feat: add exporter option
fix: preserve atomic rollback
test: cover headless startup
chore: update metadata
```

Keep each commit focused on a single topic.

## Pull Request Requirements

- Describe the behavior change and link the related issue
- List the verification commands you ran, their results, and the platforms tested
- Attach screenshots for UI changes
- For changes affecting the release process or user-visible compatibility, update `CHANGELOG.md` and `sheet_to_config/version.py` accordingly

## What Not to Commit

- Credentials, `.env` files, private keys (`*.pem` / `*.key` / `*.p12` / `*.pfx`)
- Local state files (`config.json`, `projects.json`, `theme_config.json`)
- Build artifacts (`build/`, `dist/`, `artifacts/`, `*.exe`, `*.dmg`)
- Real project paths or personal machine information

During development, you can redirect application data to an isolated directory with the `SHEETTOCONFIG_DATA_DIR` environment variable.

## Code of Conduct

All interactions in this project are governed by the [Code of Conduct](../../CODE_OF_CONDUCT.md). Report security issues privately as described in the [Security Policy](../../SECURITY.md); do not disclose them in public issues.
