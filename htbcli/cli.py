import sys
import getpass
import click
from rich.prompt import Confirm

from .api import HTBClient, HTBError, HTBAuthError
from .config import load_token, save_token, clear_token, clear_machines_cache
from . import display

# ── helpers ───────────────────────────────────────────────────────────────────


def _client() -> HTBClient:
    token = load_token()
    if not token:
        display.error("No API token found. Run [bold]htb auth[/bold] first.")
        sys.exit(1)
    return HTBClient(token)


def _is_retired(m: dict) -> bool:
    return bool(m.get("retired")) or "retired" in str(m.get("state", ""))


def _resolve_machine(client: HTBClient, target: str) -> dict | None:
    """Return a machine dict given a name or numeric ID string."""
    if target.isdigit():
        return client.get_machine_profile(int(target))
    machines = client.get_machines(term=target)
    exact = next((m for m in machines if m.get("name", "").lower() == target.lower()), None)
    return exact or (machines[0] if machines else None)


# ── cli group ─────────────────────────────────────────────────────────────────


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def main(ctx: click.Context) -> None:
    """HTB CLI — HackTheBox from your terminal."""
    display.banner()
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── auth ──────────────────────────────────────────────────────────────────────


@main.command()
@click.option("--clear", is_flag=True, help="Remove stored token.")
@click.option("--token", "-t", default="", help="Pass token directly (skips the prompt).")
def auth(clear: bool, token: str) -> None:
    """Set up or clear your HTB API token.

    \b
    Examples:
      htb auth                          # interactive prompt
      htb auth --token eyJ0eXAi...      # pass token directly
      htb auth --clear                  # remove saved token
    """
    if clear:
        clear_token()
        display.success("Token cleared.")
        return

    if not token:
        display.console.print(
            "\n[bold green]HOW TO GET YOUR API TOKEN[/bold green]\n"
            "  [dim]1.[/dim]  Log in at [cyan]https://app.hackthebox.com[/cyan]\n"
            "  [dim]2.[/dim]  Click your avatar [bold]→ Profile → Settings → API Key[/bold]\n"
            "  [dim]3.[/dim]  Click [bold]Create App Token[/bold] and copy the result\n"
            "  [dim]4.[/dim]  Paste it below (input is hidden, just paste + Enter)\n"
        )
        try:
            token = getpass.getpass("  [>] App Token: ")
        except (KeyboardInterrupt, EOFError):
            display.console.print()
            display.info("Cancelled.")
            return

    token = token.strip()
    if not token:
        display.error("Token cannot be empty.")
        return

    client = HTBClient(token)
    with display.console.status("[green]  [*] Verifying token...[/green]", spinner="dots"):
        try:
            profile = client.get_profile()
        except HTBAuthError:
            display.error("Token rejected by HTB. Double-check it and try again.")
            return
        except HTBError as e:
            display.error(str(e))
            return

    save_token(token)
    name = profile.get("name", "hacker")
    display.success(f"Authenticated as [bold cyan]{name}[/bold cyan]. Token saved to ~/.config/htbcli/config.json")


# ── search ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("query", required=False, default="")
@click.option("--difficulty", "-d",
              type=click.Choice(["easy", "medium", "hard", "insane"], case_sensitive=False),
              help="Filter by difficulty.")
@click.option("--os", "-o",
              type=click.Choice(["linux", "windows", "freebsd", "openbsd", "android"], case_sensitive=False),
              help="Filter by operating system.")
