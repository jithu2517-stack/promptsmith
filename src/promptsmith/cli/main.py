from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich import box

from promptsmith.core import Cache, Runner, Vault, VaultError
from promptsmith.models.types import Message, Prompt, Provider, Role, TestCase


console = Console()
pass_vault = click.make_pass_decorator(Vault)


@click.group()
@click.option(
    "--vault-dir",
    default=None,
    help="Path to vault directory",
    envvar="PROMPTSMITH_VAULT",
)
@click.pass_context
def main(ctx: click.Context, vault_dir: str | None) -> None:
    """PromptSmith — Prompt Engineering Toolkit

    Version control, test, cache, and compare AI prompts across providers.
    """
    ctx.ensure_object(dict)
    try:
        ctx.obj["vault"] = Vault(vault_dir)
    except Exception:
        ctx.obj["vault"] = Vault()


@main.command()
@click.option("--force", is_flag=True, help="Force reinitialize existing vault")
@click.pass_context
def init(ctx: click.Context, force: bool) -> None:
    """Initialize a new PromptSmith vault in the current directory."""
    vault: Vault = ctx.obj["vault"]
    try:
        vault.init(force=force)
        console.print(
            Panel.fit(
                f"[bold green]Vault initialized at[/bold green] {vault.root}\n\n"
                "Run [bold]promptsmith create <name>[/bold] to create your first prompt.",
                title="PromptSmith",
                border_style="green",
            )
        )
    except VaultError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("name")
@click.option("--description", "-d", default="", help="Prompt description")
@click.option("--tag", "-t", multiple=True, help="Tags for the prompt")
@click.option("--system", "-s", "system_prompt", default="", help="System message")
@click.option("--user", "-u", "user_prompt", default="", help="User message")
@click.option(
    "--stdin",
    "read_stdin",
    is_flag=True,
    help="Read prompt content from stdin",
)
@click.pass_context
def create(
    ctx: click.Context,
    name: str,
    description: str,
    tag: tuple[str, ...],
    system_prompt: str,
    user_prompt: str,
    read_stdin: bool,
) -> None:
    """Create a new prompt in the vault."""
    vault: Vault = ctx.obj["vault"]

    if read_stdin:
        user_prompt = sys.stdin.read().strip()

    messages = []
    if system_prompt:
        messages.append(Message(role=Role.SYSTEM, content=system_prompt))

    if user_prompt:
        messages.append(Message(role=Role.USER, content=user_prompt))

    if not messages:
        if not sys.stdin.isatty():
            content = sys.stdin.read().strip()
            if content:
                messages.append(Message(role=Role.USER, content=content))

    prompt = Prompt(
        name=name,
        messages=messages,
        description=description,
        tags=list(tag),
    )

    try:
        prompt = vault.save_prompt(prompt)
        console.print(
            f"[green]Created prompt[/green] [bold]{prompt.name}[/bold] "
            f"v{prompt.version} [dim]({prompt.hash})[/dim]"
        )
    except VaultError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("name", required=False)
@click.option("--version", "-v", "ver", type=int, help="Show specific version")
@click.pass_context
def show(ctx: click.Context, name: str | None, ver: int | None) -> None:
    """Show prompt details or list all prompts."""
    vault: Vault = ctx.obj["vault"]

    if name is None:
        prompts = vault.list_prompts()
        if not prompts:
            console.print("[dim]No prompts in vault. Create one with [bold]promptsmith create[/bold][/dim]")
            return

        table = Table(title="PromptSmith Vault", box=box.ROUNDED)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Version", justify="right")
        table.add_column("Hash", style="dim")
        table.add_column("Description")
        table.add_column("Tags", style="yellow")

        for p in prompts:
            table.add_row(
                p["name"],
                f"v{p['latest_version']} ({p['total_versions']} total)",
                p["hash"],
                p["description"][:60],
                ", ".join(p["tags"]),
            )
        console.print(table)
        return

    try:
        prompt = vault.get_prompt(name, ver)
    except VaultError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if not prompt:
        console.print(f"[red]Prompt '{name}' not found.[/red]")
        sys.exit(1)

    info = Table(box=box.SIMPLE, show_header=False)
    info.add_column(style="bold cyan")
    info.add_column()
    info.add_row("Name", prompt.name)
    info.add_row("Version", str(prompt.version))
    info.add_row("Hash", prompt.hash)
    info.add_row("Description", prompt.description or "-")
    info.add_row("Tags", ", ".join(prompt.tags) if prompt.tags else "-")

    console.print(Panel(info, title=f"Prompt: {prompt.name}", border_style="cyan"))

    for i, msg in enumerate(prompt.messages):
        role_color = {"system": "red", "user": "green", "assistant": "blue"}.get(
            msg.role.value, "white"
        )
        console.print(
            Panel(
                msg.content,
                title=f"[{role_color}]{msg.role.value.upper()}[/{role_color}]",
                border_style=role_color,
                title_align="left",
            )
        )


