#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuickCli - Windows 快速命令行启动器
使用标准 tkinter，无需额外依赖
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

METADATA_FILE = "app_metadata.json"


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
        "preset_commands": ["claude", "codex", "iflow"]
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

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

# 应用信息
APP_NAME = APP_METADATA["app_name"]
APP_VERSION = APP_METADATA["version"]
APP_ID = APP_METADATA["app_user_model_id"]
PRESET_COMMANDS = list(APP_METADATA.get("preset_commands", ["claude", "codex", "iflow"]))

# 默认配置
DEFAULT_CONFIG = {
    "terminal_path": r"C:\Program Files\PowerShell\7\pwsh.exe",
    "custom_commands": [],
    "command_order": PRESET_COMMANDS.copy(),
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

    try:
        window.update_idletasks()
        hwnd = window.winfo_id()
        hicon = ctypes.windll.user32.LoadImageW(
            0,
            str(ICON_FILE),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE
        )
        if hicon:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
    except Exception:
        pass


def _dedupe_commands(commands) -> List[str]:
    """去重并清理命令列表"""
    normalized = []
    seen = set()
    for cmd in commands or []:
        text = str(cmd).strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def normalize_config(raw_config: dict) -> dict:
    """兼容旧版配置并规范化命令数据"""
    config = {
        "terminal_path": raw_config.get("terminal_path", DEFAULT_CONFIG["terminal_path"]),
        "history": raw_config.get("history", DEFAULT_CONFIG["history"]),
        "max_history": raw_config.get("max_history", DEFAULT_CONFIG["max_history"])
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

    config["custom_commands"] = merged_custom
    config["command_order"] = command_order or PRESET_COMMANDS.copy()
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
    """现代化样式配置 - 亮色主题"""
    
    # 颜色方案 (亮色主题)
    BG_COLOR = "#f5f5f5"           # 主背景 - 浅灰白色
    CARD_BG = "#ffffff"            # 卡片背景 - 纯白
    ACCENT_COLOR = "#e3f2fd"       # 强调色 - 浅蓝
    ACCENT_HOVER = "#bbdefb"       # 悬停色 - 稍深蓝
    PRIMARY_COLOR = "#1976d2"      # 主色调 - 蓝色
    PRIMARY_HOVER = "#1565c0"      # 主色悬停
    TEXT_COLOR = "#212121"         # 主文字 - 深灰
    TEXT_SECONDARY = "#757575"     # 次要文字 - 中灰
    BORDER_COLOR = "#e0e0e0"       # 边框色 - 浅灰
    
    # 字体
    FONT_FAMILY = "Segoe UI"
    FONT_SIZE_TITLE = 20
    FONT_SIZE_NORMAL = 11
    FONT_SIZE_SMALL = 10
    FONT_SIZE_COMBO = 12


class QuickCliApp(tk.Tk):
    """QuickCli 主应用"""
    
    def __init__(self):
        super().__init__()
        
        # 加载配置
        self.config = load_config()
        
        # 设置窗口
        self.title(APP_NAME)
        # 增大默认窗口尺寸
        self.geometry("1200x1200")
        self.minsize(600, 750)
        self.configure(bg=ModernStyle.BG_COLOR)
        
        # 设置图标
        apply_window_icon(self)
        
        # 设置样式
        self._setup_styles()
        
        # 创建 UI
        self._create_ui()
        
        # 刷新历史记录列表
        self._refresh_history()
        
        # 居中窗口
        self._center_window()
    
    def _setup_styles(self):
        """设置 ttk 样式"""
        style = ttk.Style()
        
        # 使用 clam 主题作为基础
        style.theme_use('clam')
        
        # 配置整体样式
        style.configure('.',
            background=ModernStyle.BG_COLOR,
            foreground=ModernStyle.TEXT_COLOR,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL)
        )
        
        # Frame 样式
        style.configure('Card.TFrame',
            background=ModernStyle.CARD_BG,
            bordercolor=ModernStyle.BORDER_COLOR,
            relief='flat'
        )
        
        style.configure('TFrame',
            background=ModernStyle.BG_COLOR
        )
        
        # Label 样式
        style.configure('Title.TLabel',
            background=ModernStyle.BG_COLOR,
            foreground=ModernStyle.TEXT_COLOR,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_TITLE, 'bold')
        )
        
        style.configure('Header.TLabel',
            background=ModernStyle.CARD_BG,
            foreground=ModernStyle.TEXT_COLOR,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL, 'bold')
        )
        
        style.configure('TLabel',
            background=ModernStyle.BG_COLOR,
            foreground=ModernStyle.TEXT_COLOR,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL)
        )
        
        style.configure('Card.TLabel',
            background=ModernStyle.CARD_BG,
            foreground=ModernStyle.TEXT_COLOR,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL)
        )
        
        # Entry 样式
        style.configure('TEntry',
            fieldbackground=ModernStyle.CARD_BG,
            foreground=ModernStyle.TEXT_COLOR,
            insertcolor=ModernStyle.TEXT_COLOR,
            bordercolor=ModernStyle.BORDER_COLOR,
            lightcolor=ModernStyle.PRIMARY_COLOR,
            darkcolor=ModernStyle.BORDER_COLOR
        )
        
        # Button 样式
        style.configure('Accent.TButton',
            background=ModernStyle.PRIMARY_COLOR,
            foreground='#ffffff',
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL, 'bold'),
            bordercolor=ModernStyle.PRIMARY_COLOR,
            relief='flat',
            padding=(20, 10)
        )
        
        style.map('Accent.TButton',
            background=[('active', ModernStyle.PRIMARY_HOVER)],
            foreground=[('active', '#ffffff')]
        )
        
        style.configure('Outline.TButton',
            background=ModernStyle.BG_COLOR,
            foreground=ModernStyle.TEXT_COLOR,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL),
            bordercolor=ModernStyle.BORDER_COLOR,
            relief='flat',
            padding=(15, 8)
        )
        
        style.map('Outline.TButton',
            background=[('active', ModernStyle.CARD_BG)],
            foreground=[('active', ModernStyle.TEXT_COLOR)]
        )

        style.configure('Dropdown.TMenubutton',
            background="#f7fafc",
            foreground=ModernStyle.TEXT_COLOR,
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_COMBO),
            bordercolor="#9fb3c8",
            lightcolor="#9fb3c8",
            darkcolor="#9fb3c8",
            arrowcolor=ModernStyle.TEXT_COLOR,
            relief='solid',
            borderwidth=1,
            padding=(12, 7)
        )

        style.map('Dropdown.TMenubutton',
            background=[('active', '#eef4fb')],
            foreground=[('active', ModernStyle.TEXT_COLOR)]
        )
        
        # Combobox 样式 - 修复显示问题
        style.configure('TCombobox',
            fieldbackground=ModernStyle.CARD_BG,
            background=ModernStyle.PRIMARY_COLOR,
            foreground=ModernStyle.TEXT_COLOR,
            arrowcolor=ModernStyle.TEXT_COLOR,
            bordercolor=ModernStyle.BORDER_COLOR,
            lightcolor=ModernStyle.PRIMARY_COLOR,
            darkcolor=ModernStyle.BORDER_COLOR,
            padding=(10, 7, 10, 7),
            arrowsize=16
        )
        
        style.map('TCombobox',
            fieldbackground=[('readonly', ModernStyle.CARD_BG)],
            selectbackground=[('readonly', ModernStyle.PRIMARY_COLOR)],
            selectforeground=[('readonly', '#ffffff')],
            foreground=[('readonly', ModernStyle.TEXT_COLOR)]
        )
        
        # Scrollbar 样式
        style.configure('TScrollbar',
            background=ModernStyle.CARD_BG,
            troughcolor=ModernStyle.BG_COLOR,
            arrowcolor=ModernStyle.TEXT_COLOR,
            bordercolor=ModernStyle.BORDER_COLOR
        )

        # 下拉框下拉列表字体
        self.option_add(
            '*TCombobox*Listbox.font',
            f'{ModernStyle.FONT_FAMILY} {ModernStyle.FONT_SIZE_COMBO}'
        )
    
    def _create_ui(self):
        """创建用户界面"""
        # 主容器
        main_frame = ttk.Frame(self, style='TFrame')
        main_frame.pack(fill='both', expand=True, padx=25, pady=25)
        
        # 标题
        title_label = ttk.Label(
            main_frame,
            text="🚀 QuickCli",
            style='Title.TLabel'
        )
        title_label.pack(pady=(0, 25))
        
        # === 目录选择区域 ===
        dir_card = ttk.Frame(main_frame, style='Card.TFrame')
        dir_card.pack(fill='x', pady=(0, 15))
        
        # 目录卡片内容
        dir_content = ttk.Frame(dir_card, style='Card.TFrame')
        dir_content.pack(fill='x', padx=15, pady=15)
        
        dir_label = ttk.Label(dir_content, text="📁 选择目录", style='Header.TLabel')
        dir_label.pack(anchor='w', pady=(0, 10))
        
        dir_input_frame = ttk.Frame(dir_content, style='Card.TFrame')
        dir_input_frame.pack(fill='x')
        
        self.dir_entry = ttk.Entry(dir_input_frame, font=(ModernStyle.FONT_FAMILY, 11))
        self.dir_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.dir_entry.insert(0, normalize_windows_path(str(APP_DIR)))
        
        browse_btn = ttk.Button(
            dir_input_frame,
            text="浏览",
            style='Outline.TButton',
            command=self._browse_directory
        )
        browse_btn.pack(side='right')
        
        # === 命令选择区域 ===
        cmd_card = ttk.Frame(main_frame, style='Card.TFrame')
        cmd_card.pack(fill='x', pady=(0, 15))
        
        cmd_content = ttk.Frame(cmd_card, style='Card.TFrame')
        cmd_content.pack(fill='x', padx=15, pady=15)
        
        cmd_label = ttk.Label(cmd_content, text="⚡ 选择命令", style='Header.TLabel')
        cmd_label.pack(anchor='w', pady=(0, 10))
        
        cmd_input_frame = ttk.Frame(cmd_content, style='Card.TFrame')
        cmd_input_frame.pack(fill='x')

        # 命令下拉框
        self.cmd_var = tk.StringVar()
        self.cmd_combo = self._create_command_dropdown(
            cmd_input_frame,
            self.cmd_var,
            [],
            width=14
        )
        self.cmd_combo.pack(side='left', padx=(0, 15))
        self._sync_command_values()
        
        # 打开按钮
        open_btn = ttk.Button(
            cmd_input_frame,
            text="▶ 打开终端",
            style='Accent.TButton',
            command=self._open_terminal
        )
        open_btn.pack(side='left')
        
        # === 历史记录区域 ===
        history_card = ttk.Frame(main_frame, style='Card.TFrame')
        history_card.pack(fill='both', expand=True, pady=(0, 15))
        
        history_header = ttk.Frame(history_card, style='Card.TFrame')
        history_header.pack(fill='x', padx=15, pady=(15, 10))
        
        history_label = ttk.Label(history_header, text="📋 历史记录", style='Header.TLabel')
        history_label.pack(side='left')
        
        clear_btn = ttk.Button(
            history_header,
            text="清空",
            style='Outline.TButton',
            command=self._clear_history
        )
        clear_btn.pack(side='right')
        
        # 历史记录滚动区域
        history_scroll_frame = ttk.Frame(history_card, style='Card.TFrame')
        history_scroll_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # 创建 Canvas 和 Scrollbar
        self.history_canvas = tk.Canvas(
            history_scroll_frame,
            bg=ModernStyle.CARD_BG,
            highlightthickness=0,
            bd=0
        )
        self.history_scrollbar = tk.Scrollbar(
            history_scroll_frame,
            orient='vertical',
            command=self.history_canvas.yview,
            width=14,
            relief='flat',
            bd=0,
            bg="#d6dde6",
            activebackground=ModernStyle.PRIMARY_COLOR,
            troughcolor="#edf2f7",
            highlightthickness=0
        )
        
        self.history_inner = ttk.Frame(self.history_canvas, style='Card.TFrame')
        
        self.history_canvas.configure(yscrollcommand=self.history_scrollbar.set)
        
        self.history_scrollbar.pack(side='right', fill='y')
        self.history_canvas.pack(side='left', fill='both', expand=True)
        
        self.history_window = self.history_canvas.create_window(
            (0, 0),
            window=self.history_inner,
            anchor='nw'
        )
        
        # 绑定事件
        self.history_inner.bind('<Configure>', self._on_frame_configure)
        self.history_canvas.bind('<Configure>', self._on_canvas_configure)
        
        # === 设置按钮 ===
        settings_btn = ttk.Button(
            main_frame,
            text="⚙ 设置",
            style='Outline.TButton',
            command=self._open_settings
        )
        settings_btn.pack(pady=(0, 10))
    
    def _on_frame_configure(self, event=None):
        """更新滚动区域"""
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox('all'))
        self._update_history_scrollbar()
    
    def _on_canvas_configure(self, event):
        """调整内部框架宽度"""
        self.history_canvas.itemconfig(self.history_window, width=event.width)
        self._update_history_scrollbar()
    
    def _center_window(self):
        """窗口居中"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
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
            # 启动终端
            subprocess.Popen(
                [terminal_path, "-NoExit", "-Command", f"cd '{directory}'; {cmd}"],
                cwd=directory,
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
        self._set_dropdown_values(self.cmd_combo, self.cmd_var, commands, selected)

    def _refresh_history(self):
        """刷新历史记录列表"""
        # 清空现有记录
        for widget in self.history_inner.winfo_children():
            widget.destroy()
        
        history = self.config.get("history", [])
        
        if not history:
            empty_label = ttk.Label(
                self.history_inner,
                text="暂无历史记录",
                foreground=ModernStyle.TEXT_SECONDARY,
                background=ModernStyle.CARD_BG,
                font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_NORMAL)
            )
            empty_label.pack(pady=30)
            self.history_canvas.yview_moveto(0)
            self._update_history_scrollbar()
            return
        
        available_commands = get_available_commands(self.config)

        for item in history:
            self._create_history_item(item, available_commands)

        self.history_inner.update_idletasks()
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox('all'))
        self.history_canvas.yview_moveto(0)
        self._update_history_scrollbar()

    def _create_history_item(self, item: dict, available_commands: list):
        """创建历史记录项"""
        path = normalize_windows_path(item.get("path", ""))
        saved_cmd = item.get("command", "claude")
        item_commands = available_commands.copy()
        if saved_cmd and saved_cmd not in item_commands:
            item_commands.append(saved_cmd)
        
        # 历史记录项容器
        item_frame = tk.Frame(
            self.history_inner,
            bg=ModernStyle.ACCENT_COLOR,
            bd=0,
            highlightthickness=1,
            highlightbackground=ModernStyle.BORDER_COLOR,
            highlightcolor=ModernStyle.BORDER_COLOR
        )
        item_frame.pack(fill='x', pady=4, ipady=8)
        
        # 内部布局
        inner_frame = tk.Frame(item_frame, bg=ModernStyle.ACCENT_COLOR)
        inner_frame.pack(fill='x', padx=12, pady=4)
        inner_frame.grid_columnconfigure(0, weight=1)
        
        # 目录路径
        path_label = tk.Label(
            inner_frame,
            text="",
            font=(ModernStyle.FONT_FAMILY, 12),
            fg=ModernStyle.TEXT_COLOR,
            bg=ModernStyle.ACCENT_COLOR,
            anchor='w'
        )
        path_label.grid(row=0, column=0, sticky='ew', padx=(0, 12))
        path_label.bind(
            '<Configure>',
            lambda e, label=path_label, full_path=path: self._update_path_label(label, full_path)
        )
        self.after_idle(
            lambda label=path_label, full_path=path: self._update_path_label(label, full_path)
        )
        
        # 命令下拉框
        cmd_var = tk.StringVar(value=saved_cmd)
        cmd_combo = self._create_command_dropdown(
            inner_frame,
            cmd_var,
            item_commands,
            width=10
        )
        cmd_combo.grid(row=0, column=1, padx=(0, 8))
        
        # 打开按钮
        def make_open_handler(p, v):
            return lambda: self._open_terminal(p, v.get())
        
        open_btn = tk.Button(
            inner_frame,
            text="▶",
            font=(ModernStyle.FONT_FAMILY, 11, 'bold'),
            fg='#ffffff',
            bg=ModernStyle.PRIMARY_COLOR,
            activebackground=ModernStyle.PRIMARY_HOVER,
            activeforeground='#ffffff',
            bd=0,
            padx=12,
            pady=4,
            cursor='hand2',
            command=make_open_handler(path, cmd_var)
        )
        open_btn.grid(row=0, column=2)

        delete_btn = tk.Button(
            inner_frame,
            text="删除",
            font=(ModernStyle.FONT_FAMILY, 10),
            fg="#c62828",
            bg=ModernStyle.CARD_BG,
            activebackground="#ffcdd2",
            activeforeground="#b71c1c",
            bd=0,
            padx=12,
            pady=4,
            cursor='hand2',
            command=lambda p=path: self._delete_history_item(p)
        )
        delete_btn.grid(row=0, column=3, padx=(8, 0))
        
        # 悬停效果
        def on_enter(e):
            item_frame.configure(bg=ModernStyle.ACCENT_HOVER)
            inner_frame.configure(bg=ModernStyle.ACCENT_HOVER)
            path_label.configure(bg=ModernStyle.ACCENT_HOVER)
        
        def on_leave(e):
            item_frame.configure(bg=ModernStyle.ACCENT_COLOR)
            inner_frame.configure(bg=ModernStyle.ACCENT_COLOR)
            path_label.configure(bg=ModernStyle.ACCENT_COLOR)
        
        item_frame.bind('<Enter>', on_enter)
        item_frame.bind('<Leave>', on_leave)
        inner_frame.bind('<Enter>', on_enter)
        inner_frame.bind('<Leave>', on_leave)
        path_label.bind('<Enter>', on_enter)
        path_label.bind('<Leave>', on_leave)

    def _create_command_dropdown(self, parent, variable: tk.StringVar, values, width: int):
        """创建命令下拉菜单"""
        dropdown = ttk.OptionMenu(parent, variable, None)
        dropdown.configure(style='Dropdown.TMenubutton', width=width)
        dropdown.bind('<MouseWheel>', lambda e: 'break')
        self._set_dropdown_values(dropdown, variable, values, variable.get().strip())
        return dropdown

    def _set_dropdown_values(self, dropdown, variable: tk.StringVar, values, selected: str = ""):
        """更新下拉菜单选项"""
        normalized_values = _dedupe_commands(values)
        current = selected if selected in normalized_values else (normalized_values[0] if normalized_values else "")
        variable.set(current)
        dropdown.set_menu(current, *normalized_values)
        menu = dropdown['menu']
        menu.configure(
            font=(ModernStyle.FONT_FAMILY, ModernStyle.FONT_SIZE_COMBO),
            bg=ModernStyle.CARD_BG,
            fg=ModernStyle.TEXT_COLOR,
            activebackground=ModernStyle.ACCENT_HOVER,
            activeforeground=ModernStyle.TEXT_COLOR,
            bd=0
        )

    def _update_path_label(self, label: tk.Label, full_path: str):
        """根据可用宽度优先展示路径右侧内容"""
        available_width = max(label.winfo_width() - 8, 40)
        font = tkfont.Font(font=label.cget('font'))
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

    def _update_history_scrollbar(self):
        """根据内容高度更新滚动条显示"""
        bbox = self.history_canvas.bbox('all')
        if not bbox:
            return

        content_height = bbox[3] - bbox[1]
        canvas_height = self.history_canvas.winfo_height()
        needs_scroll = content_height > canvas_height + 2

        if needs_scroll:
            if not self.history_scrollbar.winfo_ismapped():
                self.history_scrollbar.pack(side='right', fill='y')
        else:
            self.history_canvas.yview_moveto(0)
            if self.history_scrollbar.winfo_ismapped():
                self.history_scrollbar.pack_forget()

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


class SettingsWindow(tk.Toplevel):
    """设置窗口"""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.parent = parent
        self.config = normalize_config(parent.config.copy())
        self.command_order = get_available_commands(self.config)
        self.drag_index = None
        
        self.title("设置")
        self.withdraw()
        self.resizable(False, False)
        self.configure(bg=ModernStyle.BG_COLOR)
        
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
        main_frame = ttk.Frame(self, style='TFrame')
        main_frame.pack(fill='both', expand=True, padx=25, pady=25)
        
        # === 终端设置 ===
        terminal_label = ttk.Label(
            main_frame,
            text="💻 终端设置",
            style='Title.TLabel'
        )
        terminal_label.pack(anchor='w', pady=(0, 15))
        
        terminal_card = ttk.Frame(main_frame, style='Card.TFrame')
        terminal_card.pack(fill='x', pady=(0, 20))
        
        terminal_inner = ttk.Frame(terminal_card, style='Card.TFrame')
        terminal_inner.pack(fill='x', padx=15, pady=15)
        
        ttk.Label(terminal_inner, text="终端路径:", style='Card.TLabel').pack(anchor='w')
        
        terminal_input_frame = ttk.Frame(terminal_inner, style='Card.TFrame')
        terminal_input_frame.pack(fill='x', pady=(8, 0))
        
        self.terminal_entry = ttk.Entry(terminal_input_frame, font=(ModernStyle.FONT_FAMILY, 11))
        self.terminal_entry.insert(0, self.config.get("terminal_path", ""))
        self.terminal_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ttk.Button(
            terminal_input_frame,
            text="浏览",
            style='Outline.TButton',
            command=self._browse_terminal
        ).pack(side='right')
        
        # === 命令设置 ===
        cmd_label = ttk.Label(
            main_frame,
            text="📝 命令设置",
            style='Title.TLabel'
        )
        cmd_label.pack(anchor='w', pady=(0, 15))
        
        cmd_card = ttk.Frame(main_frame, style='Card.TFrame')
        cmd_card.pack(fill='x', pady=(0, 20))
        
        cmd_inner = ttk.Frame(cmd_card, style='Card.TFrame')
        cmd_inner.pack(fill='x', padx=15, pady=15)
        
        ttk.Label(
            cmd_inner,
            text="预设命令固定包含 claude / codex / iflow，自定义命令可新增、删除，并支持拖动排序。",
            style='Card.TLabel'
        ).pack(anchor='w')

        add_frame = ttk.Frame(cmd_inner, style='Card.TFrame')
        add_frame.pack(fill='x', pady=(12, 15))

        self.custom_cmd_entry = ttk.Entry(
            add_frame,
            font=(ModernStyle.FONT_FAMILY, 11)
        )
        self.custom_cmd_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.custom_cmd_entry.bind('<Return>', self._add_custom_command)

        ttk.Button(
            add_frame,
            text="新增命令",
            style='Accent.TButton',
            command=self._add_custom_command
        ).pack(side='right')

        ttk.Label(
            cmd_inner,
            text="拖动下方列表可调整顺序，主界面和历史记录会按这个顺序显示。",
            style='Card.TLabel'
        ).pack(anchor='w')

        list_frame = ttk.Frame(cmd_inner, style='Card.TFrame')
        list_frame.pack(fill='x', pady=(8, 10))

        self.command_listbox = tk.Listbox(
            list_frame,
            height=8,
            activestyle='none',
            selectmode='browse',
            font=(ModernStyle.FONT_FAMILY, 12),
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

        list_scrollbar = ttk.Scrollbar(
            list_frame,
            orient='vertical',
            command=self.command_listbox.yview
        )
        list_scrollbar.pack(side='right', fill='y')
        self.command_listbox.configure(yscrollcommand=list_scrollbar.set)

        action_frame = ttk.Frame(cmd_inner, style='Card.TFrame')
        action_frame.pack(fill='x')

        ttk.Label(
            action_frame,
            text="预设命令不可删除。",
            style='Card.TLabel'
        ).pack(side='left')

        ttk.Button(
            action_frame,
            text="删除选中",
            style='Outline.TButton',
            command=self._delete_selected_command
        ).pack(side='right')

        self._refresh_command_listbox()
        
        # === 按钮区域 ===
        btn_frame = ttk.Frame(main_frame, style='TFrame')
        btn_frame.pack(fill='x', pady=(20, 0))
        
        ttk.Button(
            btn_frame,
            text="保存",
            style='Accent.TButton',
            command=self._save
        ).pack(side='right', padx=(10, 0))
        
        ttk.Button(
            btn_frame,
            text="取消",
            style='Outline.TButton',
            command=self.destroy
        ).pack(side='right')

    def _center_on_parent(self):
        """相对父窗口居中显示"""
        self.update_idletasks()
        width = max(self.winfo_reqwidth(), 760)
        height = max(self.winfo_reqheight(), 640)
        x = self.parent.winfo_x() + max((self.parent.winfo_width() - width) // 2, 0)
        y = self.parent.winfo_y() + max((self.parent.winfo_height() - height) // 2, 0)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def _refresh_command_listbox(self, selected_index: Optional[int] = None):
        """刷新命令排序列表"""
        self.command_listbox.delete(0, 'end')
        for index, command in enumerate(self.command_order):
            self.command_listbox.insert('end', command)
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
    app = QuickCliApp()
    app.mainloop()


if __name__ == "__main__":
    main()
