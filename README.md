# PyLocalSend CLI

A lightweight Python command-line tool for sharing files over a local network, inspired by [LocalSend](https://localsend.org).

## Features

- **Interactive Shell** — Persistent `(pylocalsend)` prompt for managing transfers without restarting
- **Auto Discovery** — Automatically find other devices on the LAN via mDNS (Zeroconf)
- **File Transfer** — Push files to or pull files from remote devices
- **Text Messaging** — Send instant text messages to LAN devices
- **Transfer Progress** — Real-time progress bar with speed display for large file transfers
- **Smart Networking** — Automatically filters out VPN/Docker/TUN virtual interfaces and selects the real LAN IP; bypasses system proxy
- **Cross-Platform** — Works on macOS, Ubuntu, and other Linux distributions

## Project Structure

```
pylocalsend/
  __init__.py          # Package version
  cli.py               # Main program
pyproject.toml         # Package metadata and build config
requirements.txt       # Dependencies (for development)
LICENSE                # MIT License
README.md              # This file
```

## Installation

Requires **Python 3.7+**.

### From PyPI

```bash
pip install pylocalsend
```

With all optional dependencies:

```bash
pip install pylocalsend[all]
```

### From Source

```bash
git clone https://github.com/guolei/pylocalsend.git
cd pylocalsend
pip install .
```

Or install in development mode:

```bash
pip install -e .
```

### Dependencies

| Package | Required | Purpose |
|---------|----------|---------|
| `requests` | Yes | HTTP client for file transfer and messaging |
| `zeroconf` | Optional | mDNS device discovery (scan command); without it, you can still use IP addresses directly |
| `netifaces` | Optional | Accurate network interface enumeration and virtual adapter filtering; falls back to socket-based detection if not installed |

Optional dependency groups:

```bash
pip install pylocalsend[discovery]    # + zeroconf
pip install pylocalsend[network]      # + netifaces
pip install pylocalsend[all]          # + zeroconf + netifaces
```

## Usage

### Starting

After installation, run on two machines within the same local network:

```bash
pylocalsend
```

Or run directly without installation:

```bash
python3 -m pylocalsend.cli
```

Optional arguments:

```bash
pylocalsend --dir ./shared_files --port 53317
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--dir` | `.` (current directory) | Directory for sharing and receiving files |
| `--port` | `53317` | Port to listen on |

### Commands

Once inside the `(pylocalsend)` prompt:

| Command | Description | Example |
|---------|-------------|---------|
| `scan` | Discover devices on the local network | `scan` |
| `list` | List shared files on a remote device | `list 1` or `list 192.168.1.10` |
| `pull` | Download a file from a remote device | `pull report.pdf 1` |
| `push` | Push a file to a remote device | `push ./photo.jpg 1` |
| `msg` | Send a text message to a remote device | `msg 1 Hello!` |
| `ls` | List files in the local shared directory | `ls` |
| `setdir` | Change the local shared directory | `setdir ~/Downloads` |
| `status` | Show current IP, port, and shared directory | `status` |
| `help` | Show command help and examples | `help push` |
| `exit` | Exit the application (Ctrl+D also works) | `exit` |

> The target in commands can be a device ID from `scan` results (e.g. `1`) or a direct IP address.

### Example Session

```
$ pylocalsend --dir ./shared
[*] Initializing PyLocalSend with shared directory: /home/user/shared
Welcome to PyLocalSend. Type help or ? to list commands.

(pylocalsend) scan
[+] Discovered devices:
  [1] MacBook-Pro (192.168.1.10)
  [2] Ubuntu-PC (192.168.1.20)

(pylocalsend) push ./report.pdf 1
[*] Pushing report.pdf (15.2MB) to 192.168.1.10...
  ██████████████████████████████ 100.0%  15.2MB/15.2MB  48.5MB/s
[+] Success!

(pylocalsend) msg 2 File sent, please check
[+] Message sent!

(pylocalsend) list 1
[*] Files on 192.168.1.10:
  - notes.txt
  - photo.jpg

(pylocalsend) pull notes.txt 1
[*] Pulling notes.txt from 192.168.1.10...
  ██████████████████████████████ 100.0%  2.3KB/2.3KB  1.1MB/s
[+] Downloaded to current directory.
```

## Network Requirements

- Both devices must be on the same local network
- Firewall must allow TCP port 53317 (UDP 53317 for mDNS discovery)
- AP isolation (client isolation) must be disabled on the router

## License

[MIT](LICENSE)
