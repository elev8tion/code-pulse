"""CodePulse CLI — typer entry points."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="codepulse",
    help="Claude Code TUI with codebase visualization and rotating subagents.",
    add_completion=False,
    invoke_without_command=True,
)


def _project_name_from_path(path: Path) -> str:
    return path.resolve().name or "project"


def _launch(project_path: str, project_name: str, resume: bool = False) -> None:
    from codepulse.app import CodePulseApp
    tui = CodePulseApp(
        project_path=project_path,
        project_name=project_name,
        resume=resume,
    )
    tui.run()


@app.callback()
def default(ctx: typer.Context) -> None:
    """Run with no subcommand to open the project launcher."""
    if ctx.invoked_subcommand is None:
        _run_launcher()


def _run_launcher() -> None:
    from codepulse.widgets.launcher import LauncherApp
    launcher = LauncherApp()
    result = launcher.run()
    if result is None:
        raise typer.Exit(0)
    path, name, resume = result
    _launch(path, name, resume)


@app.command(name="open")
def cmd_open(
    path: str = typer.Argument(..., help="Path to project folder to open"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Override project name"),
) -> None:
    """Open an existing project folder."""
    p = Path(path)
    if not p.exists():
        typer.echo(f"Error: path does not exist: {path}", err=True)
        raise typer.Exit(1)
    project_name = name or _project_name_from_path(p)
    _launch(str(p), project_name, resume=False)


@app.command(name="new")
def cmd_new(
    name: str = typer.Argument(..., help="Project name"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Project path (default: current dir)"),
) -> None:
    """Start a new blank project session."""
    project_path = Path(path) if path else Path.cwd()
    if not project_path.exists():
        project_path.mkdir(parents=True)
    _launch(str(project_path), name, resume=False)


@app.command(name="resume")
def cmd_resume(
    project: str = typer.Argument(..., help="Project name to resume"),
) -> None:
    """Resume the latest session for a project."""
    from codepulse.session.manager import SessionManager
    session = SessionManager.load_latest(project)
    if session is None:
        typer.echo(f"No session found for project: {project}", err=True)
        raise typer.Exit(1)
    _launch(session.project_path, project, resume=True)


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
