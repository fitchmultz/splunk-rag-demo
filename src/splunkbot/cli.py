"""Typer CLI for splunkbot."""

import asyncio
import hashlib
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from splunkbot.config import settings

app = typer.Typer(
    name="splunkbot",
    help="Local RAG chatbot for Splunk documentation",
    no_args_is_help=True,
)
console = Console()


@app.command()
def doctor():
    """Run preflight checks for all dependencies."""
    import httpx

    checks: list[tuple[str, bool, str]] = []

    # Check Docker
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=5, check=False)
        status = "Running" if result.returncode == 0 else "Not running"
        checks.append(("Docker", result.returncode == 0, status))
    except FileNotFoundError:
        checks.append(("Docker", False, "Not installed"))
    except subprocess.TimeoutExpired:
        checks.append(("Docker", False, "Timeout"))

    # Check Docker Compose
    try:
        result = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, timeout=5, check=False
        )
        if result.returncode == 0:
            version = result.stdout.decode().strip().split()[-1]
            checks.append(("Docker Compose", True, version))
        else:
            checks.append(("Docker Compose", False, "Not available"))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        checks.append(("Docker Compose", False, "Not available"))

    # Check PostgreSQL
    try:
        import asyncpg

        async def check_pg():
            conn = await asyncpg.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=settings.postgres_user,
                password=settings.postgres_password,
                database=settings.postgres_db,
            )
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            return version

        version = asyncio.run(check_pg())
        short_version = version.split(",")[0] if version else "Connected"
        checks.append(("PostgreSQL", True, short_version))
    except Exception as e:
        error_msg = str(e).split("\n")[0][:50]
        checks.append(("PostgreSQL", False, error_msg))

    # Check pgvector
    try:
        import asyncpg

        async def check_pgvector():
            conn = await asyncpg.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=settings.postgres_user,
                password=settings.postgres_password,
                database=settings.postgres_db,
            )
            result = await conn.fetchval(
                "SELECT installed_version FROM pg_available_extensions WHERE name = 'vector'"
            )
            await conn.close()
            return result

        version = asyncio.run(check_pgvector())
        checks.append(("pgvector", bool(version), f"v{version}" if version else "Not installed"))
    except Exception:
        checks.append(("pgvector", False, "Check PostgreSQL first"))

    # Check Ollama
    try:
        resp = httpx.get(f"{settings.ollama_host}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            checks.append(("Ollama", True, "Running"))

            # Check chat model
            chat_available = settings.chat_model in models or any(
                m.startswith(settings.chat_model.split(":")[0]) for m in models
            )
            checks.append(
                (
                    f"  Model: {settings.chat_model}",
                    chat_available,
                    "Available" if chat_available else "Not pulled",
                )
            )

            # Check embedding model
            embed_available = settings.embedding_model in models or any(
                m.startswith(settings.embedding_model.split(":")[0]) for m in models
            )
            checks.append(
                (
                    f"  Model: {settings.embedding_model}",
                    embed_available,
                    "Available" if embed_available else "Not pulled",
                )
            )
        else:
            checks.append(("Ollama", False, f"HTTP {resp.status_code}"))
    except httpx.ConnectError:
        checks.append(("Ollama", False, "Not running (connection refused)"))
    except Exception as e:
        checks.append(("Ollama", False, str(e)[:50]))

    # Display results
    table = Table(title="Preflight Checks")
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    all_passed = True
    for name, passed, details in checks:
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        if not passed and not name.startswith("  "):
            all_passed = False
        table.add_row(name, status, details)

    console.print(table)

    if not all_passed:
        console.print("\n[yellow]Some checks failed. Please fix the issues above.[/yellow]")
        raise typer.Exit(1)
    else:
        console.print("\n[green]All checks passed![/green]")


@app.command()
def init_db():
    """Initialize database schema."""
    from splunkbot.db.connection import close_pool, get_pool
    from splunkbot.db.schema import init_schema

    async def run():
        # Use with_vector=False since pgvector extension may not exist yet
        pool = await get_pool(with_vector=False)
        await init_schema(pool)
        await close_pool()

    with console.status("[bold green]Initializing database schema..."):
        asyncio.run(run())

    console.print("[green]Database schema initialized successfully![/green]")


@app.command()
def reset_db():
    """Drop and recreate database schema (deletes all data)."""
    from splunkbot.db.connection import close_pool, get_pool
    from splunkbot.db.schema import reset_schema

    msg = "[yellow]This will delete ALL data including documents, chunks, "
    msg += "and conversations. Continue?[/yellow]"
    if not typer.confirm(msg):
        raise typer.Abort()

    async def run():
        # Use with_vector=False since we're recreating pgvector extension
        pool = await get_pool(with_vector=False)
        await reset_schema(pool)
        await close_pool()

    with console.status("[bold red]Resetting database..."):
        asyncio.run(run())

    console.print("[green]Database reset successfully![/green]")


PATH_ARG = typer.Argument(..., help="Path to directory containing PDF files")
FORCE_OPT = typer.Option(False, "--force", "-f", help="Re-ingest all files")


@app.command()
def ingest(
    path: Path = PATH_ARG,
    force: bool = FORCE_OPT,
):
    """Ingest PDFs from a directory into the database."""
    from splunkbot.db.connection import close_pool, get_pool
    from splunkbot.ingestion.chunker import chunk_pages
    from splunkbot.ingestion.embeddings import embed_texts
    from splunkbot.ingestion.pdf import extract_pdf, get_pdf_metadata

    if not path.exists():
        console.print(f"[red]Path not found: {path}[/red]")
        raise typer.Exit(1)

    if not path.is_dir():
        console.print(f"[red]Path is not a directory: {path}[/red]")
        raise typer.Exit(1)

    pdfs = list(path.glob("*.pdf"))
    if not pdfs:
        console.print(f"[yellow]No PDF files found in {path}[/yellow]")
        raise typer.Exit(0)

    console.print(f"Found [cyan]{len(pdfs)}[/cyan] PDF files to process\n")

    async def run():
        pool = await get_pool()
        stats = {"pdfs": 0, "pages": 0, "chunks": 0, "skipped": 0}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
            refresh_per_second=4,
        ) as progress:
            overall_task = progress.add_task(
                "[bold]Overall", total=len(pdfs)
            )
            file_task = progress.add_task(
                "[dim]Waiting...", total=100, visible=True
            )

            for pdf_path in pdfs:
                pdf_name = pdf_path.name
                short_name = pdf_name[:35] + "..." if len(pdf_name) > 38 else pdf_name

                # Reset file progress
                progress.reset(file_task)
                progress.update(
                    file_task,
                    description=f"[cyan]{short_name}[/cyan]",
                    total=100,
                    completed=0,
                )

                # Calculate file hash
                progress.update(file_task, completed=2)
                file_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

                # Check if already ingested
                if not force:
                    existing = await pool.fetchval(
                        "SELECT id FROM documents WHERE file_hash = $1", file_hash
                    )
                    if existing:
                        progress.console.print(
                            f"  [dim]⏭ Skipped {pdf_name} (unchanged)[/dim]"
                        )
                        stats["skipped"] += 1
                        progress.advance(overall_task)
                        continue

                # Delete existing document if re-ingesting
                await pool.execute("DELETE FROM documents WHERE filename = $1", pdf_name)

                # Extract pages (5% of file progress)
                progress.update(file_task, completed=5)
                pages = extract_pdf(pdf_path)
                stats["pages"] += len(pages)

                # Get metadata
                metadata = get_pdf_metadata(pdf_path)

                # Chunk text (10% of file progress)
                progress.update(file_task, completed=10)
                chunks = chunk_pages(pages)
                stats["chunks"] += len(chunks)

                # Generate embeddings (10-90% of file progress)
                chunk_texts = [c.content for c in chunks]

                def embed_progress(completed: int, total: int) -> None:
                    # Embedding is 10% to 90% of file progress
                    pct = 10 + int((completed / total) * 80) if total > 0 else 10
                    progress.update(file_task, completed=pct)

                embeddings = embed_texts(chunk_texts, progress_callback=embed_progress)

                # Store document (90%)
                progress.update(file_task, completed=90)
                doc_id = await pool.fetchval(
                    """
                    INSERT INTO documents (filename, file_hash, page_count)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    pdf_name,
                    file_hash,
                    metadata["page_count"],
                )

                # Store chunks with embeddings (90-100%)
                insert_sql = """
                    INSERT INTO chunks
                        (document_id, page_number, chunk_index, content, embedding)
                    VALUES ($1, $2, $3, $4, $5)
                """
                total_chunks = len(chunks)
                for i, (chunk, embedding) in enumerate(
                    zip(chunks, embeddings, strict=False)
                ):
                    if i % 20 == 0:
                        pct = 90 + int((i / total_chunks) * 10)
                        progress.update(file_task, completed=pct)
                    await pool.execute(
                        insert_sql,
                        doc_id,
                        chunk.page_number,
                        chunk.chunk_index,
                        chunk.content,
                        embedding.tolist(),
                    )

                # Complete file
                progress.update(file_task, completed=100)
                stats["pdfs"] += 1
                progress.advance(overall_task)
                progress.console.print(
                    f"  [green]✓ {pdf_name}[/green]: "
                    f"{len(pages)} pages, {len(chunks)} chunks"
                )

            # Hide file task when done
            progress.update(file_task, visible=False)

        await close_pool()
        return stats

    stats = asyncio.run(run())

    # Display summary
    table = Table(title="Ingestion Complete")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("PDFs processed", str(stats["pdfs"]))
    table.add_row("PDFs skipped (unchanged)", str(stats["skipped"]))
    table.add_row("Pages extracted", str(stats["pages"]))
    table.add_row("Chunks stored", str(stats["chunks"]))
    table.add_row("Embedding dimensions", str(settings.embedding_dimensions))
    console.print(table)


@app.command()
def chat():
    """Start an interactive CLI chat session."""
    from splunkbot.chat.rag import rag_query
    from splunkbot.db.connection import close_pool

    console.print("[bold cyan]Splunk Documentation Assistant[/bold cyan]")
    console.print("Type [green]quit[/green], [green]exit[/green], or [green]q[/green] to end.")
    console.print("Type [green]new[/green] to start a new conversation.\n")

    conversation_id: int | None = None

    async def run_query(query: str, conv_id: int | None) -> tuple[str, list[dict], int]:
        response, new_conv_id = await rag_query(query, conv_id)
        return response.answer, response.sources, new_conv_id

    try:
        while True:
            try:
                query = console.input("[bold blue]You:[/bold blue] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if query.lower() in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if query.lower() == "new":
                conversation_id = None
                console.print("[dim]Starting new conversation...[/dim]\n")
                continue

            if not query:
                continue

            with console.status("[bold green]Thinking..."):
                answer, sources, conversation_id = asyncio.run(run_query(query, conversation_id))

            console.print(f"\n[bold green]Assistant:[/bold green] {answer}\n")

            if sources:
                console.print("[dim]Sources:[/dim]")
                for src in sources:
                    manual = src["filename"].replace(".pdf", "").replace("-", " ")
                    console.print(f"  [dim]- {manual} p.{src['page_number']}[/dim]")
                console.print()

    finally:
        asyncio.run(close_pool())


@app.command()
def ui():
    """Launch the Streamlit web interface."""
    streamlit_app = Path(__file__).parent / "ui" / "streamlit_app.py"

    if not streamlit_app.exists():
        console.print(f"[red]Streamlit app not found at {streamlit_app}[/red]")
        raise typer.Exit(1)

    console.print("[bold cyan]Starting Streamlit UI...[/bold cyan]")
    console.print("Press Ctrl+C to stop the server.\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(streamlit_app)],
            check=True,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Streamlit server stopped.[/dim]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Streamlit exited with code {e.returncode}[/red]")
        raise typer.Exit(e.returncode) from None


if __name__ == "__main__":
    app()
