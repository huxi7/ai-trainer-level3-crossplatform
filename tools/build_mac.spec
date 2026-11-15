# [INPUT]: 依赖 ARM64 Python 环境、Qt Essentials、OCR 模型与精简题库。
# [OUTPUT]: 构建 M 系列 Mac 的独立 .app，隐藏 Dock 与菜单栏入口。
# [POS]: tools 的 Mac 打包声明；与 Windows 共用应用代码和资源。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
from pathlib import Path
import json
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
app_identifier = json.loads((root / 'macos_identity.json').read_text(encoding='utf-8'))['identifier']
datas = [(str(root / 'bank.sqlite3'), '.'), (str(root / 'defaults.json'), '.'),
         (str(root / 'models'), 'models'), (str(root / 'verification'), 'verification')]
datas += collect_data_files('rapidocr', excludes=['models/*', '**/__pycache__/*'])
hidden = collect_submodules('rapidocr') + ['Quartz', 'AppKit', 'Foundation', 'objc', 'PySide6.QtNetwork']
a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=[], datas=datas,
             hiddenimports=hidden, hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['torch', 'paddle', 'tensorflow', 'openvino', 'matplotlib', 'IPython',
                       'PySide6.QtPdf', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtOpenGL',
                       'PySide6.QtTest', 'sympy'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='三级助手', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          target_arch='arm64', codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='三级助手-M系列')
app = BUNDLE(coll, name='三级助手.app', icon=None, bundle_identifier=app_identifier,
             info_plist={'LSUIElement': True, 'NSHighResolutionCapable': True,
                         'LSMinimumSystemVersion': '11.0', 'CFBundleShortVersionString': '0.3.1'})
