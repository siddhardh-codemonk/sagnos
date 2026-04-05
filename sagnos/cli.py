"""
sagnos/cli.py
The Sagnos CLI — sagnos generate, sagnos new, sagnos run
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app     = typer.Typer(
    help="🐍 Sagnos — The Spring Boot of Python for Flutter",
    add_completion=False,
)
console = Console()


# ─── sagnos version ──────────────────────────────────────────────────────────

@app.command()
def version():
    """Show Sagnos version."""
    from sagnos import __version__
    console.print(Panel(
        f"[bold yellow]🐍 Sagnos[/bold yellow] [green]v{__version__}[/green]\n"
        "[dim]The Spring Boot of Python for Flutter[/dim]",
        expand=False,
    ))


# ─── sagnos generate ─────────────────────────────────────────────────────────

@app.command()
def generate(
    output: str = typer.Option(
        "./lib/sagnos",
        "--output", "-o",
        help="Where to write the Dart files",
    ),
    url: str = typer.Option(
        "http://127.0.0.1:8000/sagnos/schema",
        "--url", "-u",
        help="Schema endpoint URL",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        help="Override base URL in generated Dart client",
    ),
):
    """
    Generate Dart bindings from your running Sagnos backend.

    Run your backend first, then:

        sagnos generate

    Or with custom output folder:

        sagnos generate --output ./my_flutter_app/lib/sagnos
    """
    from sagnos.codegen import generate as _generate

    console.print(f"\n[bold cyan]🐍 Sagnos Codegen[/bold cyan]")
    console.print(f"[dim]Fetching schema from {url}[/dim]\n")

    try:
        _generate(
            schema_url=url,
            output_dir=output,
            base_url=base_url,
        )
        console.print(f"\n[bold green]✅ Dart files written to {output}[/bold green]")
        console.print("[dim]Now run your Flutter app![/dim]\n")
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        console.print("[dim]Is your Sagnos backend running?[/dim]")
        raise typer.Exit(1)


# ─── sagnos new ──────────────────────────────────────────────────────────────

@app.command()
def new(
    name: str = typer.Argument(..., help="Project name"),
):
    """
    Scaffold a complete new Sagnos project.

        sagnos new my_app

    Creates:
        my_app/
        ├── backend.py
        ├── requirements.txt
        └── ui/   (Flutter project)
    """
    root = Path.cwd() / name

    if root.exists():
        console.print(f"[red]❌ Folder '{name}' already exists.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]🐍 Creating Sagnos project: {name}[/bold cyan]\n")

    # Create folders
    (root / "backend").mkdir(parents=True)

    # Write backend/main.py
    backend_code = f'''from sagnos import expose, model, SagnosApp
from typing import Optional


@model
class Item:
    id:    int
    title: str
    done:  bool


ITEMS = {{
    1: Item(id=1, title="Learn Sagnos", done=True),
    2: Item(id=2, title="Build something cool", done=False),
}}


@expose(method="GET")
async def list_items() -> list[Item]:
    """Get all items"""
    return list(ITEMS.values())


@expose(method="GET")
async def get_item(id: int) -> Item:
    """Get item by ID"""
    from sagnos import NotFoundError
    item = ITEMS.get(id)
    if not item:
        raise NotFoundError(f"Item {{id}} not found")
    return item


@expose
async def create_item(title: str) -> Item:
    """Create a new item"""
    new_id = max(ITEMS.keys()) + 1
    item   = Item(id=new_id, title=title, done=False)
    ITEMS[new_id] = item
    return item


@expose
async def toggle_item(id: int) -> Item:
    """Toggle item done status"""
    from sagnos import NotFoundError
    item = ITEMS.get(id)
    if not item:
        raise NotFoundError(f"Item {{id}} not found")
    ITEMS[id] = Item(id=item.id, title=item.title, done=not item.done)
    return ITEMS[id]


if __name__ == "__main__":
    app = SagnosApp(title="{name}")
    app.run()
'''

    (root / "backend" / "main.py").write_text(backend_code, encoding="utf-8")

    # Write requirements.txt
    (root / "requirements.txt").write_text(
        "sagnos\nfastapi\nuvicorn\npydantic\n",
        encoding="utf-8"
    )

    # Write .gitignore
    (root / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.venv/\ndist/\nbuild/\n"
        "ui/build/\nui/lib/sagnos/\n",
        encoding="utf-8"
    )

    console.print("[green]  ✅ backend/main.py[/green]")
    console.print("[green]  ✅ requirements.txt[/green]")
    console.print("[green]  ✅ .gitignore[/green]")

    # Create Flutter project
    console.print("\n[cyan]Creating Flutter project...[/cyan]")
    result = subprocess.run(
        ["flutter", "create", "ui"],
        cwd=str(root),
        capture_output=True,
        text=True,
        shell=True,
    )

    if result.returncode == 0:
        console.print("[green]  ✅ ui/ (Flutter project)[/green]")

        # Add http package
        subprocess.run(
            ["flutter", "pub", "add", "http"],
            cwd=str(root / "ui"),
            capture_output=True,
            shell=True,
        )
        console.print("[green]  ✅ http package added[/green]")

        # Create the sagnos output folder
        (root / "ui" / "lib" / "sagnos").mkdir(parents=True, exist_ok=True)

    else:
        console.print("[yellow]  ⚠️  Flutter not found — skipping UI creation[/yellow]")
        console.print("[dim]  Install Flutter and run: flutter create ui[/dim]")

    # Print next steps
    console.print(Panel(
        f"[bold green]✅ Project '{name}' created![/bold green]\n\n"
        f"[bold]Next steps:[/bold]\n\n"
        f"  [cyan]cd {name}[/cyan]\n"
        f"  [cyan]python backend/main.py or sagnos run[/cyan]       ← start backend\n\n"
        f"  In another terminal:\n"
        f"  [cyan]sagnos generate --output ./ui/lib/sagnos[/cyan]\n"
        f"  [cyan]cd ui && flutter run -d chrome[/cyan]",
        expand=False,
    ))


# ─── sagnos doctor ───────────────────────────────────────────────────────────

@app.command()
def doctor():
    """Check all dependencies Sagnos needs."""
    table = Table(title="🐍 Sagnos Doctor", show_header=True)
    table.add_column("Dependency", style="bold")
    table.add_column("Status")
    table.add_column("Notes")

    checks = []

    # Python version
    py  = sys.version_info
    ok  = py >= (3, 10)
    checks.append(("Python ≥ 3.10", ok, f"{py.major}.{py.minor}.{py.micro}"))

    # Flutter
    r = subprocess.run(["flutter", "--version"], capture_output=True, text=True)
    checks.append(("Flutter SDK", r.returncode == 0,
                   "https://flutter.dev" if r.returncode != 0 else "Found"))

    # Dart
    r = subprocess.run(["dart", "--version"], capture_output=True, text=True)
    checks.append(("Dart SDK", r.returncode == 0, "Comes with Flutter"))

    # FastAPI
    try:
        import fastapi
        checks.append(("FastAPI", True, fastapi.__version__))
    except ImportError:
        checks.append(("FastAPI", False, "pip install fastapi"))

    # Pydantic
    try:
        import pydantic
        checks.append(("Pydantic", True, pydantic.__version__))
    except ImportError:
        checks.append(("Pydantic", False, "pip install pydantic"))

    all_ok = True
    for name, ok, note in checks:
        status = "[green]✅ OK[/green]" if ok else "[red]❌ Missing[/red]"
        table.add_row(name, status, note)
        if not ok:
            all_ok = False

    console.print(table)

    if all_ok:
        console.print("\n[green]✅ Everything looks good![/green]")
        console.print("[dim]Run `sagnos new <name>` to start a project.[/dim]\n")
    else:
        console.print("\n[red]❌ Fix the issues above before continuing.[/red]\n")
        raise typer.Exit(1)


# ─── sagnos run ──────────────────────────────────────────────────────────────

@app.command()
def run(
    entry: str = typer.Option(
        "backend/main.py",
        "--entry", "-e",
        help="Python backend entry file",
    ),
    port: int = typer.Option(
        8000,
        "--port", "-p",
        help="Port to run backend on",
    ),
):
    """
    Start your Sagnos backend.

        sagnos run

    Or with custom entry file:

        sagnos run --entry backend/main.py --port 8000
    """
    entry_path = Path(entry)

    if not entry_path.exists():
        console.print(f"[red]❌ File not found: {entry}[/red]")
        console.print("[dim]Are you in the project root folder?[/dim]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]🐍 Starting Sagnos backend[/bold cyan]")
    console.print(f"[dim]Entry: {entry} | Port: {port}[/dim]\n")

    os.environ["SAGNOS_PORT"] = str(port)

    try:
        subprocess.run(
            [sys.executable, str(entry_path)],
            check=True,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]⏹  Sagnos stopped.[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]❌ Backend crashed: {e}[/red]")
        raise typer.Exit(1)


# ─── Entry ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()