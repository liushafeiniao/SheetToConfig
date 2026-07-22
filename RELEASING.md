# SheetToConfig 发布指南

## TL;DR

稳定版本使用 `vX.Y.Z` Tag 触发 GitHub Actions。流水线会验证版本与更新日志、运行 Windows/macOS 测试、构建 Windows EXE，并在 Apple 凭据完整时签名和公证两种架构的 macOS DMG，最后创建 GitHub Release 和 `SHA256SUMS.txt`。

没有 Apple Developer 凭据时，可以使用 `Build and Release` 的手动运行入口生成未签名 macOS 包。保持两个发布开关关闭时，产物只保存在 Actions；从默认分支显式开启 `publish_unsigned_macos_preview` 时，流水线会更新公开的滚动 [`macos-preview`](https://github.com/liushafeiniao/SheetToConfig/releases/tag/macos-preview) 预发布。该预发布未经 Apple 签名或公证，不能替代稳定版本。

凭据准备完成后，可手动开启 `sign_macos` 做签名与公证 dry-run；该模式只上传 Actions Artifact，不创建 GitHub Release。`sign_macos` 与 `publish_unsigned_macos_preview` 不能同时开启，也不要用正式 Tag 做首次凭据试验。

## 免费 macOS 预览发布

没有 Apple Developer 会员资格时，可为愿意手动确认 Gatekeeper 提示的用户发布实验性 Mac 包：

1. 打开 GitHub Actions → `Build and Release` → `Run workflow`。
2. 分支必须选择仓库默认分支。
3. 保持 `sign_macos` 为 `false`。
4. 将 `publish_unsigned_macos_preview` 设置为 `true` 后运行。
5. 确认测试和 ARM64、Intel 两个构建任务成功。
6. 流水线会校验四个架构产物、生成 SHA-256 与源提交元数据，然后替换 `macos-preview` 这一项滚动 Pre-release。

面向普通用户优先提供带 `-unsigned.dmg` 后缀的文件：Apple M 系列芯片下载 `arm64`，Intel 处理器下载 `x64`；`.app.zip` 作为开发者备用。预发布页必须持续明确以下事实：

- 包未经签名、公证或 Apple 验证，只应在信任仓库和对应源提交时使用。
- 首次启动被拦截后，使用 Apple 提供的「系统设置 → 隐私与安全性 → 仍要打开」，不要引导用户关闭 Gatekeeper 或执行移除隔离属性的命令。
- 公司或学校管理的 Mac 可能禁止手动放行，此时使用源码启动，或等待正式签名版本。
- GitHub 的 macOS Runner 负责实际打包，维护者不必拥有本地 Mac；但云端构建不能替代真实设备上的安装和界面验收。

预览发布采用固定非稳定标签 `macos-preview`。每次成功运行只替换该标签和预发布的资源，不得删除或修改任何 `vX.Y.Z` 标签或稳定 Release。工作流开始修改远端前，会先拒绝缺失、重复或意外产物，并核对 SHA-256。

## 首次配置

在 GitHub 仓库 Settings → Environments 中创建 `release` 环境，并设置所需审核人。把以下凭据保存为该环境的 Secrets：

| Secret | 用途 |
| --- | --- |
| `APPLE_CERTIFICATE_P12_BASE64` | Developer ID Application 证书的 P12 文件，Base64 编码 |
| `APPLE_CERTIFICATE_PASSWORD` | P12 导出密码 |
| `APPLE_DEVELOPER_ID` | 完整签名身份，例如 `Developer ID Application: Name (TEAMID)` |
| `APPLE_TEAM_ID` | Apple Developer Team ID |
| `APPLE_API_KEY_ID` | App Store Connect API Key ID |
| `APPLE_API_ISSUER_ID` | App Store Connect Issuer ID |
| `APPLE_API_PRIVATE_KEY_BASE64` | API `.p8` 私钥，Base64 编码 |

凭据只进入受保护的签名任务。Pull Request、普通 Push 和未签名构建任务不能读取这些 Secrets。

## 首次凭据验证（不发布）

Apple 凭据配置完成后，先做一次受保护的手动签名验证：

1. 打开 GitHub Actions → `Build and Release` → `Run workflow`。
2. 将 `sign_macos` 设置为 `true` 后运行。
3. 在 `release` Environment 审核提示中确认本次签名任务。
4. 确认 ARM64 与 Intel 的 `Sign and notarize macOS` job 均成功。
5. 下载 `macos-signed-arm64` 和 `macos-signed-x64` Artifacts，留作内部验收。
6. 确认 `Publish GitHub Release` 被跳过；手动运行不得创建或更新 Release。

签名脚本会依次验证 Developer ID 身份、`codesign`、Apple 公证、Stapler 和 Gatekeeper。任何 Secret 缺失都会让签名 job 明确失败，不会回退成未签名稳定包。

## 发布步骤

1. 修改 `version.py` 的 `__version__`，使用 SemVer，例如 `1.1.0`。
2. 把 `CHANGELOG.md` 的 `Unreleased` 内容整理到 `## [1.1.0] - YYYY-MM-DD`。
3. 运行 `python scripts/check_release.py --tag v1.1.0`。
4. 运行完整测试并提交源码。
5. 创建并推送 Tag：`git tag -a v1.1.0 -m "SheetToConfig v1.1.0"`，然后 `git push origin v1.1.0`。
6. 在 Actions 中确认测试、双架构构建、签名、公证、Gatekeeper 校验和 Release 发布全部成功。

发布物固定命名为：

```text
SheetToConfig-vX.Y.Z-windows-x64.exe
SheetToConfig-vX.Y.Z-macos-arm64.dmg
SheetToConfig-vX.Y.Z-macos-x64.dmg
SHA256SUMS.txt
```

## 未签名验证

在 Actions 中手动运行 `Build and Release`，并保持 `sign_macos` 与 `publish_unsigned_macos_preview` 均为 `false`。该模式不会读取 Apple Secrets 或创建 Release，而会保存 Windows EXE、两种架构的 `.app.zip` 和带 `-unsigned` 后缀的 DMG，供内部验证。

只有从默认分支显式开启 `publish_unsigned_macos_preview`，这些未签名 Mac 产物才会进入公开的滚动预发布；手动运行不会创建稳定 Release。

## 风险与边界

- PyInstaller 不能跨平台构建；每个安装包必须在对应 GitHub Runner 上生成。
- macOS 稳定包必须通过 Developer ID 签名、Apple 公证、Stapler 和 Gatekeeper 校验。
- `macos-preview` 仅是免费、未签名的实验交付通道；它不应被设为 Latest，也不能在文档中描述成官方验证或稳定 Mac 包。
- Windows 当前未配置代码签名，用户可能看到 SmartScreen 提示。
- Linux 不在正式发布矩阵中。
