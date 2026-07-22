# SheetToConfig 发布指南

## TL;DR

稳定版本使用 `vX.Y.Z` Tag 触发 GitHub Actions。流水线会验证版本与更新日志、运行 Windows/macOS 测试、构建 Windows EXE，并在 Apple 凭据完整时签名和公证两种架构的 macOS DMG，最后创建 GitHub Release 和 `SHA256SUMS.txt`。

没有 Apple Developer 凭据时，请使用 `Build and Release` 的手动运行入口验证未签名 macOS 包；不要创建正式 Tag，因为稳定 Release 不允许上传未签名 DMG。

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

在 Actions 中手动运行 `Build and Release`。该模式不会创建 Release，而会保存 Windows EXE、两种架构的 `.app.zip` 和带 `-unsigned` 后缀的 DMG，供内部验证。

## 风险与边界

- PyInstaller 不能跨平台构建；每个安装包必须在对应 GitHub Runner 上生成。
- macOS 稳定包必须通过 Developer ID 签名、Apple 公证、Stapler 和 Gatekeeper 校验。
- Windows 当前未配置代码签名，用户可能看到 SmartScreen 提示。
- Linux 不在正式发布矩阵中。
