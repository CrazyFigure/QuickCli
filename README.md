<p align="center">
  <img src="logo.png" width="120" alt="QuickCli Logo" />
</p>

<h1 align="center">QuickCli</h1>

<p align="center">
  Windows 轻量级命令行启动器 · 在常用项目目录间快速切换并打开终端
</p>

---

## 快速开始

### 安装版（推荐）

1. 前往 [Releases](https://github.com/CrazyFigure/QuickCli/releases) 下载最新 `QuickCli-Setup.exe`
2. 运行安装程序，完成后从开始菜单或桌面启动
3. 选择目录 → 选择命令 → 点击 **▶ 打开终端**

### 便携版

下载 `QuickCli.exe`，双击即可运行，无需安装。

### 开发模式

开发、打包、发布说明已迁移到 [DEVELOP.md](DEVELOP.md)。

## 功能

- **目录快速切换** — 选择本地目录并一键打开终端
- **多命令支持** — 内置预设命令 `claude` / `codex` / `opencode`，可自由添加自定义命令
- **历史记录** — 自动记录使用过的目录和命令组合，支持单条删除和一键清空
- **命令排序** — 设置中拖动调整命令显示顺序
- **系统托盘** — 最小化到托盘，右键菜单快速切换主命令和打开历史目录
- **自动更新** — 支持检查 GitHub Release 新版本并一键更新
- **现代化 UI** — 基于 customtkinter 构建，圆角卡片 + 柔和配色

## 使用方法

1. 在主界面选择或输入一个目录
2. 在「选择命令」中选中要执行的命令
3. 点击 **▶ 打开终端**
4. 程序会在该目录下打开一个新的终端窗口并执行对应命令

**历史记录**

- 点击命令下拉框可以切换命令
- 点击 **▶** 可以再次打开终端
- 点击 **✕** 删除单条记录
- 点击「清空」删除全部历史记录

## 设置说明

点击主界面底部「设置」按钮可配置：

- **终端程序路径** — 默认为 `C:\Program Files\PowerShell\7\pwsh.exe`
- **自定义命令** — 可新增任意数量的命令
- **命令显示顺序** — 拖动排序，主界面和历史记录都会按此顺序显示

> 预设命令 `claude` / `codex` / `opencode` 不可删除。

## 配置文件

| 模式 | 路径 |
|------|------|
| 开发模式 | 项目根目录 `settings.json` |
| 安装版 / exe | `%APPDATA%\QuickCli\settings.json` |

主要字段：`terminal_path`、`custom_commands`、`command_order`、`primary_command`、`history`、`max_history`

## 运行环境

- Windows 10 / 11
- Python 3.8+（仅开发模式需要）
- 建议安装 PowerShell 7

## 开发者文档

如果你要参与 QuickCli 的开发、构建安装包或执行发布流程，请阅读 [DEVELOP.md](DEVELOP.md)。

其中包含：

- 本地开发环境与运行方式
- 便携版 / 安装版构建方法
- 项目结构与关键文件说明
- 版本号、tag 与发布流程

## 许可

MIT