@main.command()
@click.argument("name")
@click.option("--version", "-v", "ver", type=int, help="Edit specific version")
@click.pass_context
def edit(ctx: click.Context, name: str, ver: int | None) -> None:
    """Edit a prompt interactively (opens $EDITOR)."""
    import subprocess
    import tempfile

    vault: Vault = ctx.obj["vault"]
    prompt = vault.get_prompt(name, ver)
    if not prompt:
        console.print(f"[red]Prompt '{name}' not found.[/red]")
        sys.exit(1)

    editor = sys.executable.split("/")[-1].replace("python", "")
    editor = (
        subprocess.run(["which", "nano"], capture_output=True).stdout.decode().strip()
        or subprocess.run(["which", "vim"], capture_output=True).stdout.decode().strip()
        or subprocess.run(["which", "vi"], capture_output=True).stdout.decode().strip()
        or "nano"
    )

    tmpl = f"# PromptSmith: {name} v{prompt.version}\n"
    tmpl += f"# Description: {prompt.description}\n"
    tmpl += f"# Tags: {', '.join(prompt.tags)}\n"
    tmpl += "# Lines starting with # are metadata; message blocks follow.\n"
    tmpl += "---\n"
    for msg in prompt.messages:
        tmpl += f"[{msg.role.value.upper()}]\n{msg.content}\n---\n"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as tf:
        tf.write(tmpl)
        tmp_path = tf.name

    subprocess.run([editor, tmp_path])

    with open(tmp_path) as f:
        raw = f.read()

    messages = []
    current_role = None
    current_content = []

    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("---"):
            if current_role:
                messages.append(
                    Message(
                        role=Role(current_role.lower()),
                        content="\n".join(current_content).strip(),
                    )
                )
                current_content = []
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            if current_role:
                messages.append(
                    Message(
                        role=Role(current_role.lower()),
                        content="\n".join(current_content).strip(),
                    )
                )
                current_content = []
            current_role = stripped[1:-1]
            continue
        if current_role:
            current_content.append(line)

    if current_role and current_content:
        messages.append(
            Message(
                role=Role(current_role.lower()),
                content="\n".join(current_content).strip(),
            )
        )

    if not messages:
        console.print("[red]No valid messages found in edited file.[/red]")
        sys.exit(1)

    new_prompt = Prompt(
        name=name,
        messages=messages,
        description=prompt.description,
        tags=prompt.tags,
    )

    try:
        new_prompt = vault.save_prompt(new_prompt)
        console.print(
            f"[green]Saved[/green] [bold]{new_prompt.name}[/bold] "
            f"v{new_prompt.version} [dim]({new_prompt.hash})[/dim]"
        )
    except VaultError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("name")
