# 更新日志

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)：`MAJOR.MINOR.PATCH`

- **MAJOR**：不兼容的架构或协议变更
- **MINOR**：新功能、界面改版（向后兼容）
- **PATCH**：问题修复

版本号唯一来源：`version.py` 中的 `__version__`。

## [Unreleased]

### 新增
- Windows、Apple Silicon macOS 与 Intel macOS 的 GitHub Actions 测试矩阵
- Windows EXE、macOS APP/DMG、SHA-256 与 GitHub Release 自动化流程
- Apple Developer ID 签名与公证接口；未配置凭据时仅生成内部测试产物
- 可选的 `macos-preview` 滚动预发布：公开提供未签名 ARM64/x64 DMG、源提交元数据和 SHA-256，并与签名稳定版本严格隔离

### 兼容性
- 使用 Qt 桌面服务跨平台打开文件夹
- 临时文件统一使用系统临时目录，避免依赖 Windows `TEMP`
- JSON 根键继续按 `id`、`ID`、`key` 的旧版优先级选择；没有传统键时才使用第一列
- 老项目未配置 `assetRoot` 时，`path()` 暂时回退到客户端输出目录进行旧版兼容校验
- CODE 输出名暂时允许省略扩展名并按 JSON 导出，同时给出迁移警告；后续版本将要求显式 `.json`
- 导出不会再自动补写现有 `TypeDefinition.xlsx`；需要升级模板时请显式创建新模板并合并自定义类型

### 升级注意
- 未知转换函数、参数数量错误仍会终止整批导出，请先使用「仅校验」修正 `TypeDefinition.xlsx`
- `int` 不再截断小数或把无效文本改成 `0`；`bool` 只接受布尔值、`0/1` 和标准真假文本；列表中的空元素会报错
- 首次使用「导出指定文件」前必须完成一次全量导出，以建立安全删除旧产物所需的 manifest
- 破坏性 Protobuf 变更默认关闭，只能在导出对话框中显式勾选

## [1.0.0] - 2026-07-21

首个公开发布版本。

### 功能
- 多项目 Excel 配置表统一管理，支持拖拽排序、右键与「···」快捷菜单
- 一键导表：JSON / Lua / Protobuf 三种格式，客户端/服务端分离，支持指定文件导出
- Protobuf：`.pb` 输出自动生成同名 `.proto` 与 `.pb`，默认按当前 Excel 类型重建协议，可选生成 C#
- 传共享：一键复制表格到团队共享目录
- 文件拖放：拖入文件夹快速设置表格目录，配置对话框路径框支持拖入
- 主题系统：8 套预设暗色主题 + 自定义配色 + 窗口背景皮肤（自动缩放缓存）
- 日志按级别着色并带状态图标
- 项目详情区可折叠，路径一键复制
- 「关于」页签：GitHub 地址、检查更新、使用说明、支持作者

### 可靠性增强
- 严格类型转换、第一列主键、结构化错误聚合与仅校验模式
- TypeDefinition 增加 enum，并补齐 required、range、regex、unique 等约束
- 客户端和服务端生成确定性热更新 manifest，指定文件导出支持合并与删除识别
- 整批产物采用可回滚原子提交，任一工作簿失败时保留全部旧文件
- 资源根目录可选校验，Protobuf 破坏性重建改为显式勾选并二次确认
