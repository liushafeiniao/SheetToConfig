# -*- coding: utf-8 -*-
"""
版本、产品与仓库信息（全应用唯一来源）

版本号规则：语义化版本 MAJOR.MINOR.PATCH
- MAJOR: 不兼容的架构/协议变更
- MINOR: 新功能、界面改版（向后兼容）
- PATCH: 问题修复

发布流程：
1. 修改本文件 __version__
2. 在 CHANGELOG.md 记录变更
3. 提交源码并创建 v<__version__> tag
4. GitHub Actions 运行跨平台测试、构建 Windows EXE 并创建 Release

当前稳定 Release 只发布 Windows x64；macOS 未签名构建仅供维护者内部验证。
"""

__version__ = "1.0.5"

APP_NAME = "SheetToConfig"
APP_TITLE = "SheetToConfig"

# Canonical public repository.
GITHUB_URL = "https://github.com/liushafeiniao/SheetToConfig"

# Release 页面（手动下载与发布说明）
GITHUB_RELEASES_URL = GITHUB_URL + "/releases"
GITHUB_LATEST_RELEASE_API_URL = (
    "https://api.github.com/repos/liushafeiniao/SheetToConfig/releases/latest"
)


def resource_path(relative):
    """Resolve a package-owned resource in source and PyInstaller modes."""
    import sys
    from pathlib import Path

    package_root = Path(__file__).resolve().parent
    if getattr(sys, "_MEIPASS", None):
        package_root = Path(sys._MEIPASS) / "sheet_to_config"
    return str(package_root / relative)
