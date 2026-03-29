# 开发环境与工具链规范 (Development Environment Rules)

## 1. Codex 命令行环境变量配置
- 确保 `codex` 命令直接指向最新的可执行文件入口：`D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe`。
- **请勿** 通过 Volta 在全局 `bin` 中配置过期的 `codex` shim (如 `0.113.0` 版本)，以防命令调用遭到劫持。
- 如果当前环境存在 PowerShell profile (如 `Microsoft.PowerShell_profile.ps1`)，其中的 `Alias:codex` 必须修正为最新版本入口，否则由于 `Set-Alias` 的存在会导致路径一直被错误覆盖。

## 2. Opencode 终端黑屏问题修复指南
- 当在 Windows PowerShell 中通过 Node.js (`spawnSync`) 调用基于 Rust/Go 编译的 `opencode` 终端 UI (TUI) 程序时，会导致标准输入输出挂起或页面直接黑屏。
- 解决该问题的方法是在 PowerShell 配置文件 (`$PROFILE`) 中设置直接指向可执行文件的 `Alias:opencode`，以跳过包含在全局 `opencode-ai` Node.js npm 包中的 wrapper 脚本，例如：
  `Set-Item -Path Alias:opencode -Value "$cwd\node_modules\opencode-ai\node_modules\opencode-windows-x64\bin\opencode.exe"`
- 这样可以通过系统的原生终端缓冲与子进程交互，恢复终端输入输出。

## 3. Git Ignore 与测试目录权限管理
- 项目运行自动化测试（如 `pytest` 或 `codex` sandbox 测试）时，会在各个子目录下生成诸多临时文件夹（例如 `__temp__`、`.pytest-local*`、`inline-snapshot*`、`tmp*` 等）。
- 某些测试若在特权模式下运行（例如以 Administrator 权限、或由 Docker Root 生成映射），这些文件夹的所有区会被锁定，标准用户无法读取。
- **解决方案**：针对此类现象，已经在全局 `.gitignore` 中配置了泛匹配（不限制根目录前缀 `/`）规则。这能够阻止 `git status` 遍历这些不可读的缓存目录从而触发海量的 `Permission denied` 警告。直接由 Git 核心绕过权限校验错误。
