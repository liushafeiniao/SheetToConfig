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
4. GitHub Actions 测试、打包、签名、公证并创建 Release
"""

__version__ = "1.0.0"

APP_NAME = "SheetToConfig"
APP_TITLE = "SheetToConfig"

# Canonical public repository.
GITHUB_URL = "https://github.com/liushafeiniao/SheetToConfig"

# Release 页面（检查更新跳转）
GITHUB_RELEASES_URL = GITHUB_URL + "/releases"


def resource_path(relative):
    """资源文件路径，兼容源码运行与 PyInstaller 打包"""
    import os
    import sys
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)
