@echo off
cd /d "%~dp0"

REM 清理可能干扰的 Python 环境变量
set PYTHONPATH=
set PYTHONHOME=

REM 使用用户安装的 Python 运行
start "" "C:\Users\21573\AppData\Local\Python\bin\pythonw.exe" "C:\Software\WorkSpace\QuickCli\main.py"