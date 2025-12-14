# Demo Guide: Building a RAG App with Claude Code

## Introduction

This demonstration shows how to use Claude Code to build a fully functional application from a natural language description - what's often called "vibe coding."

**What we're building:** A local RAG (Retrieval-Augmented Generation) chatbot for Splunk documentation that:

- Ingests PDF manuals and converts them to searchable chunks
- Stores embeddings in Postgres with pgvector
- Answers questions with citations to source pages
- Runs entirely locally with no external LLM API calls

**What this demo shows:** Claude Code taking a natural language prompt and making all the architectural decisions - database schema, file structure, implementation details - without being given a detailed specification.

**Two constraints make this interesting:**

1. **Everything runs locally.** PDF parsing, chunking, embeddings, the database, and the chat model all run on the laptop. No external LLM API calls, and no document text leaves the machine. Ollama exposes an OpenAI-compatible API surface, so the app talks to it like a standard chat/embeddings endpoint, but it's running on localhost.

2. **No hand-written code.** Claude Code receives natural language prompts and you watch it create the project structure, wire up Postgres with pgvector, implement ingestion and retrieval, and ship a working UI.

This is not a claim that local models beat cloud models. The point is speed: how quickly you can go from zero to something useful when you describe what you want precisely and let an agent handle the implementation.

---

## Before the Demo

The following prerequisites must be installed and running before starting the demonstration.

**Required software:**

