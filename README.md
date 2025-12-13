# Splunk RAG Demo

A local RAG (Retrieval-Augmented Generation) chatbot for Splunk documentation that runs entirely on Apple Silicon with no cloud dependencies.

## Overview

This application ingests Splunk PDF manuals, converts them to searchable chunks, and provides a chat interface that answers questions with citations to the source documentation.

**Key capabilities:**

- PDF ingestion with structure-aware Markdown conversion
- Local embeddings using BGE-M3 (MIT licensed, 1024 dimensions)
- Local inference using gpt-oss:20b via Ollama
- Hybrid retrieval combining vector search and full-text search
- Verifiable answers with `[Manual Name p.X]` citations
- Streamlit web interface

## Requirements

- macOS with Apple Silicon (32GB+ unified memory recommended)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Ollama](https://ollama.com/download)
- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

## Getting Started

### 1. Start the database

```bash
cp .env.example .env
docker compose up -d
```

### 2. Install Ollama models

```bash
ollama pull gpt-oss:20b
ollama pull bge-m3
```

### 3. Download documentation

```bash
mkdir -p data/pdfs
curl -L -o data/pdfs/splunk-admin-manual.pdf \
  "https://docs.splunk.com/index.php?title=Documentation:Splunk:Admin:Howtousethismanual:6.0beta&action=pdfbook&version=9.4.2&product=Splunk"
```

### 4. Install and run

```bash
uv sync
uv run splunkbot init-db
uv run splunkbot ingest data/pdfs
uv run splunkbot ui
```

## Usage

| Command | Description |
|---------|-------------|
| `splunkbot init-db` | Initialize the database schema |
| `splunkbot ingest <path>` | Ingest PDFs from a directory |
| `splunkbot chat` | Start an interactive CLI chat session |
| `splunkbot api` | Launch the REST API server |
| `splunkbot ui` | Open the Streamlit web interface |

## How It Works

```text
PDF → Markdown → Chunks → Embeddings → Postgres/pgvector
                                            ↓
User Query → Embed → Hybrid Retrieval → LLM → Answer + Citations
```

1. **Ingestion**: PDFs are converted to Markdown using PyMuPDF4LLM, preserving headers and code blocks
2. **Chunking**: Content is split on headings with page metadata for citations
3. **Embedding**: Each chunk is embedded locally using BGE-M3
4. **Storage**: Chunks and embeddings are stored in Postgres with pgvector HNSW indexes
5. **Retrieval**: Queries use both vector similarity and full-text search, fused with RRF
6. **Generation**: Retrieved chunks are passed to the LLM with instructions to cite sources

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |
| `POSTGRES_DB` | Database name | `splunkbot` |
| `POSTGRES_USER` | Database user | `splunkbot` |
| `POSTGRES_PASSWORD` | Database password | `splunkbot` |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434` |
| `CHAT_MODEL` | Model for chat | `gpt-oss:20b` |
| `EMBEDDING_MODEL` | Model for embeddings | `bge-m3` |

**Model Selection:** Any Ollama-compatible model can be used. Choose a model that fits your system's unified memory. As a general rule, a model's parameter size in GB should not exceed roughly half your unified memory for comfortable operation.

## License

MIT
