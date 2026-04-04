#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuickCli - Windows 快速命令行启动器
使用 customtkinter 构建现代化 UI
"""

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# 删除了剔除 TCL_LIBRARY 和 TK_LIBRARY 的逻辑，因为它会导致 PyInstaller 打包后的程序崩溃。

import subprocess
from typing import List, Optional
import threading
import urllib.request
import urllib.error
import tempfile
from PIL import Image
from pystray import Icon, Menu, MenuItem

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox

import customtkinter as ctk

METADATA_FILE = "app_metadata.json"
COMMAND_RENAMES = {
    "iflow": "opencode"
}


def get_bootstrap_dir() -> Path:
    """获取启动阶段可访问的资源目录"""
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        return Path(meipass)
    return Path(__file__).parent.resolve()


def load_app_metadata() -> dict:
    """加载应用元数据，未命中时回退到默认值"""
    defaults = {
        "app_name": "QuickCli",
        "version": "0.0.0",
        "publisher": "CrazyFigure",
        "app_user_model_id": "CrazyFigure.QuickCli",
        "exe_name": "QuickCli.exe",
        "setup_base_name": "QuickCli-Setup",
        "preset_commands": ["claude", "codex", "opencode"]
    }

    metadata_path = get_bootstrap_dir() / METADATA_FILE
    if not metadata_path.exists():
        return defaults

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except Exception as e:
        print(f"加载应用元数据失败: {e}")
        return defaults

    merged = defaults.copy()
    merged.update(loaded if isinstance(loaded, dict) else {})
    return merged


APP_METADATA = load_app_metadata()

# 设置 DPI 感知，确保在高 DPI 显示器上清晰
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    pass

# 设置 AppUserModelID 以便正确显示任务栏图标和名称
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_METADATA["app_user_model_id"])
except Exception:
    pass

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040

# 应用信息
APP_NAME = APP_METADATA["app_name"]
APP_VERSION = APP_METADATA["version"]
APP_ID = APP_METADATA["app_user_model_id"]
PRESET_COMMANDS = list(APP_METADATA.get("preset_commands", ["claude", "codex", "opencode"]))

# 默认配置
DEFAULT_CONFIG = {
    "terminal_path": r"C:\Program Files\PowerShell\7\pwsh.exe",
    "custom_commands": [],
    "command_order": PRESET_COMMANDS.copy(),
    "primary_command": "codex",  # 默认主命令
    "history": [],
    "max_history": 20
}

def get_app_dir() -> Path:
    """获取应用运行目录"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).parent.resolve()


def get_resource_dir() -> Path:
    """获取资源文件目录"""
    return get_bootstrap_dir()


def get_config_file(app_dir: Path) -> Path:
    """获取配置文件路径，打包后改为用户目录，避免写入安装目录"""
    if not getattr(sys, "frozen", False):
        return app_dir / "settings.json"

    appdata = os.getenv("APPDATA")
    config_dir = Path(appdata) if appdata else (Path.home() / "AppData" / "Roaming")
    return config_dir / APP_NAME / "settings.json"


# 获取应用路径
APP_DIR = get_app_dir()
RESOURCE_DIR = get_resource_dir()
LEGACY_CONFIG_FILE = APP_DIR / "settings.json"
CONFIG_FILE = get_config_file(APP_DIR)
ICON_FILE = RESOURCE_DIR / "icon.ico"


def apply_window_icon(window):
    """为 Windows 窗口设置标题栏和任务栏图标"""
    if not ICON_FILE.exists():
        return

    try:
        window.iconbitmap(default=str(ICON_FILE))
    except Exception:
        pass


def _dedupe_commands(commands) -> List[str]:
    """去重并清理命令列表"""
    normalized = []
    seen = set()
    for cmd in commands or []:
        text = normalize_command_name(cmd)
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def normalize_command_name(command: str) -> str:
    """兼容旧命令名并统一为当前命令名"""
    text = str(command).strip()
    if not text:
        return ""
    return COMMAND_RENAMES.get(text, text)


def normalize_config(raw_config: dict) -> dict:
    """兼容旧版配置并规范化命令数据"""
    config = {
        "terminal_path": raw_config.get("terminal_path", DEFAULT_CONFIG["terminal_path"]),
        "max_history": raw_config.get("max_history", DEFAULT_CONFIG["max_history"]),
        "primary_command": normalize_command_name(
            raw_config.get("primary_command", DEFAULT_CONFIG["primary_command"])
        )
    }

    legacy_commands = _dedupe_commands(raw_config.get("commands", []))
    custom_commands = _dedupe_commands(raw_config.get("custom_commands", []))
    merged_custom = _dedupe_commands(custom_commands + [
        cmd for cmd in legacy_commands if cmd not in PRESET_COMMANDS
    ])

    available_commands = PRESET_COMMANDS + merged_custom

    order_source = _dedupe_commands(
        raw_config.get("command_order", raw_config.get("command_priority", []))
    )
    if not order_source:
        legacy_default = str(raw_config.get("default_command", "")).strip()
        order_source = ([legacy_default] if legacy_default else []) + legacy_commands + PRESET_COMMANDS

    command_order = []
    for cmd in order_source:
        if cmd in available_commands and cmd not in command_order:
            command_order.append(cmd)
    for cmd in available_commands:
        if cmd not in command_order:
            command_order.append(cmd)

    history = []
    for item in raw_config.get("history", DEFAULT_CONFIG["history"]):
        if not isinstance(item, dict):
            continue
        path = normalize_windows_path(item.get("path", ""))
        if not path:
            continue
        history.append({
            "path": path,
            "command": normalize_command_name(item.get("command", config["primary_command"])),
            "time": item.get("time", "")
        })

    config["custom_commands"] = merged_custom
    config["command_order"] = command_order or PRESET_COMMANDS.copy()
    if config["primary_command"] not in available_commands:
        config["primary_command"] = config["command_order"][0]
    config["history"] = history
    return config


