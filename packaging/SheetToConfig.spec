# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


REPO_ROOT = Path(SPECPATH).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sheet_to_config.version import __version__


protobuf_hiddenimports = collect_submodules('google.protobuf')

a = Analysis(
    [str(REPO_ROOT / 'SheetToConfig.py')],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=[
        (str(REPO_ROOT / 'sheet_to_config' / 'assets'), 'sheet_to_config/assets'),
        (
            str(REPO_ROOT / 'sheet_to_config' / 'i18n' / 'catalogs'),
            'sheet_to_config/i18n/catalogs',
        ),
    ],
    hiddenimports=[
        'sheet_to_config.utils.exporter.types',
        'sheet_to_config.utils.exporter.type_registry',
        'sheet_to_config.utils.exporter.converter',
        'sheet_to_config.utils.exporter.reader',
        'sheet_to_config.utils.exporter.core',
        'sheet_to_config.utils.exporter.constraints',
        'sheet_to_config.utils.exporter.reference_validator',
        'sheet_to_config.utils.exporter.template',
        'sheet_to_config.utils.exporter.type_converter',
        'sheet_to_config.utils.exporter.exporters.json_exporter',
        'sheet_to_config.utils.exporter.exporters.lua_exporter',
        'sheet_to_config.utils.export_handler',
        'sheet_to_config.utils.import_handler',
        'sheet_to_config.utils.updater',
        'sheet_to_config.utils.project_manager',
        'sheet_to_config.app_paths',
        'openpyxl',
    ] + protobuf_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除调试和测试模块
        'pytest',
        'unittest',
        'pdb',
        'doctest',
        # 排除 tkinter（使用 PyQt5）
        'tkinter',
        'Tkinter',
        '_tkinter',
        # 排除不需要的 PyQt5 组件（已按模块细化）
        'PyQt5.QtWebEngine',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.Qt3D',
        'PyQt5.Qt3DCore',
        'PyQt5.Qt3DRender',
        'PyQt5.Qt3DInput',
        'PyQt5.Qt3DLogic',
        'PyQt5.Qt3DExtras',
        'PyQt5.QtCharts',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtBluetooth',
        'PyQt5.QtSql',
        'PyQt5.QtTest',
        'PyQt5.QtDesigner',
        'PyQt5.QtUiTools',
        'PyQt5.QtXml',
        'PyQt5.QtXmlPatterns',
        'PyQt5.QtNetwork',
        'PyQt5.QtHelp',
        'PyQt5.QtLocation',
        'PyQt5.QtNfc',
        'PyQt5.QtPositioning',
        'PyQt5.QtSensors',
        'PyQt5.QtSerialPort',
        'PyQt5.QtWinExtras',
        'PyQt5.QtX11Extras',
        'PyQt5.QtMacExtras',
        # 排除其他大型库
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFilter',
        'Crypto',
        'cryptography',
        # 排除 Python 标准库中不需要的模块
        'curses',
        'dbm',
        'idlelib',
        'lib2to3',
        'multiprocessing.popen_spawn_win32',
        'test',
        'turtledemo',
        'venv',
        'wsgiref',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='SheetToConfig',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='SheetToConfig',
    )
    app = BUNDLE(
        coll,
        name='SheetToConfig.app',
        icon=None,
        bundle_identifier='com.liushafeiniao.sheettoconfig',
        info_plist={
            'CFBundleDisplayName': 'SheetToConfig',
            'CFBundleShortVersionString': __version__,
            'CFBundleVersion': __version__,
            'NSHighResolutionCapable': True,
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='SheetToConfig',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
