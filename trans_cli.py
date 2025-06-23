#!/usr/bin/env python3

import transmission_rpc
import sys
import os
import time
import datetime
import readline
import feedparser
import getpass
import logging
import urllib
from transmission_rpc.error import TransmissionError
from pytz import timezone

### TODO!

# add 'stalled' option to peers and forcestart commands

# Configuration
TRANSMISSION_HOST = "localhost"
TRANSMISSION_PORT = 9091
TRANSMISSION_PATH = '/transmission/rpc/'
TRANSMISSION_USER = "transmission"  # Change if needed
TRANSMISSION_PASSWORD = "atm3ns13"  # Change if needed
HISTORY_FILE = ".transmission_shell_history"
RSS_FEED_FILE = "rss_feeds.txt"  # File containing RSS feed URLs
SEEN_TORRENTS_FILE = ".rss_seen"  # Stores previously added torrents
TIMEZONE_OFFSET = -8

# Logging Configuration
logging.basicConfig(
    filename="logs/transmission_shell.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def is_stalled(torrent,stall_threshold=10):
    if torrent.status == "downloading" and torrent.rate_download == 0:
        ctime = timezone("US/Pacific").localize(datetime.datetime.now())
        ttime = torrent.activity_date
        diff_time = ctime - ttime
        stall_time = int(diff_time.total_seconds() / 60)
        if stall_time >= stall_threshold:
            return True
    return False

    
def is_paused(torrent):
    if torrent.status == "stopped" and torrent.progress < 100:
        return True
    return False
    
def human_status(torrent):
    statuses = {'check pending':'Check Pending','checking':'Checking','stopped':'Finished','download pending':'Queued','downloading':'Downloading','seeding':'Seeding','seed pending':'Queued for Seed'}

    if is_stalled(torrent):
        return "STALLED"
    if is_paused(torrent):
        return "paused"
    return statuses[torrent.status]

def load_command_history():
    """Load command history from a file for persistent history."""
    if os.path.exists(HISTORY_FILE):
        readline.read_history_file(HISTORY_FILE)
        logging.info(f"Command history loaded from: {HISTORY_FILE}")

def save_command_history():
    """Save command history to a file on exit."""
    readline.write_history_file(HISTORY_FILE)
    logging.info(f"Command history written to: {HISTORY_FILE}")

def get_file_name_from_magnet(magnet_link):
    # Parse the magnet link to get query parameters
    parsed_url = urllib.parse.urlparse(magnet_link)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    # Extract the 'dn' (display name) parameter, which typically contains the file name
    file_name = query_params.get('dn', [None])[0]
    
    if file_name:
        return file_name
    else:
        return magnet_link

def connect_to_transmission(host, username, password, max_retries=3, delay=5):
    """Attempts to connect to Transmission with retries."""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Connecting to [{host}]...",end="")
            client = transmission_rpc.Client(
                host=host,
                port=TRANSMISSION_PORT,
                path=TRANSMISSION_PATH,
                username=username,
                password=password,
                timeout=10  # Prevents indefinite hangs
            )
            logging.info("Connected to Transmission successfully.")
            print("connected!")
            return client
        except TransmissionError as e:
            print(f"failed! Retrying in {delay * attempt} seconds")
            logging.warning(f"Attempt {attempt}: Connection failed - {e}")
            
            if attempt < max_retries:
                time.sleep(delay * attempt)  # Exponential backoff
            else:
                logging.error("Max retries reached. Could not connect to Transmission.")
                print("Error: Could not connect to Transmission. Please check the server.")
                return None
        
def make_prog_bar(perc):
    def spaces(perc):
        if int(perc) < 10: return "  "
        if int(perc) < 100: return " "
        return ""
    def fill(perc):
        return "#" * (int(perc) // 10)  # Ensure integer division
    def blank(perc):
        return "-" * (10-(int(perc) // 10))
    def percent(perc):
        return str(f" ({perc:.1f}%){spaces(perc)}")
    
    return fill(perc) + blank(perc) + percent(perc)

def list_torrents(client, status_filter=None, min_progress=0, max_progress=100):
    """pythonhosted.org/transmission/reference/transmissionrpc.html
    List all torrents with optional filters:
    - status_filter: Show only torrents with a specific status (e.g., 'downloading', 'seeding').
    - min_progress, max_progress: Show torrents within a progress range (0-100).
    """
    def fix_eta(eta):
        if eta == "not available":
            return "- --:--:--"
        return str(eta)
       
    try:
        torrents = client.get_torrents()
        if not torrents:
            print("No active torrents.")
            return
        
        filtered_torrents = [
            t for t in torrents 
            if (status_filter is None or t.status.lower() == status_filter.lower()) and
               (min_progress <= t.progress <= max_progress)
        ]
    
        if not filtered_torrents:
            print("No torrents match the given filters.")
            return

        print(f"\n=== Torrent List ===")
        trunc_length = 75
        for t in filtered_torrents:
            if len(t.name) > trunc_length:
                truncated_name = (t.name[:trunc_length-3] + "...")
            elif len(t.name) < trunc_length:
                fill = trunc_length - len(t.name)
                truncated_name = t.name + " " * fill
            else:
                truncated_name = t.name
                
            fixed_id = f"{t.id} " if t.id < 10 else t.id
            progress_bar = make_prog_bar(t.progress)
            eta = f"(eta: {fix_eta(t.format_eta())})" if "downloading" in t.status else ""
            the_status = human_status(t)
      
            print(f"{fixed_id} | {truncated_name} | {progress_bar} | {the_status} {eta}")
    except TransmissionError as e:
        logging.error(f"Error fetching torrent list: {e}")
        print("Error: Unable to fetch torrents. Transmission may be down.")
    
def watch_torrents(client, interval=5):
    """Continuously monitor torrents and refresh status."""
    try:
        while True:
            os.system("clear" if os.name == "posix" else "cls")  # Clear screen for a clean refresh
            print("Watching torrents (Press Ctrl+C to stop)...")
            list_torrents(client)
            time.sleep(interval)
    except TransmissionError as e:
        logging.error(f"Connection lost while watching torrents: {e}")
        print("Error: Lost connection to Transmission.")
    except KeyboardInterrupt:
        print("\nStopped watching torrents.")

def add_torrent(client, url, download_dir=None, paused=False):
    """Add a torrent by URL with an optional download directory."""
    try:
        client.add_torrent(url, download_dir=download_dir,paused=paused)
        print(f"Torrent added successfully! {'Download directory: ' + download_dir if download_dir else ''}")
    except TransmissionError as e:
        logging.error(f"Error adding torrent {url}: {e}")
        print("Error: Unable to add torrent. Transmission may be unresponsive.")

def add_torrents_from_directory(client, directory, download_dir=None,paused=False):
    """Add all .torrent files from a directory."""
    if not os.path.exists(directory):
        logging.error(f"Error adding torrents from directory. {directory} does not exist")
        print(f"Error: {directory} does not exist.")
        return
    
    torrent_files = [f for f in os.listdir(directory) if f.endswith(".torrent")]
    
    if not torrent_files:
        logging.error(f"No .torrent files found in {directory}")
        print(f"No .torrent files found in {directory}")
        return
    
    for torrent_file in torrent_files:
        file_path = os.path.join(directory, torrent_file)
        try:
            client.add_torrent(f"file://{file_path}", download_dir=download_dir,paused=paused)
            print(f"Added {torrent_file}")
        except TransmissionError as e:
            logging.error(f"Error adding torrent {torrent_file}: {e}")
            print(f"Error: Unable to add {torrent_file}. Transmission may be unresponsive.")

def add_torrents_from_file(client,file,directory=False,paused=False):
    """Add torrents from a file containing a list of magnet links."""

    file_path = file
    download_dir = directory if directory else None

    if not os.path.exists(file_path):
        logging.error(f"Error adding torrents from file: {file} does not exist")
        print(f"Error: {file} does not exist.")
        return

    try:
        with open(file_path, "r") as file:
            magnet_links = [line.strip() for line in file if line.strip().startswith("magnet:")]

        if not magnet_links:
            logging.error(f"Error adding torrents from file: {file} contains no magnet links.")
            print("No valid magnet links found in {file}")
            return

        for link in magnet_links:
            client.add_torrent(link, download_dir=download_dir)
            print(f"Added: {get_file_name_from_magnet(link)}")

        print(f"Successfully added {len(magnet_links)} torrents from file.")

    except TransmissionError as e:
        logging.error(f"Error adding torrents from {file}: {e}")
        print(f"Error: Unable to add torrents from {file}. Transmission may be unresponsive.")


def remove_torrent(client, torrent_id):
    """Remove a torrent by ID."""
    try:
        client.remove_torrent(torrent_id, delete_data=False)
        print("Torrent removed successfully!")
    except TransmissionError as e:
        logging.error(f"Error removing torrent: {e}")
        print(f"Error: Unable to remove torrent. Transmission may be unresponsive.")

def start_torrent(client, torrent_id, bypass=False):
    """Start a torrent by ID."""
    try:
        client.start_torrent(torrent_id,bypass_queue=bypass)
        print("Torrent started!")
    except TransmissionError as e:
        logging.error(f"Error starting torrent: {e}")
        print(f"Error starting torrent {torrent_id}. Transmission may be unresponsive.")

def stop_torrent(client, torrent_id):
    """Stop a torrent by ID."""
    try:
        client.stop_torrent(torrent_id)
        print("Torrent stopped!")
    except Exception as e:
        logging.error(f"Error stopping torrent {torrent_id}: {e}")
        print(f"Error stopping torrent {torrent_id}. Transmission may be unresponsive.")

def start_all_torrents(client,bypass=False):
    """Start all torrents."""
    try:
        client.start_all(bypass_queue=bypass)
        print("All torrents started!")
    except Exception as e:
        logging.error(f"Error starting all torrents: {e}")
        print(f"Error starting all torrents. Transmission may be unresponsive.")

def stop_all_torrents(client):
    """Stop all torrents."""
    try:
        client.stop_torrent()
        print("All torrents stopped!")
    except Exception as e:
        logging.error(f"Error stopping all torrents: {e}")
        print(f"Error stopping all torrents. Transmission may be unresponsive.")

def request_more_peers(client, torrent_id=None):
    """Request more peers for a specific torrent or all active torrents if no ID is provided."""
    try:
        if torrent_id:
            client.reannounce_torrent(int(torrent_id))
            print(f"Requested more peers for torrent ID {torrent_id}.")
        else:
            torrents = client.get_torrents()
            active_torrents = [t.id for t in torrents if t.status in ["downloading", "seeding"]]
            
            if not active_torrents:
                print("No active torrents to request peers for.")
                return
            
            for tid in active_torrents:
                client.reannounce_torrent(tid)
                print(f"Requested more peers for torrent ID {tid}.")
            
            print(f"Requested peers for {len(active_torrents)} active torrents.")
    except Exception as e:
        logging.error(f"Error requesting more peers: {e}")
        print(f"Error requesting more peers. Transmission may be unresponsive.")


def port_test(client):
    """Perform a port test to check if the Transmission port is open."""
    try:
        result = client.port_test()
        print("Port is open!" if result else "Port is closed.")
    except Exception as e:
        logging.error(f"Error performing port test: {e}")
        print(f"Error performing port test. Transmission may be unresponsive.")

def update_blocklist(client):
    """Update the blocklist in Transmission."""
    try:
        client.blocklist_update()
        print("Blocklist updated successfully!")
    except Exception as e:
        logging.error(f"Error updating blocklist: {e}")
        print(f"Error updating blocklist. Transmission may be unresponsive.")
        
def clear_screen():
    """Clear the terminal screen."""
    os.system("clear" if os.name == "posix" else "cls")
        
def remove_completed_torrents(client):
    """Remove all completed torrents (100% downloaded)."""
    torrents = client.get_torrents()
    completed_torrents = [t.id for t in torrents if t.progress == 100]
    if not completed_torrents:
        print("No completed torrents to remove.")
        return
        
    try:
        client.remove_torrent(completed_torrents, delete_data=False)
        print(f"Removed {len(completed_torrents)} completed torrents.")
    except Exception as e:
        logging.error(f"Error removing completed torrents: {e}")
        print(f"Error removing completed torrents. Transmission may be unresponsive.")
            
def load_rss_feeds():
    """Load RSS feed URLs from a file."""
    if not os.path.exists(RSS_FEED_FILE):
        print(f"RSS feed file '{RSS_FEED_FILE}' not found. Create it and add feed URLs.")
        return []
    
    with open(RSS_FEED_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


def load_seen_torrents():
    """Load previously seen torrents to avoid duplicates."""
    if not os.path.exists(SEEN_TORRENTS_FILE):
        return set()
    
    with open(SEEN_TORRENTS_FILE, "r") as f:
        return set(line.strip() for line in f)


def save_seen_torrent(magnet_link):
    """Save a newly seen torrent to the history file."""
    with open(SEEN_TORRENTS_FILE, "a") as f:
        f.write(magnet_link + "\n")


def fetch_rss_torrents(client):
    """Fetch new torrents from RSS feeds and add only unseen ones."""
    rss_feeds = load_rss_feeds()
    if not rss_feeds:
        print("No RSS feeds found.")
        return

    seen_torrents = load_seen_torrents()
    new_torrents = 0

    for feed_url in rss_feeds:
        print(f"Checking RSS feed: {feed_url}")
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries:
            magnet_link = entry.link.strip()
            
            if magnet_link in seen_torrents:
                continue  # Skip already seen torrents
            
            client.add_torrent(magnet_link)
            save_seen_torrent(magnet_link)
            new_torrents += 1
            print(f"Added: {entry.title}")

    if new_torrents == 0:
        print("No new torrents found.")
    else:
        print(f"Added {new_torrents} new torrents.")


def start_rss_fetching(client, interval=900):
    """Run the RSS fetching every 'interval' seconds (default: 15 minutes)."""
    print("Starting RSS auto-fetching... Press Ctrl+C to stop.")
    try:
        while True:
            fetch_rss_torrents(client)
            print(f"Waiting {interval} seconds before next fetch...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nRSS fetching stopped.")
        
def get_stalled_torrents(client, stall_threshold=10):
    """
    Identify torrents that are stalled.
    - A torrent is stalled if it's `downloading` but has `0 KB/s` speed for `stall_threshold` minutes.
    - Also includes torrents that are `stopped` but not completed.
    """
    stalled = []
    torrents = client.get_torrents()

    for t in torrents:
        if is_stalled(t,stall_threshold):
            stalled.append(t)
    
    return stalled


def get_paused_torrents(client):
    paused = []
    
    torrents = client.get_torrents()

    for t in torrents:
        if t.status == "stopped" and t.progress < 100:
            paused.append(t)
    
    return paused

def auto_resume_stalled(client, interval=900, stall_threshold=10):
    """
    Periodically scan and restart stalled torrents.
    - Runs every `interval` seconds (default: 15 minutes).
    - Resumes torrents that have been stalled for `stall_threshold` minutes.
    """
    print("Starting auto-resume for stalled torrents... Press Ctrl+C to stop.")
    try:
        while True:
            stalled_torrents = get_stalled_torrents(client, stall_threshold)
            
            if not stalled_torrents:
                print("No stalled torrents found.")
            else:
                for t in stalled_torrents:
                    print(f"Restarting stalled torrent: {t.name} (ID: {t.id})")
                    client.stop_torrent(t.id)
                    time.sleep(2)
                    client.start_torrent(t.id)

            print(f"Waiting {interval} seconds before next check...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nAuto-resume stopped.")
        
def get_server_info(client):
    torrents = len(client.get_torrents())
    print(f"No. of Torrents: {torrents}")
    
def save_magnets_for_paused(client, file=None):
    """
    Execute the command.
    :param args: List of arguments (expects one argument: output file path).
    """

    output_file = file if file else "./magnet_export.lst"
        
    paused_magnets = []
    paused_ids = []
    trackers = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://tracker.openbittorrent.com:6969",
    ]  # Common trackers (optional, improves compatibility)

    # Fetch torrents from the client
    torrents = client.get_torrents()  # This should return a list of dicts

    for t in torrents:
        if is_paused(t) and len(t.hash_string) > 0:
            info_hash = t.hash_string
            name = urllib.parse.quote(t.name)
            magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={name}"
            
            # Optionally add trackers
            for tracker in trackers:
                magnet_link += f"&tr={tracker}"
            if hasattr(t, "trackers") and t.trackers:
                for tracker in t.trackers:
                    if hasattr(tracker, "announce"):
                        magnet_link += f"&tr={tracker.announce}"

            paused_magnets.append(magnet_link)
            paused_ids.append(t.id)
         
    if not paused_magnets:
        print("No paused torrents found.")
        return

    # Save to file
    try:
        with open(output_file, "w") as f:
            f.write("\n".join(paused_magnets))
    except OSError as e:
        print(f"Error writing to file: {e}")   
        
    # Remove paused torrents without deleting files
    for torrent_id in paused_ids:
        client.remove_torrent(torrent_id, delete_data=False)
    print(f"Exported {len(paused_magnets)} magnet links to {output_file}")

def main():
    client = None
    COMMANDS = [
        "list", "watch", "add", "adddir", "massadd", "remove", "removecompleted",
        "start", "forcestart", "stop", "startall", "forcestartall", "stopall", "peers", "porttest",
        "blocklist", "clear", "exit", "help", "rssfetch", "rssauto", "autoresume", "connect", "disconnect", 
        "server-info", "exportmagnets"
    ]
    PATH_COMMANDS = ["adddir", "massadd","exportmagnets"]
    
    def file_completer(text, state):
        """Tab completion for filenames and directories."""
        options = []
        dirname = os.path.dirname(text) or "."
        prefix = os.path.basename(text)

        try:
            files = os.listdir(dirname)
            options = [os.path.join(dirname, f) for f in files if f.startswith(prefix)]
        except Exception:
            pass

        return options[state] if state < len(options) else None

    def completer(text, state):
        """Custom tab completer: Completes commands and file paths."""
        buffer = readline.get_line_buffer().strip()  # Get the full line user has typed
        parts = buffer.split()  # Split into words

        if not parts:
            return None  # Nothing typed yet

        command = parts[0]  # First word in the command
        
        if (text.startswith("./") or text.startswith("/")) and command in PATH_COMMANDS:
            return file_completer(text, state)  # File path completion
        else:
            options = [cmd for cmd in COMMANDS if cmd.startswith(text)]
            return options[state] if state < len(options) else None
    
    clear_screen()
    load_command_history()
    print("\nTransmission Shell - Type 'help' for commands")
    
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(readline.get_completer_delims().replace('.', '').replace('/', ''))
    readline.set_completer(completer)
    
    while True:
        try:
            command = input("transmission> ").strip().split()
            if not command:
                continue
            
            cmd = command[0].lower()
            paused = "paused" in command  # Check if 'paused' option is used
            
            if cmd == "connect":

                host = command[1] if len(command) > 1 else TRANSMISSION_HOST
                username = TRANSMISSION_USER if host == TRANSMISSION_HOST else input("Username: ")
                password = TRANSMISSION_PASSWORD if host == TRANSMISSION_HOST else getpass.getpass("Password: ")

                client = connect_to_transmission(host, username, password)
                if client:
                    get_server_info(client)
                    list_torrents(client)
                
            elif cmd == "disconnect":
                client = None
                print("Disconnected from Transmission.")
            
            elif cmd == "clear":
                clear_screen()
                            
            elif cmd == "exit":
                save_command_history()
                print("Exiting Transmission Shell.")
                break
            
            elif cmd == "help":
                print("\nAvailable Commands:")
                print("  list [status]                 - Show all torrents")
                print("  watch                         - Auto-refresh torrent status")
                print("  add <url> [dir] [paused]      - Add a new torrent with optional download directory")
                print("  adddir <dir> [dir] [paused]   - Add all torrents from a directory")
                print("  massadd <file> [dir] [paused] - Add a torrent magnets from a file")
                print("  exportmagnets [file]          - Export paused torrents to a file, then remove.")
                print("  rssfetch                      - Fetch new torrents from RSS feeds")
                print("  rssauto [secs]                - Automatically fetch RSS torrents (default: 900 sec)")
                print("  remove <id>                   - Remove a torrent by ID")
                print("  removecompleted               - Remove all completed torrents")
                print("  autoresume [secs] [stall_min] - Auto-restart stalled torrents")
                print("  start <id>                    - Start a torrent")
                print("  forcestart <id>               - Start a torrent, skipping the queue")                
                print("  stop <id>                     - Stop a torrent")
                print("  startall                      - Start all torrents")
                print("  forcestartall                 - Start all torrents, skipping the queue")                
                print("  stopall                       - Stop all torrents")
                print("  peers [id]                    - Request more peers for a torrent")
                print("  porttest                      - Check if the Transmission port is open")
                print("  server-info                   - Display Transmission server stats")
                print("  blocklist                     - Update the blocklist")
                print("  connect [host]                - Connect to a Transmission server")
                print("  disconnect                    - Disconnect from the current server")
                print("  clear                         - Clear screen")
                print("  exit                          - Quit the shell")
            
            elif client is None:
                print("Not connected. Use 'connect' first.")
                
#=========================================================================================================================================
# Commands below this line require connection to the server to function
#=========================================================================================================================================
              
            elif cmd == "exportmagnets":
                file = command[1] if len(command) > 1 else None
                save_magnets_for_paused(client,file)           
            
            elif cmd == "list" or cmd == "ls":
                if len(command) == 2 and command[1].isdigit():
                    list_torrents(client, min_progress=int(command[1]), max_progress=100)
                elif len(command) == 3 and command[1].isdigit() and command[2].isdigit():
                    list_torrents(client, min_progress=int(command[1]), max_progress=int(command[2]))
                elif len(command) == 2:
                    list_torrents(client, status_filter=command[1])
                else:
                    list_torrents(client)
	    
            elif cmd == "watch":
                watch_torrents(client)
            
            elif cmd == "add":
                if len(command) > 1:
                    download_dir = command[2] if len(command) > 2 and command[2] != "paused" else None
                    add_torrent(client, command[1], download_dir, paused)
                else:
                    print("usage: add <url> [dir] [paused]")

            elif cmd == "adddir":
                if len(command) > 1:
                    download_dir = command[2] if len(command) > 2 and command[2] != "paused" else None
                    add_torrents_from_directory(client, command[1], download_dir, paused)
                else:
                    print("usage: adddir <dir> [dir] [paused]")
                    
            elif cmd == "massadd" or cmd == "importmagnets":
                if len(command) > 1:
                    download_dir = command[2] if len(command) > 2 and command[2] != "paused" else None
                    add_torrents_from_file(client, command[1], download_dir, paused)
                else:
                    print("usage: massadd <file> [dir] [paused]")

            elif cmd == "remove" or cmd == "rm":
                if len(command) > 1:
                    remove_torrent(client, int(command[1]))
                else:
                    print(f"usage: remove <id>")
                
            elif cmd == "rssfetch":
                fetch_rss_torrents(client)

            elif cmd == "rssauto":
                interval = int(command[1]) if len(command) > 1 else 900  # Default: 15 min
                start_rss_fetching(client, interval)

            elif cmd == "start" and len(command) > 1:
                start_torrent(client, int(command[1]))
                
            elif cmd == "forcestart" and len(command) > 1:
                start_torrent(client, int(command[1]),True)

            elif cmd == "stop" and len(command) > 1:
                stop_torrent(client, int(command[1]))

            elif cmd == "startall":
                start_all_torrents(client)

            elif cmd == "forcestartall":
                start_all_torrents(client,True)

            elif cmd == "stopall":
                stop_all_torrents(client)

            elif cmd == "peers":
                peer_id = command[1] if len(command) > 1 else None
                request_more_peers(client, peer_id)

            elif cmd == "porttest":
                port_test(client)

            elif cmd == "blocklist":
                update_blocklist(client)
                
            elif cmd == "removecompleted" or cmd == "clearcompleted":
                remove_completed_torrents(client)
                
            elif cmd == "test":
                get_stalled_torrents(client)
                
            elif cmd == "autoresume":
                interval = int(command[1]) if len(command) > 1 else 900
                stall_threshold = int(command[2]) if len(command) > 2 else 10
                auto_resume_stalled(client, interval, stall_threshold)
            
            else:
                print("Unknown command '" + cmd + "'.\nType 'help' for a list of commands.")
        
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit the shell.")

if __name__ == "__main__":
    main()

