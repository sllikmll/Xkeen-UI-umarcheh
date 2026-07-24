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

    assert "Обновление v2.6.6-native" not in text
    assert "Проверить обновления" not in text
    assert "Светлая тема" not in text
    assert "Выйти" not in text
    assert "lambda: self.activate_page(\"Интерфейс\")" in text
    assert "lambda: self.activate_page(\"Настройки\")" in text
    assert "version = QLabel(\"v2.6." not in text
    assert "APP_RELEASE_LABEL" in text
    assert "self.setWindowTitle(f\"{APP_NAME} {APP_RELEASE_LABEL}\")" in text


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
    assert "q = self.ping_all_queue" in text
    assert "event = q.get_nowait()" in text
    assert "event = self.ping_all_queue.get_nowait()" not in text


def test_manual_proxy_editor_is_narrower_than_routing_content():
    text = source_text()

    assert "root.addWidget(left, 79)" in text
    assert "root.addWidget(self.editor_panel, 21)" in text
    assert "self.setMaximumWidth(420)" in text


def test_native_logs_page_is_labelled_logs_not_files():
    text = source_text()

    assert 'self.add_page("Логи", self.logs)' in text
    assert 'self.add_page("Файлы", self.logs)' not in text
    assert '("Смотреть логи", "Логи")' in text
    assert '"Файлы"' not in text


def test_native_subscription_mirrors_have_lifecycle_metadata_and_cleanup():
    text = source_text()

    assert "x-unified-ui-origin" in text
    assert "subscription-mirror" in text
    assert "_remove_subscription_mirrors" in text
    assert "_subscription_mirror_proxy_names" in text
    assert "_remove_static_proxies_by_names" in text
    assert "removed_static" in text


def test_native_dns_routes_has_router_style_mode_switch_and_generator():
    text = source_text()

    assert "Mihomo selectors" in text
    assert "Маршруты DNS / интерфейсы роутера" in text
    assert "Списки NDMS" in text
    assert "domain-list" in text
    assert "SERVICE_PRESETS" in text
    assert "generate_service" in text
    assert "dns_routes_path" in text
    assert "QRadioButton" in text
