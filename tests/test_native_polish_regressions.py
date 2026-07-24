from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "desktop" / "native" / "unified_ui_native.py"


def source_text() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_native_startup_splash_has_no_debug_copy_and_uses_textless_progress_bar():
    text = source_text()

    assert "Окно приложения уже живое" not in text
    assert "чёрная магия" not in text
    assert "startup_status" not in text
    assert "QProgressBar" in text
    assert "setTextVisible(False)" in text


def test_native_header_has_no_fake_update_or_exit_buttons():
    text = source_text()

    assert "Обновление v2.6.5-native" not in text
    assert "Проверить обновления" not in text
    assert "Светлая тема" not in text
    assert "Выйти" not in text
    assert "lambda: self.activate_page(\"Интерфейс\")" in text
    assert "lambda: self.activate_page(\"Настройки\")" in text


def test_native_pages_use_explicit_index_map_not_list_position_lookup():
    text = source_text()

    assert "self.page_index_by_name" in text
    assert "Duplicate Native page name" in text
    assert "self.stack.setCurrentIndex(self.page_names.index(name))" not in text


def test_native_bulk_ping_runs_off_ui_thread_with_progress_guard():
    text = source_text()

    assert "ping_all_in_progress" in text
    assert "ThreadPoolExecutor" in text
    assert "threading.Thread(target=worker, daemon=True).start()" in text
    assert "Пинги уже обновляются" in text
    assert "self.ping_all_btn.setEnabled(False)" in text
    assert "self.ping_all_btn.setEnabled(True)" in text


def test_manual_proxy_editor_is_narrower_than_routing_content():
    text = source_text()

    assert "root.addWidget(left, 79)" in text
    assert "root.addWidget(self.editor_panel, 21)" in text
    assert "self.setMaximumWidth(420)" in text