def get_available_commands(config: dict) -> List[str]:
    """获取当前可用命令，顺序以设置为准"""
    return _dedupe_commands(config.get("command_order", PRESET_COMMANDS)) or PRESET_COMMANDS.copy()


def normalize_windows_path(path: str) -> str:
    """统一为 Windows 风格路径显示"""
    text = str(path).strip()
    if not text:
        return ""
    return os.path.normpath(text).replace("/", "\\")


def load_config() -> dict:
    """加载配置文件"""
    config = DEFAULT_CONFIG.copy()
    config_candidates = [CONFIG_FILE]
    if LEGACY_CONFIG_FILE != CONFIG_FILE:
        config_candidates.append(LEGACY_CONFIG_FILE)

    for config_file in config_candidates:
        if not config_file.exists():
            continue
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                config.update(normalize_config(saved))
                break
        except Exception as e:
            print(f"加载配置失败: {e}")
    return config


def save_config(config: dict):
    """保存配置文件"""
    try:
        normalized = normalize_config(config)
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存配置失败: {e}")


class ModernStyle:
    """现代化样式配置 - 基于 Tailwind CSS 色系"""

    # 颜色方案
    BG_COLOR = "#f0f4f8"           # 微蓝调浅灰背景
    CARD_BG = "#ffffff"
    ACCENT_COLOR = "#e8f4fd"       # 历史项底色
    ACCENT_HOVER = "#d0e8f7"
    PRIMARY_COLOR = "#2563eb"      # 更鲜活的蓝
    PRIMARY_HOVER = "#1d4ed8"
    SUCCESS_COLOR = "#059669"      # 绿色（打开终端）
    SUCCESS_HOVER = "#047857"
    DANGER_COLOR = "#dc2626"       # 红色（删除）
    DANGER_HOVER = "#b91c1c"
    TEXT_COLOR = "#1e293b"         # 蓝灰深色
    TEXT_SECONDARY = "#475569"     # 加深辅助色，提升可读性
    TEXT_MUTED = "#64748b"         # 加深更淡辅助色
    BORDER_COLOR = "#e2e8f0"
    GHOST_BTN_BG = "#f1f5f9"      # 幽灵按钮底色，区分于纯白卡片

    # 字体
    FONT_FAMILY = "Segoe UI"
    FONT_SIZE_NORMAL = 13
    FONT_SIZE_SMALL = 12
    FONT_SIZE_COMBO = 13


def check_for_updates() -> dict:
    """检查 GitHub Release 是否有新版本"""
    api_url = "https://api.github.com/repos/CrazyFigure/QuickCli/releases/latest"
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'QuickCli-AutoUpdater'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            latest_tag = data.get("tag_name", "")
            if not latest_tag.startswith("v"):
                return {"has_update": False}

            latest_version = latest_tag[1:]

            # 简单版本比较
            current_parts = [int(p) for p in APP_VERSION.split(".") if p.isdigit()]
            latest_parts = [int(p) for p in latest_version.split(".") if p.isdigit()]

            # 补齐长度以便比较
            length = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (length - len(current_parts)))
            latest_parts.extend([0] * (length - len(latest_parts)))

            has_update = tuple(latest_parts) > tuple(current_parts)

            download_url = ""
            if has_update:
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith("Setup.exe"):
                        download_url = asset.get("browser_download_url", "")
                        break

            return {
                "has_update": has_update,
                "latest_version": latest_version,
                "download_url": download_url,
                "release_notes": data.get("body", "")
            }
    except Exception as e:
        print(f"检查更新失败: {e}")
        return {"has_update": False, "error": str(e)}


