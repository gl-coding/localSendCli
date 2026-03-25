# PyLocalSend CLI (Interactive Edition)

A high-performance, lightweight Python CLI tool for secure file and directory sharing over a local network, inspired by LocalSend.

## 🚀 Features

- **Interactive Shell**: A persistent `(pylocalsend)` prompt for managing transfers without restarting.
- **Auto Discovery**: Automatically find other devices in your LAN using mDNS (Zeroconf).
- **Dual Transfer Modes**:
  - **Push**: Send files directly to another device.
  - **Pull**: List and download files from another device's shared directory.
- **Live Management**: Change shared directories or list local files in real-time.
- **Cross-Platform**: Works seamlessly on macOS, Ubuntu, and other Linux distributions.

## 🛠 Installation

Requires **Python 3.7+**.

```bash
pip install zeroconf requests
```

## 📖 Quick Start

Run the tool on any two machines in the same network:

```bash
python3 localsend_cli.py --dir ./my_shared_files
```

### Common Commands

Once inside the `(pylocalsend)` prompt:

| Command | Description | Example |
| :--- | :--- | :--- |
| `scan` | Discover nearby devices | `scan` |
| `ls` | List files in YOUR shared directory | `ls` |
| `setdir` | Change local shared directory | `setdir ~/Downloads` |
| `list` | List files on a remote device | `list 1` (or `list 192.168.1.5`) |
| `pull` | Download a file from a remote device | `pull movie.mp4 1` |
| `push` | Send a file to a remote device | `push secret.zip 1` |
| `status` | Show current IP, Port, and Directory | `status` |
| `exit` | Quit the application | `exit` |

## 🤝 Contribution

Feel free to customize `localsend_cli.py` for your own workflows!
