from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

# ── theme ─────────────────────────────────────────────────────────────────────

DIFF_COLORS: dict[str, str] = {
    "easy": "bright_green",
    "medium": "yellow",
    "hard": "red1",
    "insane": "magenta",
}

OS_BADGE: dict[str, str] = {
    "linux":   "[bold green]LNX[/bold green]",
    "windows": "[bold blue]WIN[/bold blue]",
    "freebsd": "[bold cyan]BSD[/bold cyan]",
    "openbsd": "[bold cyan]OPB[/bold cyan]",
    "android": "[bold yellow]AND[/bold yellow]",
}

BANNER = """\
[bold green]
    ██╗  ██╗████████╗██████╗      ██████╗██╗     ██╗
    ██║  ██║╚══██╔══╝██╔══██╗    ██╔════╝██║     ██║
    ███████║   ██║   ██████╔╝    ██║     ██║     ██║
    ██╔══██║   ██║   ██╔══██╗    ██║     ██║     ██║
    ██║  ██║   ██║   ██████╔╝    ╚██████╗███████╗██║
    ╚═╝  ╚═╝   ╚═╝   ╚═════╝      ╚═════╝╚══════╝╚═╝[/bold green]
[dim green]              [ HackTheBox Command Line Interface v0.1.0 ][/dim green]
"""

# ── helpers ───────────────────────────────────────────────────────────────────


def banner() -> None:
    console.print(BANNER)


def _diff_color(d: str) -> str:
    return DIFF_COLORS.get(str(d).lower(), "white")


def _os_label(os_name: str) -> str:
    badge = OS_BADGE.get(os_name.lower(), "[dim]???[/dim]")
    return f"{badge} [cyan]{os_name}[/cyan]"


def _rating(m: dict) -> str:
    val = m.get("rating") or m.get("stars")
    try:
        return f"{float(val):.1f} ★"
    except (TypeError, ValueError):
        return "  —  "


def _state(m: dict) -> str:
    state = m.get("state", "")
    is_retired = bool(m.get("retired")) or "retired" in state
    if is_retired:
        is_free = "free" in state
        return "[dim]RETIRED[/dim]" + ("[bright_cyan] FREE[/bright_cyan]" if is_free else "")
    return "[bright_green]ACTIVE[/bright_green]"


def _owned_badge(m: dict) -> str:
    u = m.get("authUserInUserOwns") or m.get("auth_user_in_user_owns")
    r = m.get("authUserInRootOwns") or m.get("auth_user_in_root_owns")
    if u and r:
        return "[bold bright_green]U+R[/bold bright_green]"
    if u:
        return "[green]U[/green]"
    if r:
        return "[red]R[/red]"
    return ""


# ── tables / panels ───────────────────────────────────────────────────────────


def machines_table(machines: list[dict], title: str = "MACHINES") -> Table:
    t = Table(
        title=f"[bold bright_green]{title}[/bold bright_green]",
        box=box.DOUBLE_EDGE,
        border_style="green",
        header_style="bold green",
        title_style="bold bright_green",
        show_lines=True,
        expand=False,
        padding=(0, 1),
    )
    t.add_column("ID", style="dim green", no_wrap=True, width=6)
    t.add_column("NAME", style="bold white", min_width=16, no_wrap=True)
    t.add_column("OS", no_wrap=True, width=7)
    t.add_column("DIFF", width=9)
    t.add_column("RATING", width=7)
    t.add_column("STATE", width=12)
    t.add_column("PWN", width=4)

    for m in machines:
        diff = m.get("difficultyText", "?")
        os_name = m.get("os", "?")
        dc = _diff_color(str(diff))
        badge = OS_BADGE.get(os_name.lower(), "[dim]???[/dim]")

        t.add_row(
            str(m.get("id", "")),
            m.get("name", "?"),
            badge,
            f"[{dc}]{diff}[/{dc}]",
            _rating(m),
            _state(m),
            _owned_badge(m),
        )

    return t


def machine_panel(machine: dict) -> Panel:
    diff = machine.get("difficultyText", "?")
    dc = _diff_color(str(diff))
    os_name = machine.get("os", "?")
    release = (machine.get("release") or machine.get("releaseDate") or "N/A")[:10]
    state_str = _state(machine)

    rows = [
        f"[bold bright_green]ID:[/bold bright_green]           {machine.get('id', '?')}",
        f"[bold bright_green]Name:[/bold bright_green]         [bold white]{machine.get('name', '?')}[/bold white]",
        f"[bold bright_green]OS:[/bold bright_green]           {_os_label(os_name)}",
        f"[bold bright_green]Difficulty:[/bold bright_green]   [{dc}]{diff}[/{dc}]",
        f"[bold bright_green]Points:[/bold bright_green]       [yellow]{machine.get('points', '—')}[/yellow]",
        f"[bold bright_green]Rating:[/bold bright_green]       {_rating(machine)}",
        f"[bold bright_green]Release:[/bold bright_green]      {release}",
        f"[bold bright_green]State:[/bold bright_green]        {state_str}",
        f"[bold bright_green]User pwns:[/bold bright_green]    {machine.get('user_owns_count') or machine.get('userOwnsCount', '—')}",
        f"[bold bright_green]Root pwns:[/bold bright_green]    {machine.get('root_owns_count') or machine.get('rootOwnsCount', '—')}",
    ]

    if ip := machine.get("ip"):
        rows.insert(2, f"[bold bright_green]IP:[/bold bright_green]           [bold cyan]{ip}[/bold cyan]")

    owned = _owned_badge(machine)
    if owned:
        rows.append(f"[bold bright_green]Owned:[/bold bright_green]        {owned}")

    name = machine.get("name", "MACHINE").upper()
    return Panel(
        "\n".join(rows),
        title=f"[bold bright_green][ {name} ][/bold bright_green]",
        border_style="green",
        padding=(1, 2),
    )


