from pathlib import Path
from cognishift.app.config import settings


def test_frontend_has_no_hardcoded_api_tokens_and_keeps_strict_csp():
    frontend_src = settings.PROJECT_ROOT / "frontend" / "src"
    main_py = (settings.PROJECT_ROOT / "src" / "cognishift" / "app" / "main.py").read_text(encoding="utf-8")

    # Verify no hardcoded API tokens in frontend TypeScript sources
    for ts_file in frontend_src.rglob("*.ts*"):
        text = ts_file.read_text(encoding="utf-8")
        for prefix in ("cog_op_", "cog_sup_", "cog_adm_", "test-key-"):
            assert prefix not in text, f"Found hardcoded token prefix {prefix} in {ts_file}"
        assert "download?token=" not in text

    assert "script-src 'self'" in main_py


def test_sovereignty_ledger_uses_current_network_event_schema():
    types_ts = (settings.PROJECT_ROOT / "frontend" / "src" / "types" / "index.ts").read_text(encoding="utf-8")
    system_page = (settings.PROJECT_ROOT / "frontend" / "src" / "pages" / "SystemPage.tsx").read_text(encoding="utf-8")

    assert "requested_host: string" in types_ts
    assert "destination_host" not in types_ts
    assert "destination_port" not in types_ts
    assert "Network" in system_page or "Sovereignty" in system_page


def test_console_theme_has_brand_accent():
    index_css = (settings.PROJECT_ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    assert "--color-brand:" in index_css
    assert "#06b6d4" in index_css
