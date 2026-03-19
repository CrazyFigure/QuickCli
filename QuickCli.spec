# -*- mode: python ; coding: utf-8 -*-

import json
from pathlib import Path


from PyInstaller.utils.hooks import collect_data_files
ctk_datas = collect_data_files('customtkinter')

project_dir = Path(SPECPATH)
icon_file = project_dir / "icon.ico"
metadata_file = project_dir / "app_metadata.json"
metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
exe_stem = Path(str(metadata["exe_name"])).stem

version_parts = [int(part) for part in str(metadata["version"]).split(".")]
version_parts = (version_parts + [0, 0, 0, 0])[:4]
version_text = ".".join(str(part) for part in version_parts)

version_file = project_dir / "build" / "version_info.txt"
version_file.parent.mkdir(parents=True, exist_ok=True)
version_file.write_text(
    "\n".join(
        [
            "VSVersionInfo(",
            "  ffi=FixedFileInfo(",
            f"    filevers=({version_parts[0]}, {version_parts[1]}, {version_parts[2]}, {version_parts[3]}),",
            f"    prodvers=({version_parts[0]}, {version_parts[1]}, {version_parts[2]}, {version_parts[3]}),",
            "    mask=0x3F,",
            "    flags=0x0,",
            "    OS=0x40004,",
            "    fileType=0x1,",
            "    subtype=0x0,",
            "    date=(0, 0)",
            "  ),",
            "  kids=[",
            "    StringFileInfo([",
            "      StringTable(",
            "        '080404B0',",
            "        [",
            f"          StringStruct('CompanyName', '{metadata['publisher']}'),",
            f"          StringStruct('FileDescription', '{metadata['app_name']}'),",
            f"          StringStruct('FileVersion', '{version_text}'),",
            f"          StringStruct('InternalName', '{metadata['app_name']}'),",
            f"          StringStruct('OriginalFilename', '{metadata['exe_name']}'),",
            f"          StringStruct('ProductName', '{metadata['app_name']}'),",
            f"          StringStruct('ProductVersion', '{version_text}')",
            "        ]",
            "      )",
            "    ]),",
            "    VarFileInfo([VarStruct('Translation', [2052, 1200])])",
            "  ]",
            ")",
        ]
    ),
    encoding="utf-8",
)


a = Analysis(
    ["main.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[
        (str(icon_file), "."),
        (str(metadata_file), "."),
        *ctk_datas,
    ],
    hiddenimports=['PIL', 'pystray._win32', 'customtkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_stem,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(icon_file)],
    version=str(version_file),
)