# 设置 customtkinter 外观
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class QuickCliApp(ctk.CTk):
    """QuickCli 主应用"""

    def __init__(self):
        super().__init__()
        
        # 初始时立即隐藏窗口，阻止加载 UI 碎片时的屏幕闪动
        self.withdraw()

        self.config = load_config()
        self.primary_command = self.config.get("primary_command", "codex")
        self.tray_icon = None

        self.title(APP_NAME)
        self.geometry("680x780")
        self.minsize(580, 680)
        self.configure(fg_color=ModernStyle.BG_COLOR)

        apply_window_icon(self)
        self._create_ui()
        self._refresh_history()

        # 先设为透明，再解除隐藏。此时系统开始为其分配真正的物理大小。
        self.wm_attributes("-alpha", 0)
        self.deiconify()
        
        # 强制更新重绘。由于此时处于 alpha=0 状态，界面在后台被完全分配好确切的坐标和缩放尺寸，同时用户视觉上完全看不到。
        self.update()

        # 现在获取到的 100% 是物理放大后的精确宽高，瞬间计算中心
        self._center_window_sync()
        
        # 将透明度恢复为 1.0 (不透明)，并提到最顶层
        self.wm_attributes("-alpha", 1.0)
        self.lift()
        self.focus_force()

        self.after(200, self._setup_tray)

        self.protocol("WM_DELETE_WINDOW", self._hide_window)

    def _center_window_sync(self):
        """完全同步对齐屏幕中心（使用 Tcl 原生物理坐标）"""
        self.update_idletasks()
        
        raw_geo = str(self.tk.call('wm', 'geometry', self._w))
        # 提取真实物理像素大小
        parts = raw_geo.split('+')[0].split('x')
        if len(parts) == 2:
            phys_w, phys_h = int(parts[0]), int(parts[1])
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            
            x = max(0, (sw - phys_w) // 2)
            y = max(0, (sh - phys_h) // 2 - 40) # 视觉重心稍稍偏上一丁点
            
            self.tk.call('wm', 'geometry', self._w, f'+{x}+{y}')

    def _hide_window(self):
        """隐藏主窗口"""
        self.withdraw()

    def _show_window(self):
        """显示主窗口（平滑呼出）"""
        self.wm_attributes("-alpha", 0)
        self.deiconify()
        self._center_window_sync()
        self.lift()
        self.after(20, lambda: self.wm_attributes("-alpha", 1.0))
        self.after(20, self.focus_force)

    def _setup_tray(self):
        """初始化系统托盘"""
        if Icon is None or not ICON_FILE.exists():
            return

        try:
            image = Image.open(str(ICON_FILE))
            self.tray_icon = Icon(
                APP_NAME,
                image,
                APP_NAME,
                menu=self._build_tray_menu()
            )
            self.tray_icon.run_detached()
        except Exception:
            pass

    def _build_tray_menu(self):
        """构建托盘右键菜单 - 平级分块展示"""
        menu_items = []

        # 1. 打开主界面（pystray 回调在非主线程，必须转回主线程）
        menu_items.append(MenuItem("打开主界面", lambda: self.after(0, self._show_window), default=True))
        menu_items.append(Menu.SEPARATOR)

        # 2. 选择主命令区域 - 使用原生勾选标记
        available_commands = get_available_commands(self.config)
        for cmd in available_commands:
            def make_cmd_handler(c):
                return lambda: self._set_primary_command(c)

            # 使用 pystray 原生 checked + radio 参数
            menu_items.append(MenuItem(
                cmd,
                make_cmd_handler(cmd),
                checked=lambda item, c=cmd: c == self.primary_command,
                radio=True
            ))

        menu_items.append(Menu.SEPARATOR)

        # 3. 历史目录区域标题 (禁用项仅作视觉标识)
        menu_items.append(MenuItem("📂 历史目录", lambda: None, enabled=False))

        # 历史目录列表 (展示 ...最后一级目录名)
        history = self.config.get("history", [])
        if not history:
            menu_items.append(MenuItem("  暂无历史目录", lambda: None, enabled=False))
        else:
            # 只显示最近 10 条历史记录以保持菜单长度合理
            # 删除了剔除 TCL_LIBRARY 和 TK_LIBRARY 的逻辑，因为它会导致 PyInstaller 打包后的程序崩溃。
            for item in history[:10]:
                path = item.get("path", "")
                if not path:
                    continue

                # 获取最后一级目录名并拼接 ...
                folder_name = os.path.basename(path.rstrip('\\/'))
                display_name = f".../{folder_name}"

                def make_history_handler(p):
                    return lambda: self._open_terminal(p, self.primary_command)

                menu_items.append(MenuItem(display_name, make_history_handler(path)))

        menu_items.append(Menu.SEPARATOR)

        # 4. 检查更新
        menu_items.append(MenuItem("检查更新", self._on_check_update_clicked))

        # 5. 退出
        menu_items.append(MenuItem("退出", self._quit_app))

        return Menu(*menu_items)

    def _on_check_update_clicked(self):
        """点击检查更新（托盘或主界面调用）"""
        threading.Thread(target=self._perform_update_check, daemon=True).start()

    def _perform_update_check(self):
        """执行更新检查的后台任务"""
        result = check_for_updates()
        self.after(0, lambda: self._show_update_result(result))

    def _show_update_result(self, result):
        """展示更新检查结果"""
        if result.get("error"):
            messagebox.showerror("更新检查失败", f"无法检查更新:\n{result['error']}")
            return

        if not result.get("has_update"):
            messagebox.showinfo("检查更新", f"当前已是最新版本 (v{APP_VERSION})！")
            return

        latest_version = result.get("latest_version")
        download_url = result.get("download_url")

        if not download_url:
            messagebox.showerror("发现新版本", f"发现新版本 v{latest_version}，但未找到对应的安装包下载链接。")
            return

        msg = f"发现新版本: v{latest_version}\n\n是否立即下载并更新？"
        if messagebox.askyesno("发现更新", msg):
            self._show_window()
            self._download_and_install_update(download_url)

    def _download_and_install_update(self, url: str):
        """下载并安装更新"""
        progress_win = ctk.CTkToplevel(self)
        progress_win.title("下载更新")
        progress_win.geometry("400x150")
        progress_win.resizable(False, False)
        progress_win.transient(self)
        progress_win.grab_set()
        apply_window_icon(progress_win)

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 150) // 2
        progress_win.geometry(f"+{x}+{y}")

        lbl = ctk.CTkLabel(progress_win, text="正在下载最新版本，请稍候...",
                           font=(ModernStyle.FONT_FAMILY, 13))
        lbl.pack(pady=(25, 10))

        progress = ctk.CTkProgressBar(progress_win, width=300)
        progress.pack(pady=10)
        progress.set(0)

        def download_task():
            try:
                temp_dir = tempfile.gettempdir()
                setup_path = os.path.join(temp_dir, "QuickCli-Update-Setup.exe")

                req = urllib.request.Request(url, headers={'User-Agent': 'QuickCli-AutoUpdater'})
                with urllib.request.urlopen(req, timeout=30) as response:
                    total_size = int(response.info().get('Content-Length', 0))
                    downloaded = 0
                    chunk_size = 8192

                    with open(setup_path, 'wb') as f:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                pct = min(downloaded / total_size, 1.0)
                                self.after(0, lambda p=pct: progress.set(p))

                self.after(0, lambda: self._execute_installer(setup_path, progress_win))
            except Exception as e:
                self.after(0, lambda: self._on_download_error(progress_win, str(e)))

        threading.Thread(target=download_task, daemon=True).start()

    def _on_download_error(self, win, error_msg):
        win.destroy()
        messagebox.showerror("下载失败", f"更新包下载失败:\n{error_msg}")

    def _execute_installer(self, setup_path, win):
        """执行安装包并退出当前程序"""
        win.destroy()
        try:
            subprocess.Popen([setup_path, "/CLOSEAPPLICATIONS"])
            self._quit_app()
        except Exception as e:
            messagebox.showerror("安装失败", f"启动更新程序失败:\n{e}")

    def _refresh_tray_menu(self):
        """同步刷新托盘右键菜单（历史目录、主命令选中状态）"""
        if self.tray_icon:
            self.tray_icon.menu = self._build_tray_menu()
            self.tray_icon.update_menu()

    def _set_primary_command(self, cmd):
        """设置主命令并刷新菜单"""
        self.primary_command = cmd
        self.config["primary_command"] = cmd
        save_config(self.config)
        self._refresh_tray_menu()

    def _quit_app(self):
        """完全退出应用"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.quit()
        self.destroy()
        sys.exit(0)

    def _create_ui(self):
        """创建用户界面"""
        # 主容器
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill='both', expand=True, padx=20, pady=(15, 20))

        # 标题区域
        title_label = ctk.CTkLabel(
            main_frame,
            text="QuickCli",
            font=(ModernStyle.FONT_FAMILY, 20, "bold"),
            text_color=ModernStyle.TEXT_COLOR
        )
        title_label.pack(pady=(0, 2))

        subtitle_label = ctk.CTkLabel(
            main_frame,
            text="Windows 快速命令行启动器",
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_SMALL),
            text_color=ModernStyle.TEXT_SECONDARY
        )
        subtitle_label.pack(pady=(0, 12))

        # === 目录选择卡片 ===
        dir_card = ctk.CTkFrame(main_frame, corner_radius=10,
                                fg_color=ModernStyle.CARD_BG,
                                border_width=1, border_color=ModernStyle.BORDER_COLOR)
        dir_card.pack(fill='x', pady=(0, 12))

        dir_content = ctk.CTkFrame(dir_card, fg_color="transparent")
        dir_content.pack(fill='x', padx=18, pady=16)

        ctk.CTkLabel(dir_content, text="📁 选择目录",
                     font=(ModernStyle.FONT_FAMILY, 15, "bold"),
                     text_color=ModernStyle.TEXT_COLOR).pack(anchor='w', pady=(0, 10))

        dir_input_frame = ctk.CTkFrame(dir_content, fg_color="transparent")
        dir_input_frame.pack(fill='x')

        self.dir_entry = ctk.CTkEntry(
            dir_input_frame,
            font=(ModernStyle.FONT_FAMILY, 14),
            corner_radius=8, height=40
        )
        self.dir_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.dir_entry.insert(0, normalize_windows_path(str(APP_DIR)))

        ctk.CTkButton(
            dir_input_frame, text="浏览", width=80,
            corner_radius=8, height=40,
            font=(ModernStyle.FONT_FAMILY, 14),
            fg_color=ModernStyle.GHOST_BTN_BG,
            border_width=1, border_color=ModernStyle.BORDER_COLOR,
            text_color=ModernStyle.TEXT_COLOR,
            hover_color=ModernStyle.ACCENT_HOVER,
            command=self._browse_directory
        ).pack(side='right')

        # === 命令选择卡片 ===
        cmd_card = ctk.CTkFrame(main_frame, corner_radius=10,
                                fg_color=ModernStyle.CARD_BG,
                                border_width=1, border_color=ModernStyle.BORDER_COLOR)
        cmd_card.pack(fill='x', pady=(0, 12))

        cmd_content = ctk.CTkFrame(cmd_card, fg_color="transparent")
        cmd_content.pack(fill='x', padx=18, pady=16)

        ctk.CTkLabel(cmd_content, text="⚡ 选择命令",
                     font=(ModernStyle.FONT_FAMILY, 15, "bold"),
                     text_color=ModernStyle.TEXT_COLOR).pack(anchor='w', pady=(0, 10))

        cmd_input_frame = ctk.CTkFrame(cmd_content, fg_color="transparent")
        cmd_input_frame.pack(fill='x')

        # 命令下拉框
        self.cmd_var = tk.StringVar()
        available_commands = get_available_commands(self.config)
        current_cmd = self.cmd_var.get().strip()
        if current_cmd not in available_commands:
            current_cmd = available_commands[0] if available_commands else ""
        self.cmd_var.set(current_cmd)

        self.cmd_option_menu = ctk.CTkOptionMenu(
            cmd_input_frame,
            variable=self.cmd_var,
            values=available_commands,
            corner_radius=8, height=40, width=180,
            font=(ModernStyle.FONT_FAMILY, 14),
            dropdown_font=(ModernStyle.FONT_FAMILY, 14),
            fg_color=ModernStyle.GHOST_BTN_BG,
            button_color=ModernStyle.BORDER_COLOR,
            button_hover_color=ModernStyle.TEXT_SECONDARY,
            text_color=ModernStyle.TEXT_COLOR,
            dropdown_fg_color=ModernStyle.CARD_BG,
            dropdown_text_color=ModernStyle.TEXT_COLOR,
            dropdown_hover_color=ModernStyle.ACCENT_HOVER
        )
        self.cmd_option_menu.pack(side='left', padx=(0, 15))

        # 打开终端按钮（绿色）
        ctk.CTkButton(
            cmd_input_frame, text="▶ 打开终端",
            corner_radius=8, height=40,
            font=(ModernStyle.FONT_FAMILY, 14, "bold"),
            fg_color=ModernStyle.SUCCESS_COLOR,
            hover_color=ModernStyle.SUCCESS_HOVER,
            command=self._open_terminal
        ).pack(side='left')

        # === 历史记录区域 ===
        history_section = ctk.CTkFrame(main_frame, fg_color="transparent")
        history_section.pack(fill='both', expand=True, pady=(0, 12))

        history_header = ctk.CTkFrame(history_section, fg_color="transparent")
        history_header.pack(fill='x', pady=(0, 8))

        ctk.CTkLabel(history_header, text="📋 历史记录",
                     font=(ModernStyle.FONT_FAMILY, 14, "bold"),
                     text_color=ModernStyle.TEXT_COLOR).pack(side='left')

        ctk.CTkButton(
            history_header, text="清空", width=60,
            corner_radius=8, height=30,
            fg_color=ModernStyle.GHOST_BTN_BG,
            border_width=1, border_color=ModernStyle.BORDER_COLOR,
            text_color=ModernStyle.TEXT_SECONDARY,
            hover_color=ModernStyle.ACCENT_HOVER,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_SMALL),
            command=self._clear_history
        ).pack(side='right')

        # 使用 CTkScrollableFrame 替代手动 Canvas+Scrollbar
        self.history_scroll_frame = ctk.CTkScrollableFrame(
            history_section,
            corner_radius=10,
            fg_color=ModernStyle.CARD_BG,
            border_width=1, border_color=ModernStyle.BORDER_COLOR,
            scrollbar_button_color=ModernStyle.BORDER_COLOR,
            scrollbar_button_hover_color=ModernStyle.PRIMARY_COLOR
        )
        self.history_scroll_frame.pack(fill='both', expand=True)

        # === 底部区域：设置 + 版本号 ===
        bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_frame.pack(fill='x', pady=(4, 0))

        ctk.CTkButton(
            bottom_frame, text="⚙ 设置",
            corner_radius=8, height=36, width=100,
            fg_color=ModernStyle.GHOST_BTN_BG,
            border_width=1, border_color=ModernStyle.BORDER_COLOR,
            text_color=ModernStyle.TEXT_COLOR,
            hover_color=ModernStyle.ACCENT_HOVER,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL),
            command=self._open_settings
        ).pack(side='left')

        ctk.CTkLabel(
            bottom_frame, text=f"v{APP_VERSION}",
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_SMALL),
            text_color=ModernStyle.TEXT_MUTED
        ).pack(side='right')

    def _center_window(self):
        """窗口居中（绝对尺寸数学推导法，杜绝隐藏状态下的假尺寸误导）"""
        self.update_idletasks()
        
        # 核心秘密：在 window 被 withdraw() 或完全加载出屏幕前，
        # 系统赋予的宽度不是 680x780，而是默认启动尺寸（如 200x200）。
        # 这就是为什么只要用了底层级联的推算或者内置居中，全都会基于 200x200 去居中，
        # 等真正展开成 680x780 时，窗口的拓展方向是向下向右的，所以就会看起来“偏右下”！
        
        width = 680
        height = 780
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        x = int(max(0, (screen_width / 2) - (width / 2)))
        y = int(max(0, (screen_height / 2) - (height / 2) - 40))  # 稍微向上提一点视觉中心
        
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _browse_directory(self):
        """浏览选择目录"""
        directory = filedialog.askdirectory(title="选择目录")
        if directory:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, normalize_windows_path(directory))

    def _open_terminal(self, path: str = None, command: str = None):
        """打开终端并执行命令"""
        directory = normalize_windows_path(path or self.dir_entry.get().strip())
        cmd = command or self.cmd_var.get()

        if not directory:
            messagebox.showwarning("提示", "请选择或输入目录路径")
            return

        if not os.path.isdir(directory):
            messagebox.showerror("错误", "目录不存在，请检查路径")
            return

        terminal_path = self.config.get("terminal_path", r"C:\Program Files\PowerShell\7\pwsh.exe")

        if not os.path.isfile(terminal_path):
            messagebox.showerror("错误", f"终端程序不存在:\n{terminal_path}")
            return

        try:
            # 从传递给终端的环境变量中剥离当前 PyInstaller 的 TCL/TK 库变量
            # 防止打开终端后，终端里执行的其他含界面的 Python 工具发生崩溃
            sub_env = os.environ.copy()
            for key in ["TCL_LIBRARY", "TK_LIBRARY"]:
                if "_MEI" in sub_env.get(key, ""):
                    sub_env.pop(key, None)

            # 启动终端
            subprocess.Popen(
                [terminal_path, "-NoExit", "-Command", f"cd '{directory}'; {cmd}"],
                cwd=directory,
                env=sub_env,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )

            # 添加到历史记录
            self._add_to_history(directory, cmd)

        except Exception as e:
            messagebox.showerror("错误", f"打开终端失败:\n{e}")

    def _add_to_history(self, path: str, command: str):
        """添加到历史记录"""
        path = normalize_windows_path(path)
        history = self.config.get("history", [])

        # 移除已存在的相同路径记录
        history = [h for h in history if normalize_windows_path(h.get("path", "")) != path]

        # 添加新记录到开头
        history.insert(0, {
            "path": path,
            "command": command,
            "time": datetime.now().isoformat()
        })

        # 限制历史记录数量
        max_history = self.config.get("max_history", 20)
        history = history[:max_history]

        self.config["history"] = history
        save_config(self.config)

        # 刷新显示
        self._refresh_history()

    def _sync_command_values(self, preferred_command: str = ""):
        """同步主界面的命令下拉框"""
        commands = get_available_commands(self.config)
        selected = preferred_command or self.cmd_var.get().strip()
        if selected not in commands:
            selected = commands[0] if commands else ""
        self.cmd_option_menu.configure(values=commands)
        self.cmd_var.set(selected)

    def _refresh_history(self):
        """刷新历史记录列表（先隐藏再重建，避免闪烁）"""
        # 先隐藏滚动容器，避免逐个销毁/创建时的视觉闪烁
        self.history_scroll_frame.pack_forget()

        # 清空现有记录
        for widget in self.history_scroll_frame.winfo_children():
            widget.destroy()

        history = self.config.get("history", [])

        if not history:
            empty_label = ctk.CTkLabel(
                self.history_scroll_frame,
                text="暂无历史记录",
                text_color=ModernStyle.TEXT_SECONDARY,
                font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL)
            )
            empty_label.pack(pady=30)
            self.history_scroll_frame.pack(fill='both', expand=True)
            self._refresh_tray_menu()
            return

        available_commands = get_available_commands(self.config)

        for idx, item in enumerate(history):
            self._create_history_item(item, available_commands)

        self.history_scroll_frame.pack(fill='both', expand=True)

        self._refresh_tray_menu()


    def _create_history_item(self, item: dict, available_commands: list):
        """创建历史记录项"""
        path = normalize_windows_path(item.get("path", ""))
        saved_cmd = item.get("command", "claude")
        item_commands = available_commands.copy()
        if saved_cmd and saved_cmd not in item_commands:
            item_commands.append(saved_cmd)

        # 历史记录项容器
        item_frame = ctk.CTkFrame(
            self.history_scroll_frame,
            fg_color=ModernStyle.ACCENT_COLOR,
            corner_radius=8,
            border_width=1,
            border_color=ModernStyle.BORDER_COLOR
        )
        item_frame.pack(fill='x', pady=4, padx=4)

        # 内部布局
        inner_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        inner_frame.pack(fill='x', padx=12, pady=10)
        inner_frame.grid_columnconfigure(0, weight=1)

        # 目录路径
        path_label = ctk.CTkLabel(
            inner_frame,
            text="",
            font=(ModernStyle.FONT_FAMILY, 14),
            text_color=ModernStyle.TEXT_COLOR,
            anchor='w'
        )
        path_label.grid(row=0, column=0, sticky='ew', padx=(0, 12))
        # 使用 after_idle 延迟计算一次路径显示即可，不要绑定 Configure 防止组件进入由于大小改变引起的无限重绘死锁
        self.after_idle(
            lambda label=path_label, full_path=path: self._update_path_label(label, full_path)
        )

        # 命令下拉框
        cmd_var = tk.StringVar(value=saved_cmd)
        cmd_option = ctk.CTkOptionMenu(
            inner_frame,
            variable=cmd_var,
            values=item_commands,
            corner_radius=6, height=34, width=130,
            font=(ModernStyle.FONT_FAMILY, 13),
            dropdown_font=(ModernStyle.FONT_FAMILY, 13),
            fg_color=ModernStyle.GHOST_BTN_BG,
            button_color=ModernStyle.BORDER_COLOR,
            button_hover_color=ModernStyle.TEXT_SECONDARY,
            text_color=ModernStyle.TEXT_COLOR,
            dropdown_fg_color=ModernStyle.CARD_BG,
            dropdown_text_color=ModernStyle.TEXT_COLOR,
            dropdown_hover_color=ModernStyle.ACCENT_HOVER
        )
        cmd_option.grid(row=0, column=1, padx=(0, 8))

        # 打开按钮（绿色）
        def make_open_handler(p, v):
            return lambda: self._open_terminal(p, v.get())

        open_btn = ctk.CTkButton(
            inner_frame, text="▶", width=40, height=34,
            corner_radius=6,
            font=(ModernStyle.FONT_FAMILY, 14, "bold"),
            fg_color=ModernStyle.SUCCESS_COLOR,
            hover_color=ModernStyle.SUCCESS_HOVER,
            command=make_open_handler(path, cmd_var)
        )
        open_btn.grid(row=0, column=2)

        # 删除按钮
        delete_btn = ctk.CTkButton(
            inner_frame, text="✕", width=40, height=34,
            corner_radius=6,
            font=(ModernStyle.FONT_FAMILY, 14),
            fg_color="transparent",
            text_color=ModernStyle.DANGER_COLOR,
            hover_color="#fee2e2",
            command=lambda p=path: self._delete_history_item(p)
        )
        delete_btn.grid(row=0, column=3, padx=(8, 0))

    def _update_path_label(self, label, full_path: str):
        """根据可用宽度优先展示路径右侧内容"""
        width = label.winfo_width()
        # 宽度太小时（初始化阶段）直接显示完整路径，等下次 Configure 再重算
        if width < 100:
            label.configure(text=full_path)
            return

        available_width = width
        font = tkfont.Font(family=ModernStyle.FONT_FAMILY, size=14)
        if font.measure(full_path) <= available_width:
            label.configure(text=full_path)
            return

        ellipsis = "..."
        shortened = full_path

        while shortened and font.measure(ellipsis + shortened) > available_width:
            slash_positions = [pos for pos in (shortened.find('/'), shortened.find('\\')) if pos >= 0]
            if slash_positions:
                shortened = shortened[min(slash_positions) + 1:]
            else:
                shortened = shortened[1:]

        while shortened and font.measure(ellipsis + shortened) > available_width:
            shortened = shortened[1:]

        label.configure(text=ellipsis + shortened if shortened else full_path[-1:])

    def _delete_history_item(self, path: str):
        """删除单条历史记录"""
        path = normalize_windows_path(path)
        history = self.config.get("history", [])
        self.config["history"] = [
            item for item in history
            if normalize_windows_path(item.get("path", "")) != path
        ]
        save_config(self.config)
        self._refresh_history()

    def _clear_history(self):
        """清空历史记录"""
        if messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
            self.config["history"] = []
            save_config(self.config)
            self._refresh_history()

    def _open_settings(self):
        """打开设置窗口"""
        SettingsWindow(self)


class SettingsWindow(ctk.CTkToplevel):
    """设置窗口"""

    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self.config = normalize_config(parent.config.copy())
        self.command_order = get_available_commands(self.config)
        self.drag_index = None

        self.title("设置")
        self.withdraw()
        self.resizable(True, True)
        self.minsize(560, 540)
        self.geometry("620x680")
        self.configure(fg_color=ModernStyle.BG_COLOR)

        # 设置图标
        apply_window_icon(self)

        # 模态窗口
        self.transient(parent)
        self.grab_set()

        self._create_ui()
        self._center_on_parent()
        self.deiconify()
        self.lift()
        self.focus_force()

    def _create_ui(self):
        """创建设置界面"""
        # 主容器
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # === 按钮区域（优先 pack 到底部，确保窗口缩小时始终可见） ===
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(side='bottom', fill='x', pady=(12, 0))

        # 左侧：检查更新和版本号
        left_btn_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        left_btn_frame.pack(side='left')

        ctk.CTkButton(
            left_btn_frame, text="检查更新", width=90,
            corner_radius=8, height=36,
            fg_color=ModernStyle.GHOST_BTN_BG,
            border_width=1, border_color=ModernStyle.BORDER_COLOR,
            text_color=ModernStyle.TEXT_COLOR,
            hover_color=ModernStyle.ACCENT_HOVER,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL),
            command=self.parent._on_check_update_clicked
        ).pack(side='left')

        ctk.CTkLabel(
            left_btn_frame, text=f"v{APP_VERSION}",
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_SMALL),
            text_color=ModernStyle.TEXT_SECONDARY
        ).pack(side='left', padx=(10, 0))

        # 右侧：保存取消
        right_btn_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        right_btn_frame.pack(side='right')

        ctk.CTkButton(
            right_btn_frame, text="取消", width=80,
            corner_radius=8, height=36,
            fg_color=ModernStyle.GHOST_BTN_BG,
            border_width=1, border_color=ModernStyle.BORDER_COLOR,
            text_color=ModernStyle.TEXT_COLOR,
            hover_color=ModernStyle.ACCENT_HOVER,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL),
            command=self.destroy
        ).pack(side='right')

        ctk.CTkButton(
            right_btn_frame, text="保存", width=80,
            corner_radius=8, height=36,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL, "bold"),
            fg_color=ModernStyle.PRIMARY_COLOR,
            hover_color=ModernStyle.PRIMARY_HOVER,
            command=self._save
        ).pack(side='right', padx=(0, 10))

        # === 终端设置 ===
        ctk.CTkLabel(
            main_frame, text="💻 终端设置",
            font=(ModernStyle.FONT_FAMILY, 16, "bold"),
            text_color=ModernStyle.TEXT_COLOR
        ).pack(anchor='w', pady=(0, 10))

        terminal_card = ctk.CTkFrame(main_frame, corner_radius=10,
                                     fg_color=ModernStyle.CARD_BG,
                                     border_width=1, border_color=ModernStyle.BORDER_COLOR)
        terminal_card.pack(fill='x', pady=(0, 12))

        terminal_inner = ctk.CTkFrame(terminal_card, fg_color="transparent")
        terminal_inner.pack(fill='x', padx=18, pady=16)

        ctk.CTkLabel(terminal_inner, text="终端路径:",
                     font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL),
                     text_color=ModernStyle.TEXT_COLOR).pack(anchor='w')

        terminal_input_frame = ctk.CTkFrame(terminal_inner, fg_color="transparent")
        terminal_input_frame.pack(fill='x', pady=(8, 0))

        self.terminal_entry = ctk.CTkEntry(
            terminal_input_frame,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL),
            corner_radius=8, height=38
        )
        self.terminal_entry.insert(0, self.config.get("terminal_path", ""))
        self.terminal_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ctk.CTkButton(
            terminal_input_frame, text="浏览", width=80,
            corner_radius=8, height=38,
            fg_color=ModernStyle.GHOST_BTN_BG,
            border_width=1, border_color=ModernStyle.BORDER_COLOR,
            text_color=ModernStyle.TEXT_COLOR,
            hover_color=ModernStyle.ACCENT_HOVER,
            command=self._browse_terminal
        ).pack(side='right')

        # === 命令设置 ===
        ctk.CTkLabel(
            main_frame, text="📝 命令设置",
            font=(ModernStyle.FONT_FAMILY, 16, "bold"),
            text_color=ModernStyle.TEXT_COLOR
        ).pack(anchor='w', pady=(0, 10))

        cmd_card = ctk.CTkFrame(main_frame, corner_radius=10,
                                fg_color=ModernStyle.CARD_BG,
                                border_width=1, border_color=ModernStyle.BORDER_COLOR)
        cmd_card.pack(fill='both', expand=True, pady=(0, 0))

        cmd_inner = ctk.CTkFrame(cmd_card, fg_color="transparent")
        cmd_inner.pack(fill='both', expand=True, padx=18, pady=16)

        ctk.CTkLabel(
            cmd_inner,
            text="预设命令固定包含 claude / codex / opencode，自定义命令可新增、删除，并支持拖动排序。",
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL),
            text_color=ModernStyle.TEXT_COLOR,
            wraplength=650
        ).pack(anchor='w')

        # 新增命令行
        add_frame = ctk.CTkFrame(cmd_inner, fg_color="transparent")
        add_frame.pack(fill='x', pady=(12, 15))

        self.custom_cmd_entry = ctk.CTkEntry(
            add_frame,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL),
            corner_radius=8, height=38,
            placeholder_text="输入新命令..."
        )
        self.custom_cmd_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.custom_cmd_entry.bind('<Return>', self._add_custom_command)

        ctk.CTkButton(
            add_frame, text="新增命令",
            corner_radius=8, height=38,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL, "bold"),
            fg_color=ModernStyle.PRIMARY_COLOR,
            hover_color=ModernStyle.PRIMARY_HOVER,
            command=self._add_custom_command
        ).pack(side='right')

        ctk.CTkLabel(
            cmd_inner,
            text="拖拽 ☰ 手柄可调整顺序，主界面和历史记录会按这个顺序显示。",
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL),
            text_color=ModernStyle.TEXT_COLOR,
            wraplength=650
        ).pack(anchor='w')

        # 命令列表（保留 tk.Listbox，customtkinter 无原生列表控件）
        list_frame = ctk.CTkFrame(cmd_inner, fg_color="transparent")
        list_frame.pack(fill='both', expand=True, pady=(8, 10))

        self.command_listbox = tk.Listbox(
            list_frame,
            height=6,
            activestyle='none',
            selectmode='browse',
            font=(ModernStyle.FONT_FAMILY, 13),
            bg=ModernStyle.CARD_BG,
            fg=ModernStyle.TEXT_COLOR,
            selectbackground=ModernStyle.PRIMARY_COLOR,
            selectforeground='#ffffff',
            highlightthickness=1,
            highlightbackground=ModernStyle.BORDER_COLOR,
            highlightcolor=ModernStyle.PRIMARY_COLOR,
            relief='flat',
            bd=0
        )
        self.command_listbox.pack(side='left', fill='both', expand=True)
        self.command_listbox.bind('<ButtonPress-1>', self._start_drag)
        self.command_listbox.bind('<B1-Motion>', self._on_drag)
        self.command_listbox.bind('<ButtonRelease-1>', self._end_drag)
        self.command_listbox.bind('<Motion>', self._on_listbox_hover)
        self.command_listbox.bind('<Leave>', self._on_listbox_leave)

        list_scrollbar = ctk.CTkScrollbar(
            list_frame,
            orientation='vertical',
            command=self.command_listbox.yview,
            button_color=ModernStyle.BORDER_COLOR,
            button_hover_color=ModernStyle.PRIMARY_COLOR
        )
        list_scrollbar.pack(side='right', fill='y')
        self.command_listbox.configure(yscrollcommand=list_scrollbar.set)

        # 操作行
        action_frame = ctk.CTkFrame(cmd_inner, fg_color="transparent")
        action_frame.pack(fill='x')

        ctk.CTkLabel(
            action_frame, text="预设命令不可删除。",
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_SMALL),
            text_color=ModernStyle.TEXT_SECONDARY
        ).pack(side='left')

        ctk.CTkButton(
            action_frame, text="删除选中", width=80,
            corner_radius=8, height=32,
            fg_color=ModernStyle.CARD_BG,
            border_width=1, border_color=ModernStyle.BORDER_COLOR,
            text_color=ModernStyle.DANGER_COLOR,
            hover_color="#fee2e2",
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_SMALL),
            command=self._delete_selected_command
        ).pack(side='right')

        self._refresh_command_listbox()

    def _center_on_parent(self):
        """设置窗口居中屏幕（全程 Tcl 物理像素）"""
        self.update_idletasks()
        raw_geo = str(self.tk.call('wm', 'geometry', self._w))
        phys_w, phys_h = [int(v) for v in raw_geo.split('+')[0].split('x')]
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - phys_w) // 2)
        y = max(0, (sh - phys_h) // 2)
        self.tk.call('wm', 'geometry', self._w, f'+{x}+{y}')

    def _refresh_command_listbox(self, selected_index: Optional[int] = None):
        """刷新命令排序列表"""
        self.command_listbox.delete(0, 'end')
        for index, command in enumerate(self.command_order):
            # 添加 ☰ 手柄前缀，增强拖动视觉提示
            self.command_listbox.insert('end', f"  ☰  {command}")
            if command in PRESET_COMMANDS:
                self.command_listbox.itemconfig(index, fg=ModernStyle.PRIMARY_COLOR)

        if selected_index is not None and self.command_order:
            selected_index = max(0, min(selected_index, len(self.command_order) - 1))
            self.command_listbox.selection_clear(0, 'end')
            self.command_listbox.selection_set(selected_index)
            self.command_listbox.activate(selected_index)

    def _add_custom_command(self, event=None):
        """新增自定义命令"""
        command = self.custom_cmd_entry.get().strip()
        if not command:
            return

        if command in self.command_order:
            messagebox.showinfo("提示", "该命令已存在")
            return

        self.command_order.append(command)
        self.custom_cmd_entry.delete(0, 'end')
        self._refresh_command_listbox(len(self.command_order) - 1)

    def _delete_selected_command(self):
        """删除当前选中的自定义命令"""
        selection = self.command_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要删除的命令")
            return

        index = selection[0]
        command = self.command_order[index]
        if command in PRESET_COMMANDS:
            messagebox.showinfo("提示", "预设命令不能删除")
            return

        self.command_order.pop(index)
        self._refresh_command_listbox(min(index, len(self.command_order) - 1))

    def _start_drag(self, event):
        """开始拖动排序"""
        if not self.command_order:
            return
        self.drag_index = self.command_listbox.nearest(event.y)
        self.command_listbox.configure(cursor="fleur")

    def _on_drag(self, event):
        """拖动调整命令顺序"""
        if self.drag_index is None or not self.command_order:
            return

        target_index = self.command_listbox.nearest(event.y)
        if target_index == self.drag_index or not (0 <= target_index < len(self.command_order)):
            return

        command = self.command_order.pop(self.drag_index)
        self.command_order.insert(target_index, command)
        self.drag_index = target_index
        self._refresh_command_listbox(target_index)

    def _end_drag(self, event=None):
        """结束拖动排序"""
        self.drag_index = None
        self.command_listbox.configure(cursor="")

    def _on_listbox_hover(self, event):
        """命令列表悬停行高亮"""
        index = self.command_listbox.nearest(event.y)
        if 0 <= index < self.command_listbox.size():
            # 先清除所有行的高亮
            for i in range(self.command_listbox.size()):
                if i not in (self.command_listbox.curselection() or ()):
                    self.command_listbox.itemconfig(
                        i, bg=ModernStyle.CARD_BG,
                        fg=ModernStyle.PRIMARY_COLOR if self.command_order[i] in PRESET_COMMANDS else ModernStyle.TEXT_COLOR
                    )
            # 高亮悬停行
            if index not in (self.command_listbox.curselection() or ()):
                self.command_listbox.itemconfig(index, bg=ModernStyle.ACCENT_COLOR)

    def _on_listbox_leave(self, event):
        """命令列表离开时清除悬停高亮"""
        for i in range(self.command_listbox.size()):
            if i not in (self.command_listbox.curselection() or ()):
                self.command_listbox.itemconfig(
                    i, bg=ModernStyle.CARD_BG,
                    fg=ModernStyle.PRIMARY_COLOR if self.command_order[i] in PRESET_COMMANDS else ModernStyle.TEXT_COLOR
                )

    def _browse_terminal(self):
        """浏览选择终端程序"""
        file_path = filedialog.askopenfilename(
            title="选择终端程序",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")]
        )
        if file_path:
            self.terminal_entry.delete(0, "end")
            self.terminal_entry.insert(0, file_path)

    def _save(self):
        """保存设置"""
        self.config["terminal_path"] = self.terminal_entry.get().strip()
        self.config["custom_commands"] = [
            command for command in self.command_order if command not in PRESET_COMMANDS
        ]
        self.config["command_order"] = self.command_order.copy()

        normalized_config = normalize_config(self.config)
        save_config(normalized_config)
        self.parent.config = normalized_config
        self.parent._sync_command_values()
        self.parent._refresh_history()
        self.destroy()


def main():
    """主函数"""
    try:
        app = QuickCliApp()
        app.mainloop()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