@click.option("--provider", "-p", default="mock", help="AI provider (openai, anthropic, mock)")
@click.option("--model", "-m", default=None, help="Model name")
@click.option("--no-cache", is_flag=True, help="Skip cache")
@click.option("--var", "-v", "variables", multiple=True, help="Template variables (key=value)")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON")
@click.pass_context
def run(
    ctx: click.Context,
    name: str,
    provider: str,
    model: str | None,
    no_cache: bool,
    variables: tuple[str, ...],
    output_json: bool,
) -> None:
    """Run a prompt against an AI provider."""
    vault: Vault = ctx.obj["vault"]
    prompt = vault.get_prompt(name)
    if not prompt:
        console.print(f"[red]Prompt '{name}' not found.[/red]")
        sys.exit(1)

    vars_dict = {}
    for v in variables:
        if "=" in v:
            k, val = v.split("=", 1)
            vars_dict[k] = val

    runner = Runner(vault)
    result = asyncio.run(
        runner.run_prompt(
            prompt,
            provider=Provider(provider) if provider in ("openai", "anthropic", "mock") else provider,
            model=model,
            no_cache=no_cache,
            variables=vars_dict if vars_dict else None,
        )
    )

    if output_json:
        console.print(json.dumps(result.to_dict(), indent=2, default=str))
        return

    if result.error:
        console.print(f"[red]Error:[/red] {result.error}")
        return

    console.print(
        Panel(
            result.response_text,
            title=f"Response — {result.provider.value}/{result.model}",
            border_style="bright_cyan",
        )
    )

    stats = Table(show_header=False, box=box.SIMPLE)
    stats.add_column(style="dim")
    stats.add_column()
    stats.add_row("Provider", f"[cyan]{result.provider.value}[/cyan]")
    stats.add_row("Model", result.model)
    stats.add_row("Tokens", f"{result.tokens_input} in / {result.tokens_output} out")
    stats.add_row("Latency", f"{result.latency_ms:.0f}ms")
    stats.add_row("Cost", f"${result.cost_usd:.6f}")
    if result.cached:
        stats.add_row("Source", "[green]CACHE[/green]")
    console.print(stats)


@main.command()
@click.argument("name")
@click.option("--provider", "-p", default="mock", help="AI provider")
@click.option("--model", "-m", default=None, help="Model name")
@click.option("--no-cache", is_flag=True, help="Skip cache")
@click.option("--filter", "-f", "test_filter", default=None, help="Filter tests by name")
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
@click.pass_context
def test(
    ctx: click.Context,
    name: str,
    provider: str,
    model: str | None,
    no_cache: bool,
    test_filter: str | None,
    output_json: bool,
) -> None:
    """Run test suite for a prompt."""
    vault: Vault = ctx.obj["vault"]
    if not vault.get_prompt(name):
        console.print(f"[red]Prompt '{name}' not found.[/red]")
        sys.exit(1)

    runner = Runner(vault)
    results = asyncio.run(
        runner.run_test_suite(
            name,
            provider=provider,
            model=model,
            no_cache=no_cache,
            test_filter=test_filter,
        )
    )

    if output_json:
        console.print(json.dumps([r.to_dict() for r in results], indent=2, default=str))
        return

    if not results:
        console.print("[dim]No tests defined. Create tests with [bold]promptsmith test-add[/bold][/dim]")
        return

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    table = Table(title=f"Test Results — {name}", box=box.ROUNDED)
    table.add_column("Test", style="cyan")
    table.add_column("Result")
    table.add_column("Duration")
    table.add_column("Details")

    for r in results:
        status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        duration = f"{r.duration_ms:.0f}ms" if r.duration_ms else "-"
        details = ""
        if not r.passed:
            details = r.error or "; ".join(
                c.get("message", "") for c in r.checks if not c.get("passed", True)
            )
        table.add_row(r.test_name, status, duration, details[:80])

    console.print(table)

    summary = Text()
    summary.append(f"\n{passed} passed", style="green")
    if failed:
        summary.append(f", {failed} failed", style="red")
    summary.append(f" ({len(results)} total)")
    console.print(summary)


@main.command(name="test-add")
@click.argument("name")
@click.option("--description", "-d", default="", help="Test description")
@click.option("--var", "-v", "variables", multiple=True, help="Template variables (key=value)")
@click.option("--expect", "-e", "expected", multiple=True, help="Regex patterns that must match")
@click.option("--forbid", "-f", "forbidden", multiple=True, help="Regex patterns that must not match")
@click.option("--min-tokens", type=int, default=0, help="Minimum output tokens")
@click.option("--max-tokens", type=int, default=0, help="Maximum output tokens")
@click.pass_context
def test_add(
    ctx: click.Context,
    name: str,
    description: str,
    variables: tuple[str, ...],
    expected: tuple[str, ...],
    forbidden: tuple[str, ...],
    min_tokens: int,
    max_tokens: int,
) -> None:
    """Add a test case for prompt evaluation."""
    vault: Vault = ctx.obj["vault"]

    vars_dict = {}
    for v in variables:
        if "=" in v:
            k, val = v.split("=", 1)
            vars_dict[k] = val

    test_case = TestCase(
        name=name,
        description=description,
        input_variables=vars_dict,
        expected_patterns=list(expected),
        forbidden_patterns=list(forbidden),
        min_tokens=min_tokens,
        max_tokens=max_tokens,
    )

    vault.save_test(test_case)
    console.print(f"[green]Test case[/green] [bold]{name}[/bold] [green]created.[/green]")


