import { Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { AuthProvider } from "@/auth/AuthContext";
import { useAuth } from "@/auth/useAuth";
import { AppShell } from "@/components/AppShell";
import { AuthGatePage } from "@/components/AuthGatePage";
import { WorkspaceProvider } from "@/context/WorkspaceContext";
import { LandingPage } from "@/pages/LandingPage";
import { AgentsPage } from "@/pages/AgentsPage";
import { ApprovalsPage } from "@/pages/ApprovalsPage";
import { ArtifactsPage } from "@/pages/ArtifactsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { KnowledgePage } from "@/pages/KnowledgePage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OperatorPage } from "@/pages/OperatorPage";
import { RunsPage } from "@/pages/RunsPage";
import { SystemPage } from "@/pages/SystemPage";
import { WorkspacesPage } from "@/pages/WorkspacesPage";
import { SecurityPage } from "@/pages/SecurityPage";
import { MailPage } from "@/pages/MailPage";
import type { UserRole } from "@/types";

function RoleRoute({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
  const { role } = useAuth();
  return role && roles.includes(role) ? children : <Navigate to="/app/operator" replace />;
}

function WorkbenchApp() {
  const { token, ready } = useAuth();

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-transparent text-sm text-ink-3">
        Connecting to CogniShift…
      </div>
    );
  }

  if (!token) {
    return <AuthGatePage />;
  }

  return (
    <WorkspaceProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="operator" replace />} />
          <Route path="operator" element={<OperatorPage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route
            path="workspaces"
            element={
              <RoleRoute roles={["supervisor", "administrator"]}>
                <WorkspacesPage />
              </RoleRoute>
            }
          />
          <Route
            path="agents"
            element={
              <RoleRoute roles={["administrator"]}>
                <AgentsPage />
              </RoleRoute>
            }
          />
          <Route
            path="knowledge"
            element={
              <RoleRoute roles={["supervisor", "administrator"]}>
                <KnowledgePage />
              </RoleRoute>
            }
          />
          <Route
            path="approvals"
            element={
              <RoleRoute roles={["supervisor", "administrator"]}>
                <ApprovalsPage />
              </RoleRoute>
            }
          />
          <Route path="mailbox" element={<MailPage />} />
          <Route path="artifacts" element={<ArtifactsPage />} />
          <Route path="security" element={<SecurityPage />} />
          <Route
            path="system"
            element={
              <RoleRoute roles={["administrator"]}>
                <SystemPage />
              </RoleRoute>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </WorkspaceProvider>
  );
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Cinematic Landing Page */}
        <Route path="/" element={<LandingPage />} />

        {/* Sovereign Industrial AI Workbench */}
        <Route path="/app/*" element={<WorkbenchApp />} />

        {/* Legacy Route Redirects for Direct Links & Bookmarks */}
        <Route path="/operator" element={<Navigate to="/app/operator" replace />} />
        <Route path="/dashboard" element={<Navigate to="/app/dashboard" replace />} />
        <Route path="/runs" element={<Navigate to="/app/runs" replace />} />
        <Route path="/knowledge" element={<Navigate to="/app/knowledge" replace />} />
        <Route path="/agents" element={<Navigate to="/app/agents" replace />} />
        <Route path="/workspaces" element={<Navigate to="/app/workspaces" replace />} />
        <Route path="/approvals" element={<Navigate to="/app/approvals" replace />} />
        <Route path="/mailbox" element={<Navigate to="/app/mailbox" replace />} />
        <Route path="/artifacts" element={<Navigate to="/app/artifacts" replace />} />
        <Route path="/security" element={<Navigate to="/app/security" replace />} />
        <Route path="/system" element={<Navigate to="/app/system" replace />} />

        {/* Catch-all 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
