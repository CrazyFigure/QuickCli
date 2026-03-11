# QuickCli

QuickCli 是一个面向 Windows 的轻量级命令行启动器，使用 `tkinter` 构建，无需额外第三方依赖。

它的目标很简单：在常用项目目录之间快速切换，并直接用指定命令打开新的终端窗口，减少重复输入 `cd` 和启动命令的操作。

## 功能

- 选择本地目录并打开终端
- 内置预设命令：`claude`、`codex`、`iflow`
- 支持添加多个自定义命令
- 支持在设置中拖动调整命令顺序
- 自动保存历史记录
- 历史记录支持单条删除和一键清空
- 设置和历史记录持久化到本地配置文件

## 适用场景

- 经常在多个项目目录之间切换
- 需要频繁打开 `claude` / `codex` / `iflow` 之类的命令行工具
- 希望给非命令行重度用户一个更直观的启动入口

## 运行环境

- Windows
- Python 3
- 建议安装 PowerShell 7

默认终端路径为：

```text
C:\Program Files\PowerShell\7\pwsh.exe
```

如果你的终端路径不同，可以在设置窗口中修改。

## 启动方式

### 方式一：直接运行 Python

```powershell
python .\main.py
```

### 方式二：双击批处理

直接运行项目中的 `QuickCli.bat`。

## 使用方法

1. 在主界面选择或输入一个目录。
2. 在“选择命令”中选中要执行的命令。
3. 点击“打开终端”。
4. 程序会在该目录下打开一个新的终端窗口，并执行对应命令。

历史记录区域可以直接复用之前的目录和命令组合：

- 点击右侧命令下拉框可以切换命令
- 点击 `▶` 可以再次打开终端
- 点击“删除”可以删除单条记录
- 点击“清空”可以删除全部历史记录

## 设置说明

点击主界面底部“设置”按钮后，可以配置：

- 终端程序路径
- 自定义命令
- 命令显示顺序

说明：

- `claude`、`codex`、`iflow` 为固定预设命令，不能删除
- 可以新增任意数量的自定义命令
- 可以通过拖动排序调整命令顺序
- 主界面和历史记录中的命令列表都会按该顺序显示

## 配置文件

程序会在项目根目录读取并保存配置：

```text
settings.json
```

主要字段包括：

- `terminal_path`：终端程序路径
- `custom_commands`：自定义命令列表
- `command_order`：命令显示顺序
- `history`：历史记录
- `max_history`：历史记录最大数量

打包为 `exe` 后，配置文件会自动改为写入当前用户目录：

```text
%APPDATA%\QuickCli\settings.json
```

这样可以避免安装到 `Program Files` 后因为目录不可写导致设置保存失败。

## 打包 Windows 可执行文件

本项目可以直接打包为 Windows 单文件 `exe`，不需要 Visual Studio。

### 本地构建便携版 exe

```powershell
python -m pip install pyinstaller
python -m PyInstaller .\QuickCli.spec --noconfirm --clean
```

如果你的环境没有 `python` 命令，也可以改用 `py`：

```powershell
py -m pip install pyinstaller
py -m PyInstaller .\QuickCli.spec --noconfirm --clean
```

输出文件：

```text
dist\QuickCli.exe
```

### 本地构建安装版 exe

如果已经安装 Inno Setup 6，可以直接执行：

```powershell
.\build.ps1 -Installer
```

输出文件：

```text
output\QuickCli-Setup.exe
```

## GitHub Actions 自动构建

仓库已提供工作流：

```text
.github/workflows/windows-build.yml
```

触发方式：

- 推送到 `main`
- 推送到 `feat/**` 分支
- 在 GitHub Actions 页面手动执行 `workflow_dispatch`

工作流会自动生成两类构建产物：

- `QuickCli-portable-exe`
- `QuickCli-setup-exe`

## 项目结构

```text
QuickCli/
├─ .github/
│  └─ workflows/
│     └─ windows-build.yml
├─ installer/
│  └─ QuickCli.iss
├─ QuickCli.spec
├─ build.ps1
├─ main.py
├─ settings.json
├─ QuickCli.bat
├─ icon.ico
└─ README.md
```

## 说明

- 路径显示统一使用 Windows 风格反斜杠
- 历史记录和设置会保存在本地，不依赖网络服务
- 本项目当前为桌面小工具形态，适合个人或小团队内部使用
