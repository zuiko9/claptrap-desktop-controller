"""Build a portable app archive for this operating system and processor."""

from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile


ROOT = Path(__file__).resolve().parents[1]
NAME = 'ClaptrapDesktopController'
ARCHITECTURE = {'x86_64': 'x64', 'AMD64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(
    platform.machine(), platform.machine().lower())
PLATFORM = {'Darwin': 'macos', 'Windows': 'windows', 'Linux': 'linux'}.get(platform.system())


def build():
    if PLATFORM is None:
        raise SystemExit(f'Unsupported build host: {platform.system()}')
    command = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--windowed', '--onedir', '--name', NAME,
        '--paths', str(ROOT / 'src'),
        '--add-data', f"{ROOT / 'assets' / 'app-icon.png'}:assets",
        '--distpath', str(ROOT / 'dist'),
        '--workpath', str(ROOT / 'build' / 'pyinstaller'),
        '--specpath', str(ROOT / 'build'),
    ]
    if PLATFORM in ('macos', 'windows'):
        command.extend(['--icon', str(ROOT / 'assets' / 'app-icon.png')])
    command.append(str(ROOT / 'tools' / 'launcher.py'))
    subprocess.run(command, cwd=ROOT, check=True)

    package_dir = ROOT / 'dist' / 'packages'
    package_dir.mkdir(parents=True, exist_ok=True)
    stage = package_dir / NAME
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    if PLATFORM == 'macos':
        shutil.copytree(ROOT / 'dist' / f'{NAME}.app', stage / f'{NAME}.app', symlinks=True)
    else:
        shutil.copytree(ROOT / 'dist' / NAME, stage / NAME, symlinks=True)
    shutil.copy2(ROOT / 'LICENSE', stage / 'LICENSE')
    shutil.copy2(ROOT / 'README.md', stage / 'README.md')
    shutil.copy2(ROOT / 'assets' / 'app-icon.png', stage / 'app-icon.png')
    shutil.copy2(ROOT / 'assets' / 'TABLER-LICENSE', stage / 'TABLER-LICENSE')

    archive_base = package_dir / f'{NAME}-{PLATFORM}-{ARCHITECTURE}'
    if PLATFORM == 'macos':
        archive = archive_base.with_suffix('.zip')
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                        str(stage), str(archive)], check=True)
    elif PLATFORM == 'windows':
        archive = Path(shutil.make_archive(str(archive_base), 'zip',
                                           root_dir=package_dir, base_dir=NAME))
    else:
        archive = archive_base.with_suffix('.tar.gz')
        with tarfile.open(archive, 'w:gz') as output:
            output.add(stage, arcname=NAME)
    print(f'Built {archive}')
    return archive


if __name__ == '__main__':
    build()
