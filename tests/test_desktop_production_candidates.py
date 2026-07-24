from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_dotnet_candidates_use_native_bridge_api():
    avalonia = read("desktop/previews/avalonia/Program.cs")
    wpf = read("desktop/previews/wpf/MainWindow.xaml.cs")
    for source in (avalonia, wpf):
        assert "0.3.0" in source
        assert "BRIDGE_URL" in source
        assert "http://127.0.0.1:19191" in source
        assert "/api/status" in source
        assert "/api/proxies" in source
        assert "/api/connections" in source
        assert "/api/config/save" in source
        assert "/api/subscription/add" in source
        assert "/api/import/static" in source
        assert "/api/dns/resolve" in source
        assert "unified-ui-native-bridge" in source


def test_cpp_candidate_uses_native_bridge_api_and_gui_subsystem_build():
    cpp = read("desktop/previews/cpp-native/windows/main.cpp")
    ref = read("desktop/previews/cpp-native/windows/build-win32-preview.bat") if (ROOT / "desktop/previews/cpp-native/windows/build-win32-preview.bat").exists() else ""
    assert "0.3.0" in cpp
    assert "BRIDGE_URL" in cpp
    assert "127.0.0.1:19191" in cpp
    for endpoint in ["/api/status", "/api/proxies", "/api/connections", "/api/config", "/api/subscription/add", "/api/import/static", "/api/dns/resolve"]:
        assert endpoint in cpp
    assert "unified-ui-native-bridge.exe" in cpp
    assert "/SUBSYSTEM:WINDOWS" in ref
    assert "/ENTRY:wWinMainCRTStartup" in ref


def test_bridge_source_declares_production_feature_contract():
    bridge = read("desktop/previews/shared/native_bridge.py")
    assert 'BRIDGE_VERSION = "0.3.0"' in bridge
    for feature in [
        "runtime-start-stop-restart",
        "select-proxy",
        "close-connection",
        "config-read-save-validate",
        "subscription-add-update-delete",
        "static-proxy-import-update-delete",
        "dns-routes-manual-resolver",
    ]:
        assert feature in bridge
