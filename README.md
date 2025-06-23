# Transmission Shell - Remote Transmission CLI

## Overview
Transmission Shell is a powerful **command-line interface** (CLI) for remotely controlling a Transmission daemon. It provides enhanced functionality beyond the web UI, including **torrent management, auto-fetching from RSS feeds, automatic resume for stalled torrents, and more.**

## Features
✅ **Manage torrents** (add, remove, start, stop, list, etc.)  
✅ **Auto-complete commands** for quick input  
✅ **Auto-fetch torrents from RSS feeds** (`rssfetch`, `rssauto`)  
✅ **Prevents duplicate torrents** when fetching from RSS feeds  
✅ **Auto-resume stalled torrents** that stop downloading  
✅ **Progress bars & ETA estimation** for torrents  
✅ **Watch mode** for real-time torrent monitoring  
✅ **Support for paused torrent addition** (`add paused`)  
✅ **Clear command history & screen** (`clear`)  
✅ **Port testing & blocklist updates**  

---

## Installation
### **Dependencies**
Ensure you have the required dependencies installed:
```sh
pip install transmission-rpc feedparser
```

### **Clone the Repository**
```sh
git clone https://github.com/your-repo/transmission-shell.git
cd transmission-shell
```

### **Run the Script**
```sh
python3 transmission_shell.py
```

---

## Usage
### **Torrent Management**
| Command | Description |
|---------|-------------|
| `list` | Show all torrents |
| `list downloading` | Show only downloading torrents |
| `list 50 100` | Show torrents with 50%-100% progress |
| `watch` | Continuously refresh torrent status |
| `add <url> [dir] [paused]` | Add a torrent (optionally paused) |
| `adddir <dir> [dir] [paused]` | Add torrents from a directory |
| `massadd <file> [dir] [paused]` | Add torrents from a file |
| `remove <id>` | Remove a torrent by ID |
| `removecompleted` | Remove all completed torrents |
| `start <id>` | Start a torrent |
| `forcestart <id>` | Start torrent, skipping queue |
| `stop <id>` | Stop a torrent |
| `startall` | Start all torrents |
| `forcestartall` | Start all torrents, skipping queue |
| `stopall` | Stop all torrents |

---

### **RSS Torrent Auto-Fetching**
| Command | Description |
|---------|-------------|
| `rssfetch` | Fetch new torrents from RSS feeds |
| `rssauto [secs]` | Auto-fetch torrents every X seconds (default: 900) |

📂 **Adding RSS Feeds**
- Edit `rss_feeds.txt` and add one RSS feed URL per line.

📌 **Prevents Duplicate Torrents**
- Uses `rss_seen.txt` to track previously added torrents.

---

### **Auto-Resume Stalled Torrents**
| Command | Description |
|---------|-------------|
| `autoresume [secs] [stall_min]` | Restart stalled torrents every X seconds (default: 900) |

🔄 **How it Works**
- Scans for torrents stuck at `0 KB/s` download speed.
- Resumes torrents stalled for more than X minutes.
- Automatically restarts them.

---

### **Other Utilities**
| Command | Description |
|---------|-------------|
| `peers <id>` | Request more peers for a torrent |
| `porttest` | Check if Transmission's port is open |
| `blocklist` | Update Transmission's blocklist |
| `clear` | Clear the screen |
| `exit` | Quit the shell |

---

## Configuration
Modify the script variables to match your Transmission setup:
```python
TRANSMISSION_HOST = "localhost"
TRANSMISSION_PORT = 9091
TRANSMISSION_PATH = '/transmission/rpc/'
TRANSMISSION_USER = "your_username"
TRANSMISSION_PASSWORD = "your_password"
```

---

## Future Enhancements
📌 **Web UI for remote access**  
📌 **Custom torrent tagging & filtering**  
📌 **Email/Discord notifications for new torrents**  
📌 **Bandwidth limit management**  

---

##License

This project is licensed under the Attribution-ShareAlike License.

##Disclaimer

This software is provided "as is", without warranty of any kind. The author assumes no responsibility for any issues, damages, or legal consequences arising from the use or misuse of this tool. Use at your own risk.

MIT License

---

## Contributing
Feel free to submit pull requests, bug fixes, or suggestions to improve the script! 🎉


