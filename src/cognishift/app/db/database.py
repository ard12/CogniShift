import aiosqlite
from contextlib import asynccontextmanager
from cognishift.app.config import settings

async def init_db() -> None:
    """Initialize the database by creating all required tables."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA busy_timeout=30000")
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                name TEXT NOT NULL, 
                description TEXT, 
                operating_mode TEXT DEFAULT 'local', 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS agent_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id), 
                name TEXT NOT NULL, 
                description TEXT, 
                system_instructions TEXT, 
                model_name TEXT DEFAULT 'llama3.2:3b', 
                status TEXT DEFAULT 'active', 
                allowed_tool_ids TEXT DEFAULT '[]', 
                approval_required INTEGER DEFAULT 0, 
                knowledge_source_ids TEXT DEFAULT '[]', 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id), 
                name TEXT NOT NULL, 
                source_type TEXT NOT NULL, 
                original_filename TEXT, 
                local_path TEXT, 
                processing_status TEXT DEFAULT 'pending', 
                checksum TEXT, 
                chunk_count INTEGER DEFAULT 0, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tool_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                name TEXT NOT NULL UNIQUE, 
                description TEXT, 
                risk_level TEXT NOT NULL DEFAULT 'read_only', 
                requires_approval INTEGER DEFAULT 0, 
                enabled INTEGER DEFAULT 1, 
                implementation_key TEXT NOT NULL, 
                input_schema TEXT DEFAULT '{}', 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                workspace_id INTEGER NOT NULL, 
                agent_id INTEGER NOT NULL, 
                user_id TEXT DEFAULT 'operator', 
                input_text TEXT, 
                input_type TEXT DEFAULT 'text', 
                input_image_path TEXT, 
                status TEXT DEFAULT 'running', 
                model_name TEXT, 
                operating_mode TEXT, 
                result_text TEXT, 
                sources_used TEXT, 
                confidence REAL, 
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                completed_at TIMESTAMP, 
                error_message TEXT,
                structured_plan TEXT
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                run_id INTEGER NOT NULL REFERENCES agent_runs(id), 
                event_type TEXT NOT NULL, 
                message TEXT, 
                structured_data TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS approval_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                run_id INTEGER NOT NULL REFERENCES agent_runs(id), 
                tool_id INTEGER NOT NULL REFERENCES tool_definitions(id), 
                status TEXT DEFAULT 'pending', 
                request_reason TEXT, 
                parameters TEXT, 
                risk_level TEXT, 
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                reviewed_by TEXT, 
                reviewed_at TIMESTAMP,
                reviewed_by_2 TEXT,
                reviewed_at_2 TIMESTAMP,
                required_approvals INTEGER DEFAULT 1
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                workspace_id INTEGER, 
                actor_id TEXT DEFAULT 'system', 
                action TEXT NOT NULL, 
                resource_type TEXT, 
                resource_id INTEGER, 
                details TEXT, 
                result TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace_id, name)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                source_node_id INTEGER NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
                relation_type TEXT NOT NULL,
                target_node_id INTEGER NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
                properties TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS workspace_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                run_id INTEGER REFERENCES agent_runs(id),
                filename TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                title TEXT,
                description TEXT,
                file_size INTEGER NOT NULL,
                sha256_hash TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(workspace_id, relative_path)
            )
        ''')
        
        try:
            await db.execute("ALTER TABLE agent_runs ADD COLUMN structured_plan TEXT")
        except Exception:
            pass

        try:
            await db.execute("ALTER TABLE knowledge_sources ADD COLUMN active_processing_version TEXT")
        except Exception:
            pass

        await db.execute('''
            CREATE TABLE IF NOT EXISTS document_processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                processing_version TEXT NOT NULL,
                status TEXT NOT NULL,
                total_pages INTEGER NOT NULL DEFAULT 0,
                native_pages INTEGER NOT NULL DEFAULT 0,
                ocr_pages INTEGER NOT NULL DEFAULT 0,
                vision_pages INTEGER NOT NULL DEFAULT 0,
                failed_pages INTEGER NOT NULL DEFAULT 0,
                error_code TEXT,
                error_message TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS document_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
                processing_version TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                extraction_method TEXT NOT NULL,
                ocr_confidence REAL,
                text_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_id, processing_version, page_number)
            )
        ''')
        await db.execute("CREATE INDEX IF NOT EXISTS idx_doc_pages_source ON document_pages(source_id, processing_version)")
        
        # Phase 6 Bounded Network Audit Ledger
        await db.execute('''
            CREATE TABLE IF NOT EXISTS network_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                component TEXT NOT NULL,
                method TEXT,
                requested_host TEXT NOT NULL,
                resolved_ip TEXT,
                port INTEGER,
                destination_class TEXT NOT NULL,
                policy_decision TEXT NOT NULL,
                reason TEXT NOT NULL
            )
        ''')
        # Phase 7 Safe Migration: Dual Four-Eyes Approval columns
        for col, col_def in [
            ("reviewed_by_2", "TEXT"),
            ("reviewed_at_2", "TIMESTAMP"),
            ("required_approvals", "INTEGER DEFAULT 1")
        ]:
            try:
                await db.execute(f"ALTER TABLE approval_requests ADD COLUMN {col} {col_def}")
            except Exception:
                pass

        await db.commit()

@asynccontextmanager
async def get_db():
    """Context manager that yields an aiosqlite connection with Row factory."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA busy_timeout = 30000;")
        await db.execute("PRAGMA synchronous = NORMAL;")
        db.row_factory = aiosqlite.Row
        yield db
