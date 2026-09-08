from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
APP_TSX = FRONTEND_DIR / "src" / "App.tsx"
SIDEBAR_TSX = FRONTEND_DIR / "src" / "components" / "Sidebar.tsx"
OPERATOR_TSX = FRONTEND_DIR / "src" / "pages" / "OperatorPage.tsx"
ARTIFACTS_API_TS = FRONTEND_DIR / "src" / "api" / "artifacts.ts"


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


def test_artifact_downloads_carry_device_proof_and_labels_do_not_invent_sandboxing():
    artifact_code = ARTIFACTS_API_TS.read_text(encoding="utf-8")
    operator_code = OPERATOR_TSX.read_text(encoding="utf-8")

    assert "getDeviceSession" in artifact_code
    assert '"X-Device-Session"' in artifact_code
    assert "BACKEND-VERIFIED RUN ARTIFACTS" in operator_code
    assert "ISOLATED SANDBOX ARTIFACTS" not in operator_code
