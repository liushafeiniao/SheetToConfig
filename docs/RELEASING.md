# SheetToConfig 发布指南

## TL;DR

稳定 `vX.Y.Z` 标签只发布两个文件：Windows x64 EXE 和 `SHA256SUMS.txt`。发布前，工作流会校验版本、变更记录、跨平台测试、Windows 构建与精确文件清单；所有检查完成后才会创建新的远端 Release。

赞助二维码原图不进入公开源码。只有受保护的 `private-release-assets` Environment 构建任务能读取私密资源，并且需要维护者核对标签提交后批准；该任务只有源码读取权限。包含写权限的发布任务不接触这些私密变量，只接收已校验的 EXE 与校验文件。

macOS 继续在 CI 上测试。未签名 macOS 构建只能由维护者手动开启并作为内部预览 Artifact 保存；它不是稳定 Release，也不会在当前流程中发布。Developer ID 签名与 Apple 公证是未来稳定 macOS 发布的前置条件。

## 适用范围

本指南适用于仓库维护者发布稳定 Windows 版本，或在不发布的前提下验证 macOS 预览构建。

## 稳定 Windows 发布

1. 在 `sheet_to_config/version.py` 中更新 `__version__` 为有效 SemVer，例如 `1.1.0`。
2. 将 `CHANGELOG.md` 的未发布内容整理到 `## [1.1.0] - YYYY-MM-DD`。
3. 本地运行 `python scripts/check_release.py --tag v1.1.0` 和完整测试。
4. 提交所有变更，创建带注释标签：`git tag -a v1.1.0 -m "SheetToConfig v1.1.0"`。
5. 推送该标签：`git push origin v1.1.0`。
6. 在 Actions 中确认标签提交与当前 `main` 完全一致，再批准 `private-release-assets` Environment 的待处理部署。
7. 确认 Windows/macOS 测试、私密资源注入、Windows 构建、独立校验与发布任务均成功，再确认 Release 已创建。

稳定 Release 的精确资产清单为：

```text
SheetToConfig-vX.Y.Z-windows-x64.exe
SHA256SUMS.txt
```

`SHA256SUMS.txt` 只包含上述 EXE 的 SHA-256。工作流会拒绝缺失、重复或额外资产，且在任何远端变更前重新验证校验和。

## 私密赞助资源

公开仓库中的 `sheet_to_config/assets/donate/` 只跟踪说明文件，不跟踪 `alipay.png` 或 `wechat.png`。普通源码运行缺少图片时，「关于 → 赞助」会显示安全占位提示；官方 Windows EXE 在受保护构建中注入并包含两张图片。

Environment `private-release-assets` 必须限制为 `v*` 标签并设置维护者审批。它包含以下六个 Environment Secrets：

```text
DONATE_ALIPAY_PNG_B64_1
DONATE_ALIPAY_PNG_B64_2
DONATE_WECHAT_PNG_B64_1
DONATE_WECHAT_PNG_B64_2
DONATE_ALIPAY_PNG_SHA256
DONATE_WECHAT_PNG_SHA256
```

私密原图、完整编码、摘要值和私有 manifest 都不得写入仓库、Issue、PR、工作流字面量或日志。`scripts/inject_donation_assets.py` 会在构建前校验输入完整性、PNG 结构、尺寸和摘要；任一图片异常时整个构建失败。两文件替换对普通异常提供回滚并支持中断恢复，但不宣称具备主机故障级的跨文件原子性。

## 手动 macOS 内部预览

在 GitHub Actions 的 `Build and Release` 中手动运行工作流，将 `build_unsigned_macos` 设为 `true`。无论从哪个页面引用启动，预览任务都固定检出 `main`，并为 Apple Silicon 和 Intel 构建未签名 Artifact；该模式没有 `contents: write` 权限，不读取赞助资源 Secrets，也不会创建标签或 Release。因此内部 macOS 预览的赞助页会显示缺图占位提示。

这些产物未签名、未公证、未获 Apple 验证。仅在信任仓库和源提交时供维护者测试；受管理设备可能会阻止启动。不要引导用户关闭 Gatekeeper 或执行移除隔离属性的命令。

## 风险与边界

- PyInstaller 不能跨平台构建，Windows EXE 必须在 Windows runner 生成。
- 当前稳定通道不包含 macOS DMG、`.app.zip` 或任何其他文件。
- 签名和公证流程尚未接入稳定发布；未来接入前必须单独审查 Apple 凭据、受保护环境和真实设备验收。
- Windows 当前未配置代码签名，用户可能看到 SmartScreen 提示。
- Linux 未进入支持矩阵或 CI；源码运行可能可用，但不提供正式安装包。
- Environment 审批者必须核对待发布标签和工作流提交；拥有仓库写权限的账户仍属于受信任边界。
