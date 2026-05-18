# HTB CLI

HackTheBox from your terminal — with a hacker aesthetic.

```
    ██╗  ██╗████████╗██████╗      ██████╗██╗     ██╗
    ██║  ██║╚══██╔══╝██╔══██╗    ██╔════╝██║     ██║
    ███████║   ██║   ██████╔╝    ██║     ██║     ██║
    ██╔══██║   ██║   ██╔══██╗    ██║     ██║     ██║
    ██║  ██║   ██║   ██████╔╝    ╚██████╗███████╗██║
    ╚═╝  ╚═╝   ╚═╝   ╚═════╝      ╚═════╝╚══════╝╚═╝
```

## Install

```bash
pipx install .
# or
pip install -e .
```

## Get your API token

1. Log in at https://www.hackthebox.com
2. Click your avatar → **Profile** → **Settings** → **API Key**
3. Click **Create App Token** and copy the result

Then authenticate:

```bash
htb auth
```

Or set the `HTB_TOKEN` environment variable instead:

```bash
export HTB_TOKEN="your_token_here"
```

## Commands

| Command | Description |
|---------|-------------|
| `htb auth` | Store your API token |
| `htb search` | List all active machines |
| `htb search <query>` | Search machines by name |
| `htb search -d easy -o linux` | Filter by difficulty + OS |
| `htb search --retired -d hard` | Include retired machines |
| `htb info <name\|id>` | Show detailed machine info |
| `htb spawn <name\|id>` | Spawn a machine |
| `htb status` | Show currently active machine + IP |
| `htb stop` | Terminate active machine |
| `htb reset` | Reset active machine |
| `htb submit <flag>` | Submit a user/root flag |
| `htb profile` | Show your stats |

## Examples

```bash
# Search easy Linux machines
htb search -d easy -o linux

# Find a specific machine
htb search blue

# Spawn by name (shows info + confirms)
htb spawn blue

# Spawn by ID, no prompt
htb spawn 51 -y

# Check what's running
htb status

# Submit a flag
htb submit 3f3ef188c3694b3d5428b949b6a1d048
```

## Notes

- Spawning machines requires an **active VPN connection** or HTB Pwnbox.
- Spawning retired machines requires a **VIP subscription**.
- The machine catalog is cached locally for 6 hours. Run `htb refresh` to force an update.
