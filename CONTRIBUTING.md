<p align="right">
  <a href="docs/locales/CONTRIBUTING.en.md">English</a> ·
  <strong>简体中文</strong>
</p>

# 贡献指南

感谢你愿意为 SheetToConfig 贡献力量。本文档说明如何搭建开发环境、提交代码和发起 Pull Request。

## 项目结构

```
SheetToConfig.py        # PyQt 应用入口
sheet_to_config/        # 应用源码包
  i18n/catalogs/        # 翻译资源（JSON）
  utils/exporter/       # 导出逻辑（JSON / Lua / Protobuf）
  assets/               # 静态图片资源
docs/                   # 文档与 README 多语言版本
packaging/              # PyInstaller spec 等打包配置
scripts/                # 构建、测试与发布工具
tests/                  # unittest 测试
.github/workflows/      # CI 与发布工作流
```

## 环境搭建

Windows（PowerShell）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe SheetToConfig.py
```

macOS：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
./scripts/run.sh
```

Windows 控制台出现 Unicode 输出问题时，先设置 `$env:PYTHONUTF8 = "1"`。

## 常用命令

| 目的 | 命令 |
|---|---|
| 运行完整测试 | `python scripts/run_tests.py` |
| 运行单个测试模块 | `python -m unittest tests.test_app_paths -v` |
| 语法检查 | `python -m compileall -q .` |
| 校验发布元数据 | `python scripts/check_release.py --self-check` |
| 构建可执行文件 | `python scripts/build.py`（macOS 用 `./scripts/build.sh`） |

测试基于 Python 标准库 `unittest`，以无界面（offscreen）模式运行，无需显示环境。

## 代码风格

- 目标版本为 Python 3.12，统一四个空格缩进
- 模块、函数和变量使用 `snake_case`，类使用 `PascalCase`，常量使用 `UPPER_SNAKE_CASE`
- 新增公共辅助函数应添加类型标注
- 文件系统操作优先使用 `pathlib.Path`
- 脚本应职责单一，并尽量控制在 1,000 行以内
- 界面颜色通过 `styles.py` 或 `theme_config.py` 统一维护，不要散落硬编码值
- 项目未配置统一格式化器或静态检查器，修改时请遵循相邻代码的风格与导入顺序

## 测试规范

- 测试文件命名为 `test_<功能>.py`，测试类命名为 `<功能>Tests`，测试方法命名为 `test_<行为>`
- 每项改动应覆盖正常路径和失败路径
- 涉及文件系统、操作系统或 GUI 状态时，使用临时目录和 mock 隔离环境
- CI 会在 Windows、Apple Silicon macOS 和 Intel macOS 上运行测试，提交前请确保本地测试通过

## 提交规范

提交信息遵循 Conventional Commits 格式，例如：

```
feat: add exporter option
fix: preserve atomic rollback
test: cover headless startup
chore: update metadata
```

每个提交只处理一个明确主题。

## Pull Request 要求

- 说明行为变化，并关联相关 Issue
- 列出已运行的验证命令及结果，并注明测试平台
- 界面改动需要附截图
- 涉及发布流程或用户可见兼容性变化时，同步更新 `CHANGELOG.md` 和 `sheet_to_config/version.py`

## 禁止提交的内容

- 凭据、`.env` 文件、私钥（`*.pem` / `*.key` / `*.p12` / `*.pfx`）
- 本地状态文件（`config.json`、`projects.json`、`theme_config.json`）
- 构建产物（`build/`、`dist/`、`artifacts/`、`*.exe`、`*.dmg`）
- 真实项目路径或个人机器信息

开发时可通过 `SHEETTOCONFIG_DATA_DIR` 环境变量将应用数据重定向到独立目录，避免污染工作区。

## 行为准则

参与本项目的所有互动请遵守[行为准则](CODE_OF_CONDUCT.md)。发现安全问题时请按[安全政策](SECURITY.md)私密报告，不要在公开 Issue 中披露。
