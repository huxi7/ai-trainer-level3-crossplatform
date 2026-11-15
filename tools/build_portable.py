# [INPUT]: 依赖固定版本环境、官方 CPython Windows 运行库与可选本地报告。
# [OUTPUT]: 生成 Windows 免安装目录、M 系列 Mac 运行包及 ZIP。
# [POS]: tools 的交付入口；打包全部依赖，不要求使用者安装 Python。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.build-cache'
DIST = ROOT / 'dist'


def run(command):
    subprocess.run(list(map(str, command)), cwd=ROOT, check=True)


def copy_resources(target):
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'main.py', target / 'main.py')
    shutil.copytree(ROOT / 'assistant', target / 'assistant', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'CLAUDE.md'))
    shutil.copytree(ROOT / 'models', target / 'models', dirs_exist_ok=True, ignore=shutil.ignore_patterns('CLAUDE.md'))
    shutil.copytree(ROOT / 'verification', target / 'verification', dirs_exist_ok=True, ignore=shutil.ignore_patterns('CLAUDE.md'))
    for name in ('bank.sqlite3', 'defaults.json'):
        shutil.copyfile(ROOT / name, target / name)


def download(url, destination):
    if not destination.exists():
        temporary = destination.with_suffix('.download')
        with urllib.request.urlopen(url, timeout=45) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output)
        temporary.replace(destination)


def archive(folder):
    destination = DIST / (folder.name + '.zip')
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(folder.rglob('*')):
            if path.is_file() or path.is_symlink():
                output.write(path, path.relative_to(folder.parent).as_posix())
    with zipfile.ZipFile(destination) as output:
        assert output.testzip() is None
    print(json.dumps({'archive': destination.name, 'mib': round(destination.stat().st_size / 1024**2, 1)}, ensure_ascii=False), flush=True)


def trim_qt(site):
    qt = site / 'PySide6'
    keep = {'QtCore.pyd', 'QtGui.pyd', 'QtWidgets.pyd', 'QtNetwork.pyd', 'QtCore.abi3.so',
            'QtGui.abi3.so', 'QtWidgets.abi3.so', 'QtNetwork.abi3.so', 'Qt6Core.dll', 'Qt6Gui.dll',
            'Qt6Widgets.dll', 'Qt6Network.dll'}
    for path in qt.glob('Qt*'):
        if path.is_file() and path.suffix in {'.pyd', '.dll'} and path.name not in keep:
            path.unlink()
    plugins = qt / 'plugins'
    if plugins.exists():
        for path in plugins.iterdir():
            if path.name not in {'platforms', 'imageformats', 'styles', 'tls', 'iconengines'}:
                if path.is_dir():
                    shutil.rmtree(path)
        platforms = plugins / 'platforms'
        if platforms.exists():
            for path in platforms.iterdir():
                if path.name != 'qwindows.dll':
                    path.unlink()
    for name in ('include', 'typesystems', 'glue', 'doc', 'qml', 'metatypes', 'scripts', 'examples'):
        shutil.rmtree(qt / name, ignore_errors=True)
    for pattern in ('*.exe', '*.lib', '*.pdb', '*.pyi'):
        for path in qt.rglob(pattern):
            path.unlink()
    for name in ('pyside6qml.abi3.dll', 'plugins/iconengines/qsvgicon.dll',
                 'plugins/imageformats/qsvg.dll', 'plugins/imageformats/qpdf.dll'):
        (qt / name).unlink(missing_ok=True)
    shutil.rmtree(site / 'cv2/qt', ignore_errors=True)
    shutil.rmtree(site / 'rapidocr/models', ignore_errors=True)
    for path in site.rglob('__pycache__'):
        shutil.rmtree(path, ignore_errors=True)