@main.command(name="test-list")
@click.pass_context
def test_list(ctx: click.Context) -> None:
    """List all test cases."""
    vault: Vault = ctx.obj["vault"]
    tests = vault.list_tests()
    if not tests:
        console.print("[dim]No tests defined.[/dim]")
        return

    table = Table(title="Test Cases")
    table.add_column("Name", style="cyan")
    for t in tests:
        tc = vault.get_test(t)
        desc = tc.description[:60] if tc and tc.description else ""
        table.add_row(t) if not desc else table.add_row(f"{t} — {desc}")
    console.print(table)


@main.command()
@click.argument("name")
@click.option("--versions", "-v", "vers", type=(int, int), help="Compare two versions (e.g., -v 1 3)")
@click.option("--other", "-o", "other_name", help="Compare with another prompt")
@click.pass_context
def diff(
    ctx: click.Context,
    name: str,
    vers: tuple[int, int] | None,
    other_name: str | None,
) -> None:
    """Compare prompt versions or two different prompts."""
    vault: Vault = ctx.obj["vault"]

    if vers:
        try:
            result = vault.diff_prompts(name, vers[0], vers[1])
        except VaultError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)

        console.print(
            f"[bold]Diff:[/bold] {name} v{vers[0]} → v{vers[1]} "
            f"[dim]({result['hash_old']} → {result['hash_new']})[/dim]\n"
        )

        for d in result["diffs"]:
            if d["type"] == "added":
                console.print(f"  [green]+ Added[/green] at index {d['index']}:")
                console.print(f"    {d['content'][:200]}")
            elif d["type"] == "removed":
                console.print(f"  [red]- Removed[/red] at index {d['index']}:")
                console.print(f"    {d['content'][:200]}")
            elif d["type"] == "changed":
                console.print(f"  [yellow]~ Changed[/yellow] at index {d['index']}:")
                console.print(f"    [dim]Old ({d['old_role']}):[/dim] {d['old_content'][:150]}")
                console.print(f"    [dim]New ({d['new_role']}):[/dim] {d['new_content'][:150]}")

        if not result["diffs"]:
            console.print("[dim]No differences found.[/dim]")
        return

    if other_name:
        p1 = vault.get_prompt(name)
        p2 = vault.get_prompt(other_name)
        if not p1 or not p2:
            console.print("[red]Prompt not found.[/red]")
            sys.exit(1)

        console.print(f"[bold]Comparing:[/bold] {name} vs {other_name}\n")
        for i, (m1, m2) in enumerate(
            zip(p1.messages, p2.messages)
        ):
            if m1.content != m2.content:
                console.print(f"[yellow]Message {i} differs:[/yellow]")
                console.print(f"  {name}: {m1.content[:150]}")
                console.print(f"  {other_name}: {m2.content[:150]}")
        return

    console.print("[yellow]Specify --versions or --other to compare.[/yellow]")


@main.command()
@click.argument("name")
@click.option("--provider", "-p", multiple=True, default=["mock"], help="Providers to benchmark")
@click.option("--model", "-m", multiple=True, help="Models to benchmark")
@click.option("--runs", "-n", type=int, default=3, help="Number of runs per provider")
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
@click.pass_context
def benchmark(
    ctx: click.Context,
    name: str,
    provider: tuple[str, ...],
    model: tuple[str, ...],
    runs: int,
    output_json: bool,
) -> None:
    """Benchmark a prompt across providers."""
    vault: Vault = ctx.obj["vault"]
    if not vault.get_prompt(name):
        console.print(f"[red]Prompt '{name}' not found.[/red]")
        sys.exit(1)

    if not model:
        model = ("mock",)

    providers_list = [
        (Provider(p) if p in ("openai", "anthropic", "mock") else p, m)
        for p in provider
        for m in model
    ]

    runner = Runner(vault)
    results = asyncio.run(
        runner.benchmark_prompt(name, providers_list, runs=runs)
    )

    if output_json:
        console.print(json.dumps([r.to_dict() for r in results], indent=2, default=str))
        return

    table = Table(title=f"Benchmark — {name} ({runs} runs)", box=box.ROUNDED)
    table.add_column("Provider", style="cyan")
    table.add_column("Model")
    table.add_column("Avg Latency", justify="right")
    table.add_column("Avg Tokens In", justify="right")
    table.add_column("Avg Tokens Out", justify="right")
    table.add_column("Avg Cost", justify="right")

    grouped: dict[tuple[str, str], list[Any]] = {}
    for r in results:
        key = (str(r.provider.value), r.model)
        grouped.setdefault(key, []).append(r)

    for (prov, mod), res_list in grouped.items():
        avg_lat = sum(r.latency_ms for r in res_list) / len(res_list)
        avg_in = sum(r.tokens_input for r in res_list) / len(res_list)
        avg_out = sum(r.tokens_output for r in res_list) / len(res_list)
        avg_cost = sum(r.cost_usd for r in res_list) / len(res_list)
        table.add_row(
            prov,
            mod,
            f"{avg_lat:.0f}ms",
            f"{avg_in:.0f}",
            f"{avg_out:.0f}",
            f"${avg_cost:.6f}",
        )

    console.print(table)


