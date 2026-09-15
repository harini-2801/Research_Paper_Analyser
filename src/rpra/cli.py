"""
CLI entry point  —  `rpra` command.

Usage examples
--------------
  rpra run                                  # run with config.yaml
  rpra run -b heuristic --no-nli            # fully offline, no API key
  rpra run -b llm                           # LLM extraction (needs OPENAI_API_KEY)
  rpra serve                                # launch the web UI
  rpra validate-config                      # validate config only
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from rpra.config import load_settings

app = typer.Typer(
    name="rpra",
    help="Research Paper Relationship Analyzer",
    add_completion=False,
)
console = Console()


@app.command("validate-config")
def validate_config(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Path to config file"),
) -> None:
    """Validate the configuration file and print a summary."""
    try:
        settings = load_settings(config)
        console.print(Panel("[green]✓ Configuration is valid[/green]", title="Config Validation"))
        console.print(f"  LLM provider  : {settings.llm.provider} / {settings.llm.model}")
        console.print(f"  Embedding     : {settings.embedding.model}")
        console.print(f"  NLI model     : {settings.nli.model}")
        console.print(f"  Corpus path   : {settings.storage.corpus_input_path}")
        console.print(f"  Output path   : {settings.storage.output_path}")
        w = settings.relationship_scoring.weights
        console.print(
            f"  Score weights : obj={w.objective} meth={w.methodology} "
            f"ds={w.dataset} res={w.results_metrics} cite={w.citation}"
        )
    except Exception as exc:
        console.print(f"[bold red]✗ Configuration error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command("run")
def run(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Path to config file"),
    backend: str = typer.Option(
        None,
        "--extraction-backend",
        "-b",
        help="auto | llm | heuristic. 'heuristic' needs no API key.",
    ),
    no_nli: bool = typer.Option(
        False, "--no-nli", help="Skip the NLI model; use numeric claim comparison only"
    ),
    skip_extraction: bool = typer.Option(
        False, "--skip-extraction", help="Skip extraction entirely (smoke test only)"
    ),
    skip_explanation: bool = typer.Option(
        False, "--skip-explanation", help="Skip LLM explanation generation"
    ),
) -> None:
    """Run the full analysis pipeline."""
    # ---- Load & validate config ------------------------------------------
    try:
        settings = load_settings(config)
    except Exception as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    settings.resolve_api_key()

    # ---- Progress panel --------------------------------------------------
    from rpra.progress import ProgressPanel
    panel = ProgressPanel(log_path=settings.storage.log_path)

    console.print(
        Panel(
            "[bold cyan]Research Paper Relationship Analyzer[/bold cyan]\n"
            f"Corpus: [yellow]{settings.storage.corpus_input_path}[/yellow]",
            title="RPRA",
        )
    )

    # ---- Run pipeline ----------------------------------------------------
    from rpra.pipeline import run_pipeline

    try:
        result = run_pipeline(
            settings,
            on_progress=panel.callback(),
            skip_extraction=skip_extraction,
            skip_explanation=skip_explanation,
            extraction_backend=backend,
            use_nli=False if no_nli else None,
        )
    except Exception as exc:
        console.print(f"[bold red]Pipeline error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # ---- Summary ---------------------------------------------------------
    panel.print_summary()
    console.print(
        Panel(
            f"[green]Documents processed :[/green] {len(result.documents)}\n"
            f"[green]Extraction backend  :[/green] {result.extraction_backend or 'skipped'}\n"
            f"[green]Embedding backend   :[/green] {result.embedding_backend or 'n/a'}\n"
            f"[green]Entities extracted  :[/green] {len(result.entities)}\n"
            f"[green]Bridge concepts     :[/green] {len(result.bridge_entities)}\n"
            f"[green]Relations found     :[/green] {len(result.relations)}\n"
            f"[green]KG nodes / edges    :[/green] "
            f"{result.knowledge_graph.node_count() if result.knowledge_graph else 0} / "
            f"{result.knowledge_graph.edge_count() if result.knowledge_graph else 0}\n"
            f"[green]Contradictions      :[/green] {len(result.contradictions)}\n"
            f"[green]Research gaps       :[/green] {len(result.gaps)}\n"
            f"[green]Elapsed             :[/green] {result.elapsed_seconds}s\n"
            f"[green]JSON report         :[/green] {result.report_json}\n"
            f"[green]Markdown report     :[/green] {result.report_md}",
            title="Pipeline Complete",
        )
    )

    if result.ingestion_errors:
        console.print(f"[yellow]⚠ {len(result.ingestion_errors)} file(s) failed to ingest.[/yellow]")
        for err in result.ingestion_errors:
            console.print(f"  • {err['file']}: {err['reason']}")


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind server"),
    port: int = typer.Option(8000, "--port", "-p", help="Port number to bind server"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Automatically open web browser"),
) -> None:
    """Launch the web UI and REST API."""
    import webbrowser

    import uvicorn

    url = f"http://{host}:{port}"
    console.print(
        Panel(
            f"[bold cyan]Research Paper Relationship Analyzer[/bold cyan]\n"
            f"URL: [bold green]{url}[/bold green]",
            title="Web UI",
        )
    )

    if open_browser:
        webbrowser.open(url)

    uvicorn.run("rpra.server:app", host=host, port=port, reload=False)