def windows():
    folder = DIST / '三级助手-Windows-x64'
    runtime, application = folder / 'runtime', folder / 'app'
    runtime.mkdir(parents=True, exist_ok=True)
    wheels = CACHE / 'wheels-win'
    wheels.mkdir(parents=True, exist_ok=True)
    requirements = CACHE / 'windows-requirements.txt'
    lines = [line for line in (ROOT / 'requirements.txt').read_text().splitlines()
             if line.strip() and not line.startswith('#') and 'pyobjc' not in line]
    lines += ['colorama==0.4.6', 'pyreadline3==3.5.4']
    from importlib.metadata import version
    for name in ('certifi', 'charset-normalizer', 'idna', 'urllib3', 'coloredlogs', 'flatbuffers',
                 'humanfriendly', 'packaging', 'protobuf', 'mpmath', 'sympy'):
        lines.append(name + '==' + version(name))
    requirements.write_text('\n'.join(lines) + '\n')
    run([sys.executable, '-m', 'pip', 'download', '-r', requirements, '--dest', wheels,
         '--platform', 'win_amd64', '--python-version', '310', '--implementation', 'cp', '--abi', 'cp310', '--only-binary=:all:', '--no-deps'])
    package = CACHE / 'python-3.10.11-embed-amd64.zip'
    download('https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip', package)
    with zipfile.ZipFile(package) as source:
        source.extractall(runtime)
    site = runtime / 'Lib/site-packages'
    site.mkdir(parents=True, exist_ok=True)
    for wheel in wheels.glob('*.whl'):
        with zipfile.ZipFile(wheel) as source:
            source.extractall(site)
        for data in site.glob('*.data'):
            for section in ('purelib', 'platlib'):
                if (data / section).exists():
                    shutil.copytree(data / section, site, dirs_exist_ok=True)
            shutil.rmtree(data)
    # antlr4 是 omegaconf 的纯 Python 依赖，官方没有 wheel。
    import antlr4
    shutil.copytree(Path(antlr4.__file__).parent, site / 'antlr4', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for metadata in Path(antlr4.__file__).parent.parent.glob('antlr4_python3_runtime-*.dist-info'):
        shutil.copytree(metadata, site / metadata.name, dirs_exist_ok=True)
    (runtime / 'python310._pth').write_text('python310.zip\n.\nLib/site-packages\n../app\nimport site\n', encoding='utf-8')
    trim_qt(site)
    # Qt 官方轮子携带 VC++ 运行库，复制到解释器目录供 OCR 独立加载。
    for pattern in ('msvcp*.dll', 'vcruntime*.dll', 'concrt*.dll'):
        for dependency in (site / 'shiboken6').glob(pattern):
            shutil.copyfile(dependency, runtime / dependency.name)
    copy_resources(application)
    import ziglang
    zig = Path(ziglang.__file__).parent / ('zig.exe' if os.name == 'nt' else 'zig')
    for name, action in (('三级助手.exe', ''), ('设置.exe', '--configure'), ('退出.exe', '--quit'), ('本机检查.exe', '--self-check')):
        run([zig, 'cc', '-target', 'x86_64-windows-gnu', '-O2', '-municode', '-Wl,--subsystem,windows',
             '-DACTION=L"' + action + '"', ROOT / 'tools/launcher_windows.c', '-o', folder / name, '-luser32'])
    (folder / '使用说明.txt').write_text(
        '先完整解压。双击“三级助手.exe”，短暂显示“应用启动”。\n'
        '在题目位置右键；单选、多选显示当前字母，判断显示正确或错误。识别不完整显示“无”。\n'
        '日常不显示主窗口、托盘或任务栏窗口。双击“设置.exe”调整外观与截图范围；“退出.exe”结束运行。\n'
        '运行环境和模型均已内置，不需要安装 Python，不需要联网，不需要管理员权限。\n'
        '目标系统：64位 Windows 10 1809 及以上、Windows 11。Windows 实机检查结果见项目验证报告。\n'
        '截图失败时可在设置中切换到“截取鼠标所在屏幕”。受保护窗口、锁屏和企业策略限制不能绕过。\n', encoding='utf-8-sig')
    with (folder / '使用说明.txt').open('a', encoding='utf-8-sig') as instructions:
        instructions.write('0.3.1：设置内可调整答案显示时长，范围0.2–5.0秒，默认2.5秒。\n两平台使用同一 OCR 和匹配代码。双击“本机检查.exe”运行共同的10个图像回归。\n')
    shutil.copyfile(ROOT / 'THIRD_PARTY_NOTICES.txt', folder / 'THIRD_PARTY_NOTICES.txt')
    if (ROOT / '验证报告.md').exists():
        shutil.copyfile(ROOT / '验证报告.md', folder / '验证报告.md')
    archive(folder)


def helper_app(folder, name, action):
    app = folder / (name + '.app') / 'Contents'
    (app / 'MacOS').mkdir(parents=True, exist_ok=True)
    script = app / 'MacOS' / 'launch'
    script.write_text('#!/bin/sh\nbase=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)\nexec /usr/bin/open -n "$base/三级助手.app" --args ' + action + '\n')
    script.chmod(0o755)
    import plistlib
    (app / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'net.local.trainerlevel3.' + ('settings' if action == '--configure' else 'quit'),
        'CFBundleName': name, 'CFBundleExecutable': 'launch', 'CFBundlePackageType': 'APPL', 'LSUIElement': True,
        'LSMinimumSystemVersion': '11.0'}))
    run(['codesign', '--force', '--sign', '-', folder / (name + '.app')])


