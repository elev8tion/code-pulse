"""CodePulse CLI — typer entry points."""
from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="codepulse",
    help="Local web-based visual studio for solo agentic programming with Claude Code.",
    add_completion=False,
    invoke_without_command=True,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3000


def _project_name_from_path(path: Path) -> str:
    return path.resolve().name or "project"


def _launch_server(
    project_path: str,
    project_name: str,
    resume: bool = False,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    """Start the FastAPI server and open the browser."""
    # Set env vars before uvicorn imports/runs the server module
    os.environ["CODEPULSE_PROJECT_PATH"] = project_path
    os.environ["CODEPULSE_PROJECT_NAME"] = project_name
    os.environ["CODEPULSE_RESUME"] = "1" if resume else "0"

    url = f"http://{host}:{port}"
    typer.echo(f"🚀  Starting Code-Pulse for project '{project_name}'")
    typer.echo(f"    Path:    {project_path}")
    typer.echo(f"    Server:  {url}")
    typer.echo("    Press Ctrl+C to stop.\n")

    import threading
    import time

    def _open_browser() -> None:
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    try:
        import uvicorn
        uvicorn.run(
            "codepulse.server:app",
            host=host,
            port=port,
            log_level="warning",
        )
    except ImportError:
        typer.echo("Error: uvicorn not installed. Run: pip install codepulse", err=True)
        raise typer.Exit(1)


@app.callback()
def default(
    ctx: typer.Context,
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Server host"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Server port"),
) -> None:
    """Launch Code-Pulse for the current directory and open the browser."""
    if ctx.invoked_subcommand is None:
        project_path = str(Path.cwd())
        project_name = _project_name_from_path(Path(project_path))
        _launch_server(project_path, project_name, resume=False, host=host, port=port)


@app.command(name="open")
def cmd_open(
    path: str = typer.Argument(..., help="Path to project folder to open"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Override project name"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Server host"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Server port"),
) -> None:
    """Open an existing project folder in Code-Pulse."""
    p = Path(path)
    if not p.exists():
        typer.echo(f"Error: path does not exist: {path}", err=True)
        raise typer.Exit(1)
    project_name = name or _project_name_from_path(p)
    _launch_server(str(p.resolve()), project_name, resume=False, host=host, port=port)


@app.command(name="resume")
def cmd_resume(
    project: str = typer.Argument(..., help="Project name to resume"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Server host"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Server port"),
) -> None:
    """Resume the latest session for a project."""
    from codepulse.session.manager import SessionManager
    session = SessionManager.load_latest(project)
    if session is None:
        typer.echo(f"No session found for project: {project}", err=True)
        raise typer.Exit(1)
    _launch_server(session.project_path, project, resume=True, host=host, port=port)


@app.command(name="list")
def cmd_list() -> None:
    """List all saved projects and sessions."""
    from codepulse.session.manager import SessionManager
    projects = SessionManager.list_projects()
    if not projects:
        typer.echo("No projects found in ~/.codepulse/projects/")
        return
    typer.echo(f"\n{'Project':<30} {'Sessions':>8}  {'Latest'}")
    typer.echo("─" * 55)
    for p in projects:
        typer.echo(f"{p['name']:<30} {p['session_count']:>8}  {p['latest']}")
    typer.echo()


@app.command(name="export")
def cmd_export(
    project: str = typer.Argument(..., help="Project name to export"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path for markdown file"),
) -> None:
    """Export the latest session for a project as a markdown report."""
    from codepulse.session.manager import SessionManager
    from codepulse.session.exporter import MarkdownExporter
    from codepulse.utils.paths import project_dir

    session = SessionManager.load_latest(project)
    if session is None:
        typer.echo(f"No session found for project: {project}", err=True)
        raise typer.Exit(1)

    out_path = Path(output) if output else Path.cwd() / f"codepulse-{project}-{session.session_date}.md"
    pd = project_dir(project)
    exporter = MarkdownExporter(session, pd)
    exporter.export(out_path)
    typer.echo(f"Exported to: {out_path}")


if __name__ == "__main__":
    app()
