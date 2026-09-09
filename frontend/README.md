# CogniShift Operator Console (Vite + React 19 + TypeScript)

This directory contains the production Single Page Application (SPA) operator console for the **CogniShift Sovereign On-Premise Agentic AI Workbench** (SIH26117).

It provides industrial plant engineers, control room operators, and supervisors with a responsive, zero-CDN, air-gapped web interface for agent orchestration, real-time telemetry observation, document retrieval, human-in-the-loop approvals, and multi-format deliverable inspection.

---

## Key Capabilities & Features

1. **Zero External CDN Dependencies:** 100% self-contained typography, Tailwind styling, and SVG icon system. Operates strictly offline without external network egress.
2. **Deterministic & Agentic Operator Console (`/operator`):**
   - Direct execution prompt dispatch with quick-scenario industrial presets (`check-pt101-telemetry`, `trip-495psi-emergency`, `verify-tt204-temp`).
   - Multimodal image attachment support for analog gauge reading and equipment nameplate OCR.
   - Real-time step-by-step lifecycle tracking (`dispatching` → `settled`) with live timeline events and tool execution indicators.
   - Inline deliverable preview and download cards for generated reports (`.docx`, `.pdf`, `.xlsx`, `.png`, `.json`).
3. **Four-Eyes Supervisor Approval Workflow (`/approvals`):**
   - High-consequence operational actions automatically trigger safety gates.
   - Two-stage supervisor sign-off cards enforcing dual-independent authorization (`reviewed_by` + `reviewed_by_2`).
4. **Knowledge Base Manager (`/knowledge`):**
   - Drag-and-drop ingestion of standard operating procedures (SOPs), P&ID schematics, and technical manuals (`.pdf`, `.png`, `.jpg`).
   - Workspace-isolated ChromaDB collection indexing with real-time vector status.
5. **Multi-Tenant Workspace Context (`/workspaces`):**
   - Dynamic workspace selector with reactive context switching across telemetry, agents, documents, and generated artifacts.
6. **Air-Gap Sovereignty & Telemetry Center (`/system`):**
   - Real-time status beacon displaying loopback isolation, offline FastEmbed cache, and local Ollama GPU/CPU offload telemetry.

---

## Technology Stack

