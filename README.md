# Splunk RAG Chatbot

A local RAG (Retrieval-Augmented Generation) chatbot for Splunk documentation. Ingest PDF manuals, ask questions, and get answers with citations.

## Features

- PDF ingestion with page tracking and smart chunking
- Hybrid search combining vector similarity and keyword search (RRF fusion)
- Citations like `[Splunk 9.4.2 Admin p.42]` for every claim
- Interactive CLI and Streamlit web UI
- Conversation history persisted to database
- Smart re-ingestion (skips unchanged files)

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for package management
- Docker and Docker Compose
- Ollama (installed via Homebrew or directly)
- ~16GB RAM for gpt-oss:20b model

## Quick Start

### 1. Clone and Setup

```bash
cd splunk-rag-demo

# Copy environment file
cp .env.example .env

# Install dependencies with uv
uv sync
```

### 2. Start PostgreSQL

```bash
docker compose up -d

# Wait for healthy status
docker compose ps
```

### 3. Pull Ollama Models

```bash
ollama pull gpt-oss:20b
ollama pull bge-m3
```

### 4. Initialize Database

```bash
uv run splunkbot init-db
```

### 5. Ingest PDFs

Place your Splunk PDF manuals in `data/pdfs/`, then:

```bash
uv run splunkbot ingest data/pdfs
```

### 6. Start Chatting

**CLI:**

```bash
uv run splunkbot chat
```

**Web UI:**

```bash
uv run splunkbot ui
```

## CLI Commands

All commands are run via `uv run splunkbot <command>`:

| Command | Description |
|---------|-------------|
| `uv run splunkbot doctor` | Preflight check for Docker, Postgres, pgvector, Ollama |
| `uv run splunkbot init-db` | Initialize database schema |
| `uv run splunkbot reset-db` | Drop and recreate schema (deletes all data) |
| `uv run splunkbot ingest <path>` | Ingest PDFs from a directory |
| `uv run splunkbot chat` | Interactive CLI chat |
| `uv run splunkbot ui` | Launch Streamlit web interface |

**Tip:** You can also activate the virtual environment to skip the `uv run` prefix:

```bash
source .venv/bin/activate
splunkbot doctor
```

### Ingest Options

```bash
# Normal ingest (skips unchanged files)
uv run splunkbot ingest data/pdfs

# Force re-ingest all files
uv run splunkbot ingest data/pdfs --force
```

## Configuration

All settings can be configured via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | localhost | Database host |
| `POSTGRES_PORT` | 5432 | Database port |
| `POSTGRES_USER` | splunkbot | Database user |
| `POSTGRES_PASSWORD` | splunkbot | Database password |
| `POSTGRES_DB` | splunkbot | Database name |
| `OLLAMA_HOST` | <http://localhost:11434> | Ollama API endpoint |
| `CHAT_MODEL` | gpt-oss:20b | LLM for chat |
| `EMBEDDING_MODEL` | bge-m3 | Model for embeddings |
| `CHUNK_SIZE` | 1000 | Max chunk size in characters |
| `CHUNK_OVERLAP` | 200 | Overlap between chunks |
| `TOP_K_RESULTS` | 5 | Number of chunks to retrieve |
| `RRF_K` | 60 | RRF fusion constant |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   PDF Files     │────▶│   Ingestion     │
└─────────────────┘     │   - Extract     │
                        │   - Chunk       │
                        │   - Embed       │
                        └────────┬────────┘
                                 │
                                 ▼
┌─────────────────┐     ┌─────────────────┐
│   User Query    │────▶│  Hybrid Search  │
└─────────────────┘     │  - Vector       │
                        │  - Keyword      │
                        │  - RRF Fusion   │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   RAG Pipeline  │
                        │  - Context      │
                        │  - LLM Generate │
                        │  - Citations    │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   Response      │
                        │   with Sources  │
                        └─────────────────┘
```

## Troubleshooting

### Docker Volume Issues (Postgres 18)

Postgres 18 changed the default PGDATA location to `/var/lib/postgresql/18/docker`. If you see permission errors:

```bash
# Remove old volume and restart
docker compose down -v
docker compose up -d
```

### Ollama Model Not Loading

```bash
# Check if models are available
ollama list

# Pull models if missing
ollama pull gpt-oss:20b
ollama pull bge-m3

# Check Ollama is running
curl http://localhost:11434/api/tags
```

### Database Connection Refused

```bash
# Check container is running and healthy
docker compose ps

# View logs
docker compose logs db

# Restart if needed
docker compose restart db
```

### Slow Ingestion

Embedding generation is the bottleneck. For large document sets:

1. Ensure Ollama has GPU access
2. Consider reducing `CHUNK_SIZE` (smaller chunks = more API calls but less memory)
3. Use `--force` only when needed

### No Results Found

1. Verify documents were ingested:

   ```bash
   docker exec -it splunkbot-db psql -U splunkbot -c "SELECT COUNT(*) FROM chunks;"
   ```

2. Try different search terms
3. Check if keyword search is working by using exact terms from the docs

## Development

### Type Checking

```bash
uv run ty check
```

### Linting and Formatting

```bash
uv run ruff check .
uv run ruff format .
```

### Database Schema

The schema includes:

- `documents` - Ingested PDF metadata and file hashes
- `chunks` - Text chunks with embeddings and tsvector
- `conversations` - Chat session metadata
- `messages` - Conversation history with sources

## License Notes

This project uses the following notable dependencies:

- **PyMuPDF (AGPL-3.0)**: Used for PDF text extraction. If you distribute this software, you must comply with AGPL requirements (provide source code). For commercial use without AGPL obligations, consider:
  - `pdfplumber` (MIT) - slower but permissively licensed
  - `pypdf` (BSD) - pure Python alternative
  - Commercial PyMuPDF license from Artifex

All other dependencies use permissive licenses (MIT, BSD, Apache 2.0).

## Sample Questions

Try these questions after ingesting Splunk documentation:

- "What is props.conf used for?"
- "How do I configure a TCP input?"
- "What are the tstats command options?"
- "How do I troubleshoot slow searches?"
- "What is the difference between index-time and search-time field extractions?"
