from cognishift.app.config import settings


def test_frontend_has_no_hardcoded_api_tokens_and_keeps_strict_csp():
    static_dir = settings.static_dir
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    main_py = (static_dir.parent / "main.py").read_text(encoding="utf-8")
    for prefix in ("cog_op_", "cog_sup_", "cog_adm_", "test-key-"):
        assert prefix not in app_js
    assert "download?token=" not in app_js
    assert "script-src 'self'" in main_py
    assert "localStorage" not in app_js.replace("never localStorage", "")


def test_sovereignty_ledger_uses_current_network_event_schema():
    static_dir = settings.static_dir
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    index_html = (static_dir / "index.html").read_text(encoding="utf-8")

    assert "ev.requested_host" in app_js
    assert "ev.destination_host" not in app_js
    assert "ev.destination_port" not in app_js
    assert "Network Policy Decision Ledger" in index_html


def test_console_command_input_has_explicit_visible_foreground():
    app_css = (settings.static_dir / "app.css").read_text(encoding="utf-8")

    assert "#consoleCmdInput" in app_css
    assert "-webkit-text-fill-color: var(--text-primary)" in app_css
    assert "caret-color: var(--color-green)" in app_css
