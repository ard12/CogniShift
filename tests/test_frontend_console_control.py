from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
APP_TSX = FRONTEND_DIR / "src" / "App.tsx"
SIDEBAR_TSX = FRONTEND_DIR / "src" / "components" / "Sidebar.tsx"
OPERATOR_TSX = FRONTEND_DIR / "src" / "pages" / "OperatorPage.tsx"
ARTIFACTS_API_TS = FRONTEND_DIR / "src" / "api" / "artifacts.ts"
MAIL_API_TS = FRONTEND_DIR / "src" / "api" / "mail.ts"
MAIL_PAGE_TSX = FRONTEND_DIR / "src" / "pages" / "MailPage.tsx"
MAIL_FEATURES_DIR = FRONTEND_DIR / "src" / "features" / "mail"


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
    assert "BACKEND-VERIFIED" in operator_code
    assert "BACKEND-VERIFIED DELIVERABLES" in operator_code
    assert "ISOLATED SANDBOX ARTIFACTS" not in operator_code


def test_mail_attachment_downloads_carry_auth_and_device_proof():
    mail_api_code = MAIL_API_TS.read_text(encoding="utf-8")
    mail_feature_code = "\n".join(
        p.read_text(encoding="utf-8") for p in MAIL_FEATURES_DIR.glob("*.tsx")
    )

    assert "downloadAttachment(" in mail_api_code
    assert "getStoredToken" in mail_api_code
    assert "getDeviceSession" in mail_api_code
    assert '"X-Device-Session"' in mail_api_code
    assert "await mailApi.downloadAttachment" in mail_feature_code
    assert "href={mailApi.downloadAttachmentUrl" not in mail_feature_code
    assert '{currentUserId || "not-verified"}@secure.internal' in mail_feature_code


def test_mail_ai_status_and_transport_claims_are_backend_truthful():
    mail_feature_code = "\n".join(
        p.read_text(encoding="utf-8") for p in MAIL_FEATURES_DIR.glob("*.tsx")
    )

    assert "Draft generated via local ${draft.model}" in mail_feature_code
    assert "deterministic fallback used" in mail_feature_code
    assert "Local SLM Operational Draft Assistant (qwen2.5:7b)" not in mail_feature_code
    assert 'smtpHealth.loopback_only ? "LOCAL ONLY" : "NOT VERIFIED"' in mail_feature_code
    assert "100% OFFLINE" not in mail_feature_code
    assert "ZERO CLOUD" not in mail_feature_code


def test_operator_carries_non_image_upload_into_the_run_source_context():
    operator_code = OPERATOR_TSX.read_text(encoding="utf-8")

    assert "attachedSourceName" in operator_code
    assert "source.original_filename ?? source.name ?? imageFile.name" in operator_code
    assert "Attached source file: ${attachedSourceName}" in operator_code