- **Runtime & Tooling:** [Vite](https://vitejs.dev/) with Fast HMR and optimized ESBuild bundling.
- **Framework:** [React 19](https://react.dev/) + [TypeScript 5.8](https://www.typescriptlang.org/) in strict type-checking mode.
- **Routing:** [React Router v7](https://reactrouter.com/) client-side declarative SPA routing.
- **Styling:** [Tailwind CSS v4](https://tailwindcss.com/) with custom industrial dark theme palette (`surface-1`, `surface-2`, `ink-1`, `ink-2`, `brand`).
- **Icons:** Zero-dependency inline SVG icon library (`components/ui/Icon.tsx`).
- **Network Layer:** Sovereign Fetch API client (`api/clients.ts`) passing Bearer token authentication and strict CSP compliance.

---

## Directory & Component Structure

```
frontend/
├── index.html                   # HTML entry point with zero external assets
├── package.json                 # Scripts and dependencies
├── vite.config.ts               # Vite configuration with @ path alias and proxy
├── tsconfig.json                # Project TypeScript configuration
└── src/
    ├── main.tsx                 # Root React entry mounting to #root
    ├── App.tsx                  # Top-level Router and AuthGate wrapper
    ├── index.css                # Tailwind CSS imports and custom design tokens
    ├── api/                     # Type-safe REST client endpoints
    │   ├── agents.ts            # Agent CRUD endpoints
    │   ├── approvals.ts         # Supervisor Four-Eyes approval actions
    │   ├── artifacts.ts         # Deliverable download and preview API
    │   ├── clients.ts           # Sovereign HTTP fetch wrapper with auth
    │   ├── knowledge.ts         # Document upload and search API
    │   ├── runs.ts              # Agent run execution and event streaming
    │   ├── system.ts            # Health, hardware telemetry, and privacy status
    │   └── workspaces.ts        # Workspace management API
    ├── auth/                    # Authentication and session state
    │   ├── AuthContext.tsx      # Context provider for bearer tokens & personas
    │   ├── auth-context.ts      # Auth context interface definitions
    │   └── useAuth.ts           # Hook for accessing user credentials
    ├── context/                 # Multi-tenant application state
    │   ├── WorkspaceContext.tsx # Global active workspace provider
    │   └── useWorkspaces.ts     # Hook for active workspace switching
    ├── components/              # Shared high-level layout and workflow widgets
    │   ├── AppShell.tsx         # Top navigation bar, sidebar, and workspace dock
    │   ├── ApprovalCard.tsx     # Four-Eyes dual approval card widget
    │   ├── AuthGatePage.tsx     # Sovereign login & demo persona selector
    │   ├── EventTimeline.tsx    # Live agent reasoning and tool step timeline
    │   ├── PageHeader.tsx       # Standardized page title and action bar
    │   ├── Sidebar.tsx          # Primary SPA navigation link rail
    │   ├── StatusBeacon.tsx     # System health and air-gap status indicator
    │   ├── WorkspacePicker.tsx  # Quick dropdown workspace switcher
    │   └── ui/                  # Atom-level reusable UI primitives
    │       ├── Badge.tsx        # Status pill indicators (risk level, run state)
    │       ├── Button.tsx       # Standard and icon buttons
    │       ├── ConfirmDialog.tsx# Modal confirmation for destructive operations
    │       ├── Icon.tsx         # Handcrafted SVGs (Gauge, Terminal, Book, etc.)
    │       ├── Panel.tsx        # Contained card container with header/footer
    │       ├── Select.tsx       # Dropdown select control
    │       └── States.tsx       # Empty and inline error state placeholders
    ├── pages/                   # Primary SPA view routes
    │   ├── DashboardPage.tsx    # Plant operational overview and quick actions
    │   ├── OperatorPage.tsx     # Interactive agent execution console & chat
    │   ├── WorkspacesPage.tsx   # Workspace creation and configuration
    │   ├── AgentsPage.tsx       # Agent definitions, system prompts, tool policies
    │   ├── KnowledgePage.tsx    # Ingested documents and vector search
    │   ├── RunsPage.tsx         # Execution history, traces, and metrics
    │   ├── ApprovalsPage.tsx    # Pending and historical supervisor sign-offs
    │   ├── ArtifactsPage.tsx    # Generated reports, diagrams, spreadsheets
    │   ├── SystemPage.tsx       # Air-gap integrity, GPU memory, model status
    │   └── NotFoundPage.tsx     # 404 fallback page
    ├── lib/                     # Utilities
    │   ├── cn.ts                # Class name merging utility
    │   ├── format.ts            # Byte formatting, date display, status tones
    │   └── token-storage.ts     # In-memory and sessionStorage token manager
    └── types/                   # Authoritative TypeScript interface definitions
        └── index.ts             # Workspace, Agent, Run, Approval, Artifact types
```

---

## Development & Build Guide

### 1. Install Dependencies
```bash
npm install
```

### 2. Start Vite Dev Server
```bash
npm run dev
```
Starts the local development server on `http://localhost:5173` with instant HMR. API requests to `/api` and `/static` are automatically proxied to the backend at `http://127.0.0.1:8000`.

### 3. Build for Production
```bash
npm run build
```
Compiles TypeScript, runs Vite asset bundling, and outputs production assets to `dist/`:
- `dist/index.html`
- `dist/assets/index-[hash].js`
- `dist/assets/index-[hash].css`

FastAPI automatically serves `frontend/dist/` at the root URL (`http://127.0.0.1:8000/`) when present, protected by strict Content Security Policy headers.

