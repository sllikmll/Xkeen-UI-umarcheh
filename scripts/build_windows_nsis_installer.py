#!/usr/bin/env python3
"""Build a Unicode NSIS installer for Unified UI Native on Windows.

The important bit: the generated .nsi is written as UTF-8 with BOM and contains
`Unicode true`. Without that, custom Russian strings render as mojibake in NSIS
welcome/finish pages on Windows.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "Unified UI Native"
PUBLISHER = "sllikmll"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2.6.6", help="Release version used in filenames and registry metadata")
    parser.add_argument("--app-exe", default=None, type=Path, help="Path to the main Unified UI Native .exe. Defaults to <app-dir>/Unified UI Native.exe")
    parser.add_argument("--app-dir", default=None, type=Path, help="Path to the PyInstaller onedir bundle directory to install")
    parser.add_argument("--out", default=None, type=Path, help="Output setup .exe path")
    parser.add_argument("--workdir", default=Path("build/native-windows-installer"), type=Path)
    parser.add_argument("--makensis", default=None, type=Path, help="Path to makensis.exe; defaults to PATH lookup")
    parser.add_argument("--skip-build", action="store_true", help="Only write the .nsi script; do not invoke makensis")
    return parser.parse_args()


def nsis_quote(value: str | Path) -> str:
    return str(value).replace('\\', '\\\\').replace('"', '$\\"')


def installer_script(*, version: str, app_dir: Path, app_exe: Path, out_exe: Path) -> str:
    # Keep custom Russian text here intentionally; tests assert this stays Unicode-safe.
    return f'''Unicode true
SetCompressor /SOLID lzma
RequestExecutionLevel user

!include "MUI2.nsh"

!define APP_NAME "{APP_NAME}"
!define APP_EXE "Unified UI Native.exe"
!define COMPANY_NAME "{PUBLISHER}"
!define VERSION "{version}"
!define MUI_ABORTWARNING

Name "${{APP_NAME}}"
OutFile "{nsis_quote(out_exe)}"
InstallDir "$LOCALAPPDATA\\Programs\\Unified UI Native"
InstallDirRegKey HKCU "Software\\${{COMPANY_NAME}}\\${{APP_NAME}}" "InstallDir"

!define MUI_WELCOMEPAGE_TITLE "Установка Unified UI Native"
!define MUI_WELCOMEPAGE_TEXT "Мастер установит Unified UI Native на этот компьютер. Перед продолжением закройте запущенное приложение."
!define MUI_FINISHPAGE_TITLE "Unified UI Native установлен"
!define MUI_FINISHPAGE_TEXT "Установка завершена. Приложение готово к запуску."
!define MUI_FINISHPAGE_RUN "$INSTDIR\\${{APP_EXE}}"
!define MUI_FINISHPAGE_RUN_TEXT "Запустить Unified UI Native"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "{nsis_quote(app_dir)}\\*.*"
  WriteRegStr HKCU "Software\\${{COMPANY_NAME}}\\${{APP_NAME}}" "InstallDir" "$INSTDIR"
  WriteUninstaller "$INSTDIR\\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\\Unified UI Native"
  CreateShortcut "$SMPROGRAMS\\Unified UI Native\\Unified UI Native.lnk" "$INSTDIR\\${{APP_EXE}}"
  CreateShortcut "$SMPROGRAMS\\Unified UI Native\\Удалить Unified UI Native.lnk" "$INSTDIR\\Uninstall.exe"
  CreateShortcut "$DESKTOP\\Unified UI Native.lnk" "$INSTDIR\\${{APP_EXE}}"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\\Unified UI Native.lnk"
  Delete "$SMPROGRAMS\\Unified UI Native\\Unified UI Native.lnk"
  Delete "$SMPROGRAMS\\Unified UI Native\\Удалить Unified UI Native.lnk"
  RMDir "$SMPROGRAMS\\Unified UI Native"
  RMDir /r "$INSTDIR\\_internal"
  Delete "$INSTDIR\\${{APP_EXE}}"
  Delete "$INSTDIR\\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\\${{COMPANY_NAME}}\\${{APP_NAME}}"
SectionEnd
'''


def find_makensis(explicit: Path | None) -> str:
    if explicit:
        return str(explicit)
    found = shutil.which("makensis") or shutil.which("makensis.exe")
    if found:
        return found
    common = [
        Path(r"C:\Program Files (x86)\NSIS\makensis.exe"),
        Path(r"C:\Program Files\NSIS\makensis.exe"),
        Path(r"C:\Program Files (x86)\NSIS\Bin\makensis.exe"),
    ]
    for path in common:
        if path.exists():
            return str(path)
    raise FileNotFoundError("makensis.exe not found. Install NSIS or pass --makensis")


def nsis_dir_for(makensis: str | Path) -> str:
    exe = Path(makensis).resolve()
    # Standard install: C:\Program Files (x86)\NSIS\makensis.exe.
    if (exe.parent / "Stubs").is_dir():
        return str(exe.parent)
    # Alternate PATH entry: C:\Program Files (x86)\NSIS\Bin\makensis.exe.
    if exe.parent.name.lower() == "bin" and (exe.parent.parent / "Stubs").is_dir():
        return str(exe.parent.parent)
    return str(exe.parent)


def main() -> int:
    args = parse_args()
    if args.app_dir is not None:
        app_dir = args.app_dir.resolve()
    elif args.app_exe is not None:
        app_dir = args.app_exe.resolve().parent
    else:
        app_dir = (Path("dist") / APP_NAME).resolve()
    if not app_dir.is_dir():
        print(f"app dir not found: {app_dir}", file=sys.stderr)
        return 2
    app_exe = args.app_exe.resolve() if args.app_exe is not None else app_dir / f"{APP_NAME}.exe"
    if not app_exe.is_file():
        print(f"app exe not found: {app_exe}", file=sys.stderr)
        return 2
    if app_exe.parent != app_dir:
        print(f"app exe must be inside app dir: {app_exe} not in {app_dir}", file=sys.stderr)
        return 2
    out = args.out or Path(f"dist-artifacts/Unified-UI-Native-Setup-{args.version}-x64.exe")
    out = out.resolve()
    args.workdir.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    nsi = args.workdir / "Unified-UI-Native-Setup.nsi"
    script = installer_script(version=args.version, app_dir=app_dir, app_exe=app_exe, out_exe=out)
    nsi.write_text(script, encoding="utf-8-sig")
    raw = nsi.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError("NSIS script must be UTF-8 with BOM")
    if "Unicode true" not in script:
        raise RuntimeError("NSIS script must enable Unicode true")
    if any(bad in script for bad in ("РЈ", "Рџ", "Рњ", "Рќ")):
        raise RuntimeError("Generated NSIS script contains likely mojibake")
    print(f"wrote {nsi}")
    if args.skip_build:
        return 0
    makensis = find_makensis(args.makensis)
    env = os.environ.copy()
    env.setdefault("NSISDIR", nsis_dir_for(makensis))
    result = subprocess.run([makensis, str(nsi)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    print(result.stdout)
    if result.returncode != 0:
        return result.returncode
    if not out.is_file():
        print(f"installer not produced: {out}", file=sys.stderr)
        return 3
    print(f"built {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
