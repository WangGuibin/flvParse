# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files

# --- 平台相关的配置 ---
if sys.platform == 'darwin':
    # macOS specific settings
    ffmpeg_path = '/opt/homebrew/bin/ffmpeg'
    import os
    app_icon = 'app_icon.icns' if os.path.exists('app_icon.icns') else None
    bundle_identifier = 'com.yourcompany.flvparser' # 建议修改为你的标识符
else:
    # Windows specific settings
    ffmpeg_path = 'ffmpeg.exe'
    app_icon = 'app_icon.ico'
    bundle_identifier = None # Not used on Windows

# --- 数据文件 ---
# 将特定平台的 ffmpeg 添加到打包数据中
# 在应用中，ffmpeg 将被放置在根目录
datas = [(ffmpeg_path, '.')]

# --- 主体配置 ---
a = Analysis(
    ['flv_parser.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FLVParser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 设置为 False，因为这是一个 GUI 应用
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None, # 在命令行中指定 for macOS
    codesign_identity=None, # 可选，用于 macOS 代码签名
    entitlements_file=None, # 可-选，用于 macOS
    icon=app_icon
)

# --- macOS 特有的 .app 包配置 ---
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='FLVParser.app',
        icon=app_icon,
        bundle_identifier=bundle_identifier,
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSAppleScriptEnabled': False,
            'CFBundleDisplayName': 'FLV Parser',
            'CFBundleName': 'FLV Parser',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0',
            'NSHumanReadableCopyright': 'Copyright © 2024 Your Name. All rights reserved.'
        }
    )