- macOS with Apple Silicon (M1/M2/M3/M4), 32GB+ unified memory recommended
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- [Ollama](https://ollama.com/download) (running, with models pulled)
- Claude Code (authenticated)
- VS Code or similar IDE
- [uv](https://docs.astral.sh/uv/) (Python package manager)

**Ollama models to pull:**

```bash
ollama pull gpt-oss:20b    # Chat model (~14GB)
ollama pull bge-m3         # Embedding model (~1.2GB)
```

Ollama provides [OpenAI-compatible endpoints](https://ollama.com/blog/openai-compatibility), so the app can use standard OpenAI SDK patterns while running entirely locally.

**Pre-pull the database image (recommended):**

```bash
docker pull pgvector/pgvector:pg18
```

This ensures Docker doesn't compile extensions during the demo. The [pgvector/pgvector](https://hub.docker.com/r/pgvector/pgvector/tags) repository publishes ready-to-use Postgres + pgvector images.

**Verify everything is ready:**

```bash
docker info                              # Docker is running
ollama list                              # Shows gpt-oss:20b and bge-m3
claude --version                         # Claude Code is installed
```

**Docs used in this demo:**

- Splunk 9.4.2 Admin Manual
- Splunk 9.4.2 Knowledge Manual
- Splunk 9.4.2 REST API Reference
- Splunk 9.4.2 Search Reference
- Splunk 9.4.2 Troubleshooting Manual

Pre-download these to `~/Downloads/splunk-pdfs/` so you can copy them during the demo instead of waiting for downloads. Citations will appear as `[Splunk 9.4.2 Search Reference p.42]` in answers.

See [Appendix: Detailed Setup](#appendix-detailed-setup) for full installation instructions and download commands.

---

## The Demo

### Opening (1 minute)

**Say:**

> "Today I'm going to build a useful internal tool from scratch using an AI coding agent.
>
> The end result is a local Splunk documentation chatbot. You point it at a folder of Splunk PDF manuals, it ingests them, builds a searchable index, and then you can ask questions and get answers with citations back to the exact manual and page.
>
> Two constraints make this interesting. First, everything runs locally - PDF parsing, chunking, embeddings, the database, and the chat model all run on my laptop. No external API calls, no document text leaving the machine. I'm using Ollama, which exposes an OpenAI-compatible API, so the app talks to it like a standard endpoint but it's running on localhost.
>
> Second, I'm not going to hand-write this app. I'm going to drive Claude Code with a natural language prompt, and you'll watch it create the project structure, wire up Postgres with pgvector, implement ingestion and retrieval, and ship a working UI.
>
> I've already installed the prerequisites - Docker, Ollama with the models, and Claude Code. I'm starting with an empty folder. Let's build something."

---

### Step 1: Open Empty Project (1 minute)

1. Open VS Code
2. Create and open a new empty folder called `splunk-rag-demo`
3. Open the integrated terminal: View → Terminal
4. Initialize git (allows `git diff` to show what Claude changed):

```bash
git init
```

**Say:** "Starting with a completely empty project folder. I'm initializing git so we can see exactly what Claude creates."

---

### Step 2: Start Claude Code (30 seconds)

In the terminal:

```bash
claude
```

**Say:** "I'm launching Claude Code in this directory. It's ready to receive instructions."

---

### Step 3: Give Claude the Prompt (paste and wait 20-30 minutes)

Paste this prompt into Claude Code:

```text
Build me a local RAG chatbot for Splunk documentation. I want to be able to ingest PDF manuals, ask questions about Splunk, and get answers with citations to the source pages.

Here's what I need:

**Tech stack:**
- Python 3.13 with uv for package management. Use pyproject.toml. `ty` for type checking and `ruff` for linting and formatting.
- Postgres 18 with pgvector for storage (I'll run it in Docker)
- Ollama for local LLM inference (already installed via homebrew)
- Chat model: gpt-oss:20b
- Embedding model: bge-m3

**What it should do:**

1. Ingest PDFs from a folder - convert them to text, split into chunks, generate embeddings, and store everything in the database. Track which document and page each chunk came from.

2. Answer questions using RAG - when I ask a question, find the most relevant chunks using both vector similarity and keyword search, then pass them to the LLM to generate an answer. The answer should cite sources like [Manual Name p.42]. If the retrieved chunks don't contain enough evidence, the assistant should say it can't find that in the docs rather than making things up.

3. Have a nice Streamlit UI with a chat interface. Show the sources for each answer so I can verify them.

**CLI commands I want (name the CLI `splunkbot`):**
- `splunkbot doctor` - preflight check that verifies Docker, Postgres, pgvector, Ollama, and required models are all reachable
- `splunkbot init-db` - initialize the database schema
- `splunkbot reset-db` - drop and recreate schema (for re-runs)
- `splunkbot ingest <path>` - ingest PDFs from a directory
- `splunkbot chat` - interactive CLI chat
- `splunkbot ui` - launch the Streamlit UI

**Docker configuration:**
- Create `docker-compose.yml` for the Postgres database
- Include a healthcheck so `docker compose ps` shows "healthy" before proceeding
- Postgres 18 changed PGDATA to `/var/lib/postgresql/18/docker` and the volume to `/var/lib/postgresql` - make the volume mount compatible with Postgres 18 defaults

**Packaging and ops deliverables:**
- Create `.env.example` with all configuration variables and sensible defaults
- Create `README.md` with exact local run steps (docker up, init-db, ingest, ui) and troubleshooting for Docker volumes and Ollama model loading
- Create `.gitignore` that excludes `data/`, `.env`, `__pycache__/`, `.venv/`, and any DB volumes or caches
- Prefer Python 3.13 compatible wheels - avoid dependencies that require source compilation on macOS arm64
- If you use any AGPL or non-permissive dependencies, call them out in the README and suggest permissive alternatives

**Ingestion output:**
- Print stats during ingestion: number of PDFs, pages processed, chunks stored, embedding dimension

Make sure the chunking is smart - don't break up code blocks or split in the middle of sentences. And use hybrid search (combining vector and keyword search) for better retrieval on technical documentation.
```

**Say:** "I'm giving Claude a natural language description of what I want. I'm telling it the tech stack and features, but I'm not specifying database schemas or file structures - that's up to Claude to figure out. This is vibe coding."

**While Claude works, narrate:**

- "Claude is planning the architecture based on my requirements."
- "Now it's setting up the project and deciding what dependencies we need."
- "It's creating the Docker configuration for our database."
- "Here it's designing the database schema - notice I didn't tell it what tables to create."
- "Now the PDF ingestion pipeline."
- "The retrieval logic with hybrid search."
- "And the Streamlit interface."

**When Claude asks for permission:** Click Allow or press 'y'.

**Say:** "Claude always asks before creating files. This gives me control over what gets created."

---

### Step 4: Set Up and Run (3 minutes)

Open a new terminal tab and run:

```bash
# Set up environment
cp .env.example .env
docker compose up -d
docker compose ps          # Wait for "healthy" status

# Install dependencies
uv sync

# Run preflight checks
uv run splunkbot doctor
```

**Say:** "The doctor command verifies all our dependencies are ready - Docker, Postgres, Ollama, and the models."

---

### Step 5: Ingest Documentation (5 minutes)

```bash
# Create data folder and copy PDFs
mkdir -p data/pdfs
cp ~/Downloads/splunk-pdfs/*.pdf data/pdfs/   # Or download fresh

# Initialize database and ingest
uv run splunkbot init-db
uv run splunkbot ingest data/pdfs
```

**Say:** "The ingestion is converting PDFs to text, splitting into chunks, and generating embeddings with our local model."

---

### Step 6: Pre-warm Ollama (15 seconds)

Load the model into memory before launching the UI to avoid dead air on the first question:

```bash
curl -s http://localhost:11434/api/generate -d '{"model": "gpt-oss:20b", "prompt": "hello", "stream": false}' > /dev/null
```

**Say:** "Pre-loading the model so our first question responds quickly."

---

### Step 7: Launch the UI (30 seconds)

```bash
uv run splunkbot ui
```

Browser opens to `http://localhost:8501`

**Say:** "Here's our chat interface. Claude designed this based on my description."

---

### Step 8: Demo the Chat (5 minutes)

**Question 1:** "What is props.conf used for and where is it located?"

**Say:** "A configuration question. Watch how it cites specific pages from the Admin Manual."

*(Expand Sources to show citations)*

**Question 2:** "Show me an example of using the stats command with a by clause"

**Say:** "A technical question. It pulls exact examples from the Search Reference."

**Question 3:** "How do I troubleshoot a universal forwarder that isn't sending data?"

**Say:** "Troubleshooting. The hybrid search helps match both meaning and specific terms."

**Question 4:** "What REST API endpoint would I use to manage saved searches?"

**Say:** "A REST API question - exercises the REST API Reference manual."

**Question 5:** "How do I create a Splunk SOAR playbook to quarantine a host?"

**Say:** "Something not in our docs - SOAR is a different product. Watch how it handles this gracefully."

*(Should say it can't find that information in the indexed documentation)*

---

### Closing (1 minute)

**Say:**

> "So in about 30 minutes, Claude Code built a complete RAG application from a natural language description. I didn't give it table schemas or file structures - I described what I wanted, and Claude figured out how to build it.
>
> This is vibe coding. You describe the vibe, the AI handles the details. Be clear about requirements and tech stack, but let Claude make the architectural decisions.
>
> And it's iterative. If something doesn't work, just tell Claude: 'The chunking is too aggressive, make chunks bigger.' Or 'Add a button to clear chat history.' Development at the speed of conversation."

---

## Troubleshooting

### Ollama not responding

```bash
curl -s http://localhost:11434/api/tags    # Test connection
# If not responding, open Ollama from Applications
```

If the model isn't loaded, Ollama needs time to load it into memory on first request. This can take 30-60 seconds for large models.

### Database connection failed

```bash
docker compose ps              # Check status
docker compose logs db         # View logs
docker compose restart         # Restart if needed
```

### Postgres 18 volume issues

The official Postgres image changed PGDATA and volume behavior in version 18+:
- `PGDATA` changed to `/var/lib/postgresql/18/docker`
- The defined `VOLUME` changed to `/var/lib/postgresql`
- Mounts should target `/var/lib/postgresql` (not `/var/lib/postgresql/data`)

If you see permission errors or data not persisting, check that your docker-compose volume mount is compatible with Postgres 18 defaults. See [Docker Hub postgres docs](https://hub.docker.com/_/postgres) for details.

### Slow inference

gpt-oss:20b needs significant memory. As a rule of thumb, a model's parameter count in GB should not exceed roughly half your unified memory. Check with Activity Monitor or `memory_pressure`.

### Model not found errors

Ensure the model names in your `.env` match exactly what Ollama reports:

```bash
ollama list    # Check exact model names
```

---

## Recovery Prompts

Use these when something breaks mid-demo. They're designed to get Claude back on track without redesigning the whole app.

### Fix a failing command

> One of the commands we just ran failed. Diagnose the failure using logs and error output, propose the smallest fix, apply it, and rerun the exact command until it succeeds. Do not refactor unrelated code.

### Improve ingestion for ugly PDFs

> The PDF extraction is producing messy text and retrieval quality is low. Improve extraction and chunking specifically for technical manuals. Preserve page citations. Keep changes localized to ingestion and chunking, and demonstrate the improvement with before/after retrieval results on the same question.

### Add a missing feature

> Add a button to clear chat history. Keep the change minimal - just the button and the state reset.

---

## Talking Points

**Why local?**

- No data leaves the laptop
- No API costs
- Works offline
- Full control over models and data

**Why RAG instead of fine-tuning?**

- No training required
- Easy to update (just re-ingest)
- Citations provide verifiability
- "No evidence, no answer" - the model admits when it can't find something rather than hallucinating

**Why hybrid retrieval?**

- Technical docs have specific terms (props.conf, tstats)
- Vector search captures semantic meaning
- Full-text search catches exact matches
- Fusion (like RRF) combines the best of both

**Why Postgres instead of a dedicated vector database?**

- One database for everything
- Full-text search built in
- pgvector is production-ready
- Simpler ops than running multiple datastores

**Modern Python workflow**

- uv for fast, reproducible dependency management
- pyproject.toml as the single source of truth
- [Astral ty](https://docs.astral.sh/ty/) for type checking
- ruff for linting and formatting

**Important reminder**

Never commit Splunk PDFs (or any proprietary documentation) to git. Keep them in a gitignored `data/` folder.

---

## Appendix: Detailed Setup

Complete these steps before the demonstration.

### Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew --version
```

### Install Git

```bash
brew install git
git --version
```

### Install uv

```bash
brew install uv
uv --version
```

### Install Docker Desktop

1. Download from [docker.com](https://www.docker.com/products/docker-desktop/)
2. Drag to Applications
3. Launch and wait for whale icon to stop animating

```bash
docker info
```

### Install Ollama

1. Download from [ollama.com](https://ollama.com/download)
2. Drag to Applications
3. Launch (llama icon appears in menu bar)

```bash
curl -s http://localhost:11434/api/tags | head -5
```

### Pull Models

See [gpt-oss:20b on Ollama](https://ollama.com/library/gpt-oss:20b) for model details.

```bash
ollama pull gpt-oss:20b
ollama pull bge-m3
ollama list
```

### Install Claude Code

```bash
brew install node
npm install -g @anthropic-ai/claude-code
claude --version
```

Launch and authenticate with your Anthropic account.

### Pre-Download PDFs (Optional)

```bash
mkdir -p ~/Downloads/splunk-pdfs

curl -L -o ~/Downloads/splunk-pdfs/splunk-admin-manual.pdf \
  "https://docs.splunk.com/index.php?title=Documentation:Splunk:Admin:Howtousethismanual:6.0beta&action=pdfbook&version=9.4.2&product=Splunk"

curl -L -o ~/Downloads/splunk-pdfs/splunk-search-reference.pdf \
  "https://docs.splunk.com/index.php?title=Documentation:Splunk:SearchReference:WhatsInThisManual:9.4.2&action=pdfbook&version=9.4.2&product=Splunk"

curl -L -o ~/Downloads/splunk-pdfs/splunk-rest-api-reference.pdf \
  "https://docs.splunk.com/index.php?title=Documentation:Splunk:RESTREF:RESTprolog:7.2.0&action=pdfbook&version=9.4.2&product=Splunk"

curl -L -o ~/Downloads/splunk-pdfs/splunk-knowledge-manager.pdf \
  "https://docs.splunk.com/index.php?title=Documentation:Splunk:Knowledge:WhatisSplunkknowledge:Minty&action=pdfbook&version=9.4.2&product=Splunk"

curl -L -o ~/Downloads/splunk-pdfs/splunk-troubleshooting.pdf \
  "https://docs.splunk.com/index.php?title=Documentation:Splunk:Troubleshooting:Whatsinhere:6.1beta&action=pdfbook&version=9.4.2&product=Splunk"

ls -lh ~/Downloads/splunk-pdfs/
```

---

## Appendix: Multi-Prompt Approach (Alternative)

The main demo uses a single comprehensive prompt to showcase "vibe coding." For production work or when you want more control, consider breaking the build into sequential prompts with explicit acceptance checks.

This approach trades demo speed for precision - each prompt builds a vertical slice and verifies it before moving on.

### Prompt 1: Set the contract and force a plan

```text
You are coding inside this repo using Claude Code. Start by inspecting the current directory and assume it is empty.

Goal: build a local-only Splunk documentation chatbot. I will have several Splunk PDF manuals (100+ pages each) in a folder. The app ingests PDFs, creates chunks with page metadata, embeds locally, stores in Postgres 18 with pgvector, and answers questions with citations to manual name and page number.

Hard constraints:
- Python 3.13 project managed with uv and a pyproject.toml
- Use ruff for linting and formatting
- Use Astral ty for type checking
- Services run in Docker, specifically Postgres 18 plus pgvector
- LLM inference is local via Ollama, using gpt-oss:20b for chat
- Embeddings must also be generated locally via Ollama
- No external AI API calls, and no sending document text off-machine
- Provide a simple UI (Streamlit is fine) and a CLI for ingest and chat

How to work:
- Do not ask me clarifying questions unless you are truly blocked
- If something is ambiguous, decide, document the decision briefly, and move on
- After you present a plan, immediately start executing it in small, verifiable steps
- After each major step, run the relevant commands to prove it works

Start by producing:
1. A short architecture overview
2. A numbered execution plan
3. The first concrete actions you will take in the repo

Then begin.
```

### Prompt 2: Scaffold the project and quality gates

```text
Implement the initial project scaffold now.

Requirements:
- Use uv to initialize the project and lock dependencies
- Configure ruff to run both lint and format
- Add ty type checking
- Create a clean package layout and an entrypoint CLI

Acceptance checks:
- Running the lint and format commands should succeed
- Running ty should succeed on the scaffold
- Tests should run even if there are none yet

Proceed and run the checks.
```

### Prompt 3: Docker services

```text
Create the Docker setup for the database layer.

Requirements:
- Use docker-compose with Postgres 18 and pgvector
- Use persistent volumes correctly for Postgres 18+
- Add health checks
- Put secrets in a .env file and commit a .env.example

Acceptance checks:
- docker-compose up starts cleanly
- The database is reachable from the host
- A quick SQL check can confirm pgvector is installed

Make it work and document the exact run commands in the README.
```

### Prompt 4: Database schema and init-db

```text
Implement the persistence layer.

Requirements:
- Define tables for: documents, chunks, embeddings, and metadata for citations
- Store: document name, source file path, page number, chunk text, and embedding vector
- Add indexes for vector similarity and text search
- Add an init-db CLI command that creates the schema idempotently
- Do not hardcode embedding dimensions - determine from the model at runtime

Acceptance checks:
- init-db creates everything from scratch
- Running init-db twice is safe
```

### Prompt 5: PDF ingestion pipeline

```text
Implement ingestion end-to-end.

Requirements:
- Input: folder of PDFs
- Extract text preserving page boundaries
- Chunk text into retrieval-friendly chunks
- Each chunk must carry document name and page number range for citations
- Add an ingest CLI command that detects already-ingested PDFs and skips unless forced

Acceptance checks:
- Ingest works on at least one sample PDF
- The database ends up with chunks and embeddings
```

### Prompt 6: Retrieval with citations

```text
Implement the retrieval and answer pipeline.

Requirements:
- Given a user question, embed it locally
- Retrieve top K chunks using pgvector similarity search
- Include a lexical retrieval path (FTS) and fuse results
- Generate an answer using Ollama gpt-oss:20b with citations

Rules for answering:
- The assistant must cite sources for every non-trivial claim
- If the retrieved chunks don't contain enough evidence, say it can't find that in the docs

Acceptance checks:
- A CLI chat mode can answer questions and show citations
```

### Prompt 7: Simple UI

```text
Add a UI for the demo.

Requirements:
- One screen: chat input, answer output
- A "Sources" panel showing retrieved chunks with citations
- A small "Index status" section showing number of PDFs and chunks

Acceptance checks:
- UI starts with one command
- Asking a question shows an answer plus sources
```

### Prompt 8: Quality gates

```text
Tighten quality gates.

Requirements:
- Add tests for chunking behavior and retrieval
- Make sure ruff lint + format passes
- Make sure ty passes

Acceptance checks:
- One command runs all checks locally
```

### Prompt 9: Polish and documentation

```text
Finish with polish.

Update the README to include:
- What this app does, in one paragraph
- Exact prerequisites and steps
- Troubleshooting section

Also add:
- A short list of suggested demo questions
- A note to never commit Splunk PDFs into git
```