@click.option("--retired", "-r", is_flag=True, help="Include retired machines.")
@click.option("--limit", "-l", default=25, show_default=True, help="Results per page.")
@click.option("--page", "-p", default=1, show_default=True, help="Page number.")
@click.option("--refresh", is_flag=True, help="Force-refresh the local machine cache.")
def search(query: str, difficulty: str, os: str, retired: bool, limit: int, page: int, refresh: bool) -> None:
    """Search and filter machines.

    \b
    Examples:
      htb search
      htb search lame
      htb search -d easy -o linux
      htb search -d easy -o linux -p 2
      htb search --retired -d hard
    """
    client = _client()

    status_msg = "[bold green]  [*] Refreshing machine cache...[/bold green]" if refresh else "[bold green]  [*] Fetching machines...[/bold green]"
    with display.console.status(status_msg, spinner="dots"):
        try:
            machines = client.get_machines(term=query, force_refresh=refresh)
        except HTBError as e:
            display.error(str(e))
            return

    # Only hide retired machines when listing without a name query.
    # If the user searched by name, show results regardless of status.
    if not retired and not query:
        machines = [m for m in machines if not _is_retired(m)]

    if difficulty:
        machines = [m for m in machines
                    if (m.get("difficultyText") or "").lower() == difficulty.lower()]

    if os:
        machines = [m for m in machines
                    if (m.get("os") or "").lower() == os.lower()]

    total = len(machines)
    if not total:
        display.warn("No machines found matching your filters.")
        return

    total_pages = max(1, (total + limit - 1) // limit)
    page = max(1, min(page, total_pages))
    start = (page - 1) * limit
    machines = machines[start : start + limit]

    label = f"RESULTS [{total}]  page {page}/{total_pages}"
    if query:
        label += f" — \"{query}\""

    display.console.print(display.machines_table(machines, title=label))
    if total_pages > 1:
        display.info(f"Page {page}/{total_pages} — use [bold]-p {page + 1}[/bold] for next" if page < total_pages else f"Page {page}/{total_pages} — last page")
    else:
        display.info(f"Run [bold]htb info <name>[/bold] or [bold]htb spawn <name>[/bold] to continue.")


# ── spawn ─────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("target")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def spawn(target: str, yes: bool) -> None:
    """Spawn a machine by name or ID.

    \b
    Examples:
      htb spawn lame
      htb spawn 1
      htb spawn "Lame" -y
    """
    client = _client()

    machine_id: int
    machine_name: str

    if target.isdigit():
        machine_id = int(target)
        # Fetch profile for display
        with display.console.status("[bold green]  [*] Loading machine...[/bold green]", spinner="dots"):
            try:
                machine = client.get_machine_profile(machine_id)
                matrix = client.get_machine_matrix(machine_id)
            except HTBError as e:
                display.error(str(e))
                return
        machine_name = machine.get("name", target)
        display.console.print(display.machine_panel(machine))
        display.console.print(display.matrix_panel(matrix, machine_name))
    else:
        with display.console.status(
            f"[bold green]  [*] Searching for '{target}'...[/bold green]", spinner="dots"
        ):
            try:
                machine = _resolve_machine(client, target)
                if machine:
                    matrix = client.get_machine_matrix(machine["id"])
                else:
                    matrix = {}
            except HTBError as e:
                display.error(str(e))
                return

        if not machine:
            display.error(f"Machine '{target}' not found. Try [bold]htb search {target}[/bold].")
            return

        machine_id = machine["id"]
        machine_name = machine.get("name", target)
        display.console.print(display.machine_panel(machine))
        display.console.print(display.matrix_panel(matrix, machine_name))

    if not yes:
        if not Confirm.ask(
            f"\n[bold bright_green]  [>] Spawn [cyan]{machine_name}[/cyan]?[/bold bright_green]"
        ):
            display.info("Aborted.")
            return

    with display.console.status(
        f"[bold green]  [*] Spawning [cyan]{machine_name}[/cyan]...[/bold green]", spinner="aesthetic"
    ):
        try:
            resp = client.spawn(machine_id)
        except HTBError as e:
            display.error(str(e))
            return

    data = resp.get("data") or resp
    ip = data.get("ip") or data.get("target_ip")
    expires = data.get("expires_at", "")

    if ip:
        display.console.print(display.spawn_panel(ip, machine_name, expires))
    else:
        display.success(
            f"[cyan]{machine_name}[/cyan] is spawning. "
            "Run [bold]htb status[/bold] once the IP is assigned."
        )
        if msg := resp.get("message"):
            display.info(msg)


# ── status ────────────────────────────────────────────────────────────────────


@main.command()
def status() -> None:
    """Show the currently active/spawned machine."""
    client = _client()

    with display.console.status("[bold green]  [*] Checking active machine...[/bold green]", spinner="dots"):
        try:
            active = client.get_active_machine()
        except HTBError as e:
            display.error(str(e))
            return

    if not active:
        display.warn("No machine is currently running.")
        display.info("Use [bold]htb spawn <name>[/bold] to start one.")
        return

    display.console.print(display.machine_panel(active))


# ── stop ──────────────────────────────────────────────────────────────────────


@main.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def stop(yes: bool) -> None:
    """Terminate the currently running machine."""
    client = _client()

    with display.console.status("[bold green]  [*] Checking active machine...[/bold green]", spinner="dots"):
        try:
            active = client.get_active_machine()
        except HTBError as e:
            display.error(str(e))
            return

    if not active:
        display.warn("No machine is currently running.")
        return

    machine_name = active.get("name", "?")
    display.console.print(display.machine_panel(active))

    if not yes and not Confirm.ask(
        f"\n[bold red]  [!] Terminate [cyan]{machine_name}[/cyan]?[/bold red]"
    ):
        display.info("Aborted.")
        return

    with display.console.status("[bold red]  [*] Terminating...[/bold red]", spinner="dots"):
        try:
            client.terminate(active["id"])
        except HTBError as e:
            display.error(str(e))
            return

    display.success(f"Machine [cyan]{machine_name}[/cyan] terminated.")


# ── reset ─────────────────────────────────────────────────────────────────────


@main.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def reset(yes: bool) -> None:
    """Reset the currently running machine."""
    client = _client()

    with display.console.status("[bold green]  [*] Checking active machine...[/bold green]", spinner="dots"):
        try:
            active = client.get_active_machine()
        except HTBError as e:
            display.error(str(e))
            return

    if not active:
        display.warn("No machine is currently running.")
        return

    machine_name = active.get("name", "?")

    if not yes and not Confirm.ask(
        f"\n[bold yellow]  [!] Reset [cyan]{machine_name}[/cyan]?[/bold yellow]"
    ):
        display.info("Aborted.")
        return

    with display.console.status("[bold yellow]  [*] Resetting...[/bold yellow]", spinner="dots"):
        try:
            client.reset(active["id"])
        except HTBError as e:
            display.error(str(e))
            return

    display.success(f"Machine [cyan]{machine_name}[/cyan] reset. Give it ~1 minute to come back up.")


# ── info ──────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("target")
def info(target: str) -> None:
    """Show detailed info + skill matrix for a machine.

    \b
    Examples:
      htb info lame
      htb info 1
    """
    client = _client()

    with display.console.status(
        f"[bold green]  [*] Loading '{target}'...[/bold green]", spinner="dots"
    ):
        try:
            machine = _resolve_machine(client, target)
            if machine:
                matrix = client.get_machine_matrix(machine["id"])
            else:
                matrix = {}
        except HTBError as e:
            display.error(str(e))
            return

    if not machine:
        display.error(f"Machine '{target}' not found.")
        return

    display.console.print(display.machine_panel(machine))
    display.console.print(display.matrix_panel(matrix, machine.get("name", "")))


# ── submit ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("flag")
@click.option("--difficulty", "-d", default=50, show_default=True,
              type=click.IntRange(0, 100),
              help="Rate difficulty 0 (Easy) to 100 (Insane).")
def submit(flag: str, difficulty: int) -> None:
    """Submit a user or root flag.

    \b
    Example:
      htb submit 3f3ef188c3694b3d5428b949b6a1d048
    """
    client = _client()

    with display.console.status("[bold green]  [*] Checking active machine...[/bold green]", spinner="dots"):
        try:
            active = client.get_active_machine()
        except HTBError as e:
            display.error(str(e))
            return

    if not active:
        display.error("No active machine. Spawn one first with [bold]htb spawn <name>[/bold].")
        return

    machine_name = active.get("name", "?")
    machine_id = active["id"]

    with display.console.status(
        f"[bold green]  [*] Submitting flag for [cyan]{machine_name}[/cyan]...[/bold green]",
        spinner="dots",
    ):
        try:
            resp = client.submit_flag(machine_id, flag, difficulty)
        except HTBError as e:
            display.error(str(e))
            return

    success_val = resp.get("success") or resp.get("message", "")
    if success_val and success_val != "0":
        display.success(f"[bold]Flag accepted![/bold] Machine [cyan]{machine_name}[/cyan] owned.")
    else:
        display.error(f"Incorrect flag. Message: {resp.get('message', 'no details')}")


# ── profile ───────────────────────────────────────────────────────────────────


@main.command()
def refresh() -> None:
    """Re-download the full machine list and update the local cache."""
    client = _client()
    with display.console.status("[bold green]  [*] Fetching all machines...[/bold green]", spinner="dots"):
        try:
            machines = client.get_machines(force_refresh=True)
        except HTBError as e:
            display.error(str(e))
            return
    display.success(f"Cache updated — {len(machines)} machines stored locally.")


@main.command()
def profile() -> None:
    """Show your HTB profile and stats."""
    client = _client()

    with display.console.status("[bold green]  [*] Loading profile...[/bold green]", spinner="dots"):
        try:
            data = client.get_profile()
        except HTBError as e:
            display.error(str(e))
            return

    display.console.print(display.profile_panel(data))