def matrix_panel(matrix: dict, machine_name: str = "") -> Panel:
    """Render the skill matrix as colored bar chart."""
    agg = matrix.get("aggregate", {})
    if not agg:
        return Panel("[dim]No matrix data available.[/dim]", title="[bold bright_green][ SKILL MATRIX ][/bold bright_green]", border_style="green")

    LABELS = {
        "enum":   "Enumeration   ",
        "real":   "Real-life     ",
        "cve":    "CVE Exploit   ",
        "custom": "Custom Exploit",
        "ctf":    "CTF-like      ",
    }

    BAR_WIDTH = 20
    rows = []
    for key, label in LABELS.items():
        val = float(agg.get(key, 0))
        filled = round((val / 10) * BAR_WIDTH)
        empty = BAR_WIDTH - filled

        if val >= 7:
            bar_color = "red1"
        elif val >= 4:
            bar_color = "yellow"
        else:
            bar_color = "bright_green"

        bar = f"[{bar_color}]{'█' * filled}[/{bar_color}][dim]{'░' * empty}[/dim]"
        rows.append(f"  [bold bright_green]{label}[/bold bright_green]  {bar}  [yellow]{val:.1f}[/yellow]/10")

    title = f"[ SKILL MATRIX: {machine_name.upper()} ]" if machine_name else "[ SKILL MATRIX ]"
    return Panel(
        "\n".join(rows),
        title=f"[bold bright_green]{title}[/bold bright_green]",
        border_style="green",
        padding=(1, 1),
    )


def spawn_panel(ip: str, machine_name: str, expires: str = "") -> Panel:
    rows = [
        f"[bold bright_green]TARGET IP :[/bold bright_green]  [bold cyan]{ip}[/bold cyan]",
    ]
    if expires:
        rows.append(f"[bold bright_green]EXPIRES   :[/bold bright_green]  {expires}")
    rows += [
        "",
        f"[dim green]VPN      :[/dim green]  sudo openvpn ~/htb.ovpn",
        f"[dim green]Ping     :[/dim green]  ping {ip}",
        f"[dim green]Nmap     :[/dim green]  nmap -sC -sV -oA {machine_name.lower()} {ip}",
    ]

    return Panel(
        "\n".join(rows),
        title=f"[bold bright_green][ ✓ MACHINE SPAWNED: {machine_name.upper()} ][/bold bright_green]",
        border_style="bright_green",
        padding=(1, 2),
    )


def profile_panel(data: dict) -> Panel:
    sub = data.get("subscriptionType", "free") or "free"
    sub_color = "bright_green" if sub.lower() != "free" else "dim"

    rows = [
        f"[bold bright_green]Name     :[/bold bright_green]  [bold white]{data.get('name', '?')}[/bold white]",
        f"[bold bright_green]Rank     :[/bold bright_green]  [cyan]{data.get('rank', '?')}[/cyan]",
        f"[bold bright_green]Ranking  :[/bold bright_green]  #{data.get('ranking', '?')}",
        f"[bold bright_green]Points   :[/bold bright_green]  [yellow]{data.get('points', 0)}[/yellow]",
        f"[bold bright_green]User owns:[/bold bright_green]  {data.get('user_owns', 0)}",
        f"[bold bright_green]Root owns:[/bold bright_green]  {data.get('system_owns', 0)}",
        f"[bold bright_green]Country  :[/bold bright_green]  {data.get('country_name', '?')}",
        f"[bold bright_green]Plan     :[/bold bright_green]  [{sub_color}]{sub}[/{sub_color}]",
    ]

    name = (data.get("name") or "USER").upper()
    return Panel(
        "\n".join(rows),
        title=f"[bold bright_green][ PROFILE: {name} ][/bold bright_green]",
        border_style="green",
        padding=(1, 2),
    )


# ── print shortcuts ───────────────────────────────────────────────────────────


def error(msg: str) -> None:
    console.print(f"\n[bold red]  [!][/bold red] {msg}\n")


def success(msg: str) -> None:
    console.print(f"\n[bold bright_green]  [+][/bold bright_green] {msg}\n")


def info(msg: str) -> None:
    console.print(f"[dim green]  [*][/dim green] {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]  [!][/yellow] {msg}")
