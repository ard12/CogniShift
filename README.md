# CogniShift

On-premise Agentic AI Workbench

## Quick Start

```bash
pip install -r requirements.txt
copy .env.example .env
cd src
uvicorn cognishift.app.main:app --reload
```

## Architecture
CogniShift is a FastAPI backend providing an Agentic AI Workbench designed for on-premise usage. It connects with local Ollama for language models, ChromaDB for knowledge base embeddings, and SQLite for structured data. The workspace routes will support multiple projects, agents, and data sources.