@main.command()
@click.argument("name")
@click.option("--output", "-o", default=None, help="Output file path")
@click.option("--version", "-v", "ver", type=int, help="Version to export")
@click.pass_context
def export(
    ctx: click.Context,
    name: str,
    output: str | None,
    ver: int | None,
) -> None:
    """Export a prompt to a portable YAML file."""
    vault: Vault = ctx.obj["vault"]
    if output is None:
        output = f"{name}.promptsmith.yaml"
    try:
        path = vault.export_prompt(name, output, ver)
        console.print(f"[green]Exported to[/green] {path}")
    except VaultError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("file_path")
@click.pass_context
def import_prompt(ctx: click.Context, file_path: str) -> None:
    """Import a prompt from a YAML file."""
    vault: Vault = ctx.obj["vault"]
    try:
        prompt = vault.import_prompt(file_path)
        console.print(
            f"[green]Imported[/green] [bold]{prompt.name}[/bold] "
            f"v{prompt.version} [dim]({prompt.hash})[/dim]"
        )
    except VaultError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete(ctx: click.Context, name: str, yes: bool) -> None:
    """Delete a prompt and all its versions."""
    vault: Vault = ctx.obj["vault"]
    if not yes:
        confirmed = click.confirm(
            f"Delete prompt '{name}' and all its versions? This cannot be undone."
        )
        if not confirmed:
            return
    try:
        vault.delete_prompt(name)
        console.print(f"[green]Deleted[/green] [bold]{name}[/bold]")
    except VaultError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.group()
def cache() -> None:
    """Manage the response cache."""


@cache.command("stats")
def cache_stats() -> None:
    """Show cache statistics."""
    c = Cache()
    stats = c.stats()
    table = Table(title="Cache Statistics", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value")
    table.add_row("Entries", str(stats["total_entries"]))
    table.add_row("Cost saved", f"${stats['cost_saved_usd']:.6f}")
    table.add_row("Total accesses", str(stats["total_accesses"]))
    table.add_row("DB size", f"{stats['db_size_bytes']:,} bytes")
    console.print(table)


@cache.command("clear")
@click.option("--prompt", "-p", default=None, help="Clear cache for specific prompt hash")
def cache_clear(prompt: str | None) -> None:
    """Clear the cache."""
    c = Cache()
    count = c.invalidate(prompt)
    console.print(f"[green]Cleared {count} cache entries.[/green]")


@cache.command("prune")
@click.option("--days", "-d", type=int, default=30, help="Max age in days")
def cache_prune(days: int) -> None:
    """Prune old cache entries."""
    c = Cache()
    count = c.prune(days)
    console.print(f"[green]Pruned {count} entries older than {days} days.[/green]")


@main.group()
def config() -> None:
    """Manage vault configuration."""


@config.command("get")
@click.argument("key")
@click.pass_context
def config_get(ctx: click.Context, key: str) -> None:
    """Get a config value."""
    vault: Vault = ctx.obj["vault"]
    cfg = vault.get_config()
    console.print(f"{key} = {cfg.get(key, '[dim]not set[/dim]')}")


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set a config value."""
    vault: Vault = ctx.obj["vault"]
    vault.set_config(key, value)
    console.print(f"[green]Set {key} = {value}[/green]")


if __name__ == "__main__":
    main()
