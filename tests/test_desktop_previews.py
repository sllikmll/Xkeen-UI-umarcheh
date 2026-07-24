from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

def test_preview_sources_exist_and_expose_smoke_modes():
    assert '--smoke' in read('desktop/previews/avalonia/Program.cs')
    assert '--smoke' in read('desktop/previews/wpf/MainWindow.xaml.cs')
    assert '--smoke' in read('desktop/previews/cpp-native/windows/main.cpp')

def test_preview_ui_variants_are_separate():
    assert 'Avalonia' in read('desktop/previews/avalonia/UnifiedUiAvaloniaPreview.csproj')
    assert '<UseWPF>true</UseWPF>' in read('desktop/previews/wpf/UnifiedUiWpfPreview.csproj')
    assert '#include <windows.h>' in read('desktop/previews/cpp-native/windows/main.cpp')

def test_preview_manifest_lists_all_three_artifacts():
    text = read('scripts/build_desktop_previews_manifest.py')
    assert 'Unified-UI-Avalonia-Preview-0.3.0-win-x64.zip' in text
    assert 'Unified-UI-WPF-Preview-0.3.0-win-x64.zip' in text
    assert 'Unified-UI-Cpp-Win32-Preview-0.3.0-win-x64.zip' in text
