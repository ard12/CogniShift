from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
APP_TSX = FRONTEND_DIR / "src" / "App.tsx"
SIDEBAR_TSX = FRONTEND_DIR / "src" / "components" / "Sidebar.tsx"
OPERATOR_TSX = FRONTEND_DIR / "src" / "pages" / "OperatorPage.tsx"


def test_console_routes_every_primary_view_and_preserves_agent_fallback():
    app_code = APP_TSX.read_text(encoding="utf-8")
    sidebar_code = SIDEBAR_TSX.read_text(encoding="utf-8")

    for view in (
        "dashboard",
        "operator",
        "workspaces",
        "agents",
        "knowledge",
        "runs",
        "approvals",
        "artifacts",
        "system",
    ):
        assert f'path="{view}"' in app_code or f'to="/{view}"' in sidebar_code

    operator_code = OPERATOR_TSX.read_text(encoding="utf-8")
    assert "runsApi.create" in operator_code
    assert "dispatchStage" in operator_code


def test_console_supports_conversational_and_session_commands():
    operator_code = OPERATOR_TSX.read_text(encoding="utf-8")
    app_code = APP_TSX.read_text(encoding="utf-8")

    # Verify quick operator scenarios and conversational triggers
    for scenario in (
        "check-pt101-telemetry",
        "trip-495psi-emergency",
        "verify-tt204-temp",
    ):
        assert scenario in operator_code

    # Verify authentication and session gates
    assert "AuthGatePage" in app_code
    assert "AuthProvider" in app_code


def test_conversational_command_bar_remains_available_outside_dashboard():
    # Verify primary navigation remains globally accessible in AppShell/Sidebar
    sidebar_code = SIDEBAR_TSX.read_text(encoding="utf-8")
    assert 'aria-label="Primary"' in sidebar_code
    assert 'to: "/operator"' in sidebar_code
    assert 'to: "/dashboard"' in sidebar_code

