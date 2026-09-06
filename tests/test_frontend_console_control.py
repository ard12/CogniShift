from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "src" / "cognishift" / "app" / "static" / "app.js"


def test_console_routes_every_primary_view_and_preserves_agent_fallback():
    script = APP_JS.read_text(encoding="utf-8")

    for view in (
        "dashboard",
        "workspaces",
        "documents",
        "agents",
        "approvals",
        "artifacts",
        "audit",
        "sandbox",
        "sovereignty",
    ):
        assert f"view: '{view}'" in script

    assert "handleConsoleControlCommand(cmd)" in script
    assert "Any other non-empty request is sent to the local agent" in script
    assert "api.fetch('/api/v1/runs'" in script


def test_console_supports_conversational_and_session_commands():
    script = APP_JS.read_text(encoding="utf-8")

    for phrase in (
        "what can you do",
        "who am i",
        "system status",
        "switch identity",
        "terminate session",
        "show policy",
    ):
        assert phrase in script


def test_conversational_command_bar_remains_available_outside_dashboard():
    html = (APP_JS.parent / "index.html").read_text(encoding="utf-8")
    script = APP_JS.read_text(encoding="utf-8")

    assert 'id="globalCommandDock"' in html
    assert 'id="globalConsoleCmdInput"' in html
    assert 'data-input="globalConsoleCmdInput"' in html
    assert "globalCommandDock.classList.toggle('hidden', viewName === 'dashboard')" in script
    assert "['consoleCmdInput', 'globalConsoleCmdInput']" in script
