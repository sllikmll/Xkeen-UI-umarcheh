from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'build_native_release_manifest.py'
PORTAL = ROOT / 'docs' / 'native-download-portal.html'
PACKAGE_JSON = ROOT / 'package.json'


def touch(path: Path, data: bytes = b'x') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_native_release_manifest_distinguishes_windows_setup_and_standalone(tmp_path: Path):
    files = [
        'Unified-UI-Native-2.6.6-mac-arm64.zip',
        'Unified-UI-Native-Setup-2.6.6-x64.exe',
        'Unified-UI-Native-2.6.6-x64.exe',
        'Unified-UI-Native-2.6.6-windows-x64-portable.zip',
        'Unified-UI-Native-2.6.6-linux-x64-portable.tar.gz',
        'Unified-UI-Native-2.6.6-linux-x64.deb',
        'Unified-UI-Native-2.6.6-linux-x64.rpm',
    ]
    for name in files:
        touch(tmp_path / name, name.encode('utf-8'))

    out = tmp_path / 'manifest.json'
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--dist', str(tmp_path), '--output', str(out), '--release-base-url', 'https://example.invalid/release'],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads(out.read_text(encoding='utf-8'))
    by_key = {item['key']: item for item in manifest['artifacts']}
    assert by_key['win_setup_x64']['file'] == 'Unified-UI-Native-Setup-2.6.6-x64.exe'
    assert by_key['win_standalone_x64']['file'] == 'Unified-UI-Native-2.6.6-x64.exe'
    assert by_key['win_setup_x64']['sha256'] != by_key['win_standalone_x64']['sha256']


def test_native_release_manifest_fails_when_required_artifacts_are_missing(tmp_path: Path):
    touch(tmp_path / 'Unified-UI-Native-2.6.6-mac-arm64.zip')
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--dist', str(tmp_path), '--output', str(tmp_path / 'manifest.json')],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert 'missing required artifact' in result.stdout


def test_native_download_portal_and_npm_scripts_are_wired():
    html = PORTAL.read_text(encoding='utf-8')
    assert 'Unified UI Native' in html
    assert 'native-release-manifest.json' in html
    assert 'Unified-UI-Native-Setup-2.6.6-x64.exe' in html
    assert 'Unified-UI-Native-2.6.6-linux-x64.deb' in html
    assert 'SHA256' in html

    package = json.loads(PACKAGE_JSON.read_text(encoding='utf-8'))
    scripts = package['scripts']
    assert scripts['native:manifest'] == 'python3 scripts/build_native_release_manifest.py --allow-missing'
    assert scripts['native:manifest:strict'] == 'python3 scripts/build_native_release_manifest.py --write-sha256sums'
    assert scripts['native:portal:open'] == 'python3 -m http.server 8765 -d docs'