def mac():
    if sys.platform != 'darwin':
        raise RuntimeError('Mac 运行包须在 M 系列 Mac 上构建')
    import platform
    if platform.machine() != 'arm64':
        raise RuntimeError('仅构建 M 系列 Mac，不支持 Intel Mac')
    folder = DIST / '三级助手-M系列Mac'
    folder.mkdir(parents=True, exist_ok=True)
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', CACHE / 'mac-dist',
         '--workpath', CACHE / 'mac-work', ROOT / 'tools/build_mac.spec'])
    target = folder / '三级助手.app'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(CACHE / 'mac-dist/三级助手.app', target, symlinks=True)
    # 固定指定要求，更新不再把二进制 CDHash 作为授权身份。
    identity = json.loads((ROOT / 'macos_identity.json').read_text(encoding='utf-8'))
    identifier = identity['identifier']
    expected_requirement = identity['designated_requirement']
    run(['codesign', '--force', '--sign', '-', '--identifier', identifier,
         '--requirements', '=designated => ' + expected_requirement, target])
    requirement = subprocess.check_output(['codesign', '-dr', '-', target], stderr=subprocess.STDOUT).decode()
    if 'designated => ' + expected_requirement not in requirement or 'cdhash H' in requirement:
        raise RuntimeError('Mac 固定签名要求校验失败')
    for name, action in (('设置', '--configure'), ('退出', '--quit')):
        helper_app(folder, name, action)
    (folder / '使用说明.txt').write_text(
        '仅支持 M 系列 Mac。完整解压后双击“三级助手.app”。\n'
        '首次运行按提示允许屏幕录制、输入监听，退出并重新打开应用。每台 Mac 均须各自授权。\n'
        '运行环境、OCR 模型和题库均已内置，不用安装 Python，也不需要联网。\n'
        '日常无菜单栏图标、Dock 图标或主窗口。启动时短暂显示“应用启动”。\n'
        '在题目位置右键，鼠标旁显示当前答案；显示时长默认2.5秒，可调0.2–5.0秒。\n'
        '双击“设置.app”调整外观、显示时长与截图范围；“退出.app”结束运行。\n'
        '运行包当前为本地签名。转发下载时，macOS 可能要求在隐私与安全性中允许打开。\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'THIRD_PARTY_NOTICES.txt', folder / 'THIRD_PARTY_NOTICES.txt')
    if (ROOT / '验证报告.md').exists():
        shutil.copyfile(ROOT / '验证报告.md', folder / '验证报告.md')
    run(['codesign', '--verify', '--deep', '--strict', target])
    # ditto 保留 .app 符号链接与可执行权限。
    run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', folder, DIST / (folder.name + '.zip')])
    print(json.dumps({'archive': folder.name + '.zip', 'mib': round((DIST / (folder.name + '.zip')).stat().st_size / 1024**2, 1)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('platform', choices=['mac', 'windows'])
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    globals()[args.platform]()
