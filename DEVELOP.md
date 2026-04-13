# QuickCli 开发说明

`README.md` 面向普通使用者；本文档面向开发、打包和发布维护者。

## 开发环境

- Windows 10 / 11
- Python 3.8+
- 建议安装 PowerShell 7
- 构建安装版时需安装 [Inno Setup 6](https://jrsoftware.org/isinfo.php)

安装依赖并启动开发版：

```powershell
pip install -r requirements.txt
python main.py
```

## 项目结构

```text
QuickCli/
├─ installer/
│  └─ QuickCli.iss
├─ QuickCli.spec
├─ build.ps1
├─ main.py
├─ requirements.txt
├─ app_metadata.json
├─ icon.ico
├─ logo.png
├─ README.md
└─ DEVELOP.md
```

关键文件说明：

- `main.py`：主程序入口、界面、托盘和更新逻辑
- `app_metadata.json`：版本号、应用名、发布者、安装包名等统一元数据
- `QuickCli.spec`：PyInstaller 打包配置，读取 `app_metadata.json` 生成 exe 版本信息
- `build.ps1`：本地构建脚本，可选输出安装版
- `installer/QuickCli.iss`：Inno Setup 安装脚本

## 版本维护

版本号统一维护在 `app_metadata.json`：

```json
{
  "version": "2.1.4"
}
```

更新这个字段后，以下内容会自动跟随：

- 主界面和设置页右下角版本显示
- PyInstaller 生成的 exe 文件版本
- Inno Setup 安装包版本

## 构建

构建便携版：

```powershell
pip install -r requirements.txt
pip install pyinstaller
python -m PyInstaller .\QuickCli.spec --noconfirm --clean
```

输出文件：`dist\QuickCli.exe`

构建安装版：

```powershell
.\build.ps1 -Installer
```

输出文件：`output\QuickCli-Setup.exe`

## 发布流程

建议流程：

1. 从 `main` 切出版本分支，例如 `v2.1.4`
2. 修改 `app_metadata.json` 中的版本号
3. 完成本地验证和打包检查
4. 提交版本分支
5. 创建同名 tag，例如 `v2.1.4`
6. 推送分支和 tag，触发 GitHub Actions Release 构建

GitHub Actions 会在推送 `v*` tag 后生成 Release 构建产物。
