import os
import sys
import socket
import ipaddress
import json
import argparse
import http.server
import socketserver
import threading
from urllib.parse import urlparse, unquote
import time
import cmd
import requests

# Optional dependency for discovery
try:
    from zeroconf import IPVersion, ServiceInfo, Zeroconf, ServiceBrowser
except ImportError:
    Zeroconf = None

PORT = 53317
SERVICE_TYPE = "_pylocalsend._tcp.local."
SHARE_DIR = "."

EXCLUDED_NETWORKS = [
    ipaddress.ip_network('198.18.0.0/15'),   # Clash TUN / RFC 2544 benchmark
    ipaddress.ip_network('100.64.0.0/10'),    # CGNAT / Tailscale
    ipaddress.ip_network('172.17.0.0/16'),    # Docker default bridge
    ipaddress.ip_network('172.18.0.0/16'),    # Docker user-defined
]

EXCLUDED_IFACE_PREFIXES = (
    'lo', 'docker', 'br-', 'veth', 'virbr',
    'tun', 'tap', 'utun', 'wg', 'tailscale',
    'vmnet', 'vboxnet',
)

def get_local_ips():
    """Enumerate all local IPv4 addresses, filtering out virtual/VPN interfaces.
    Returns a list of (interface_name, ip_string) or just ip_strings."""
    candidates = []

    # Method 1: netifaces (most reliable, gives interface names)
    try:
        import netifaces
        for iface in netifaces.interfaces():
            if iface.lower().startswith(EXCLUDED_IFACE_PREFIXES):
                continue
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    candidates.append(addr['addr'])
    except ImportError:
        # Method 2: socket.getaddrinfo + UDP probe (no extra deps)
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                candidates.append(info[4][0])
        except socket.gaierror:
            pass
        for target in ['10.255.255.255', '192.168.255.255', '172.31.255.255']:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0)
                s.connect((target, 1))
                candidates.append(s.getsockname()[0])
                s.close()
            except Exception:
                pass

    seen = set()
    filtered = []
    for ip_str in candidates:
        if ip_str in seen:
            continue
        seen.add(ip_str)
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback or ip.is_link_local:
            continue
        if any(ip in net for net in EXCLUDED_NETWORKS):
            continue
        if ip.is_private:
            filtered.append(ip_str)
    return filtered

def pick_best_ip(ips):
    """Prefer common LAN ranges: 192.168.x > 10.x > 172.x > first available."""
    for prefix in ['192.168.', '10.', '172.']:
        for ip in ips:
            if ip.startswith(prefix):
                return ip
    return ips[0] if ips else '127.0.0.1'

class FileServerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to prevent logging every request to stdout
        pass

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = unquote(parsed_path.path)

        if path == "/list":
            files = []
            if os.path.exists(SHARE_DIR) and os.path.isdir(SHARE_DIR):
                for f in os.listdir(SHARE_DIR):
                    if os.path.isfile(os.path.join(SHARE_DIR, f)):
                        files.append(f)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(files).encode())
        
        elif path.startswith("/download/"):
            filename = path[len("/download/"):]
            file_path = os.path.join(SHARE_DIR, filename)
            if os.path.abspath(file_path).startswith(os.path.abspath(SHARE_DIR)) and os.path.exists(file_path):
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(os.path.getsize(file_path)))
                self.end_headers()
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File not found")

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = unquote(parsed_path.path)
        raw_length = self.headers.get('Content-Length')
        if raw_length is None:
            self.send_error(411, "Content-Length required")
            return
        content_length = int(raw_length)
        post_data = self.rfile.read(content_length)

        if path == "/message":
            try:
                msg = json.loads(post_data.decode('utf-8'))
                sender = msg.get('sender', 'unknown')
                text = msg.get('text', '')
                print(f"\n[MSG] from {sender}: {text}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'OK')
            except Exception as e:
                self.send_error(400, str(e))
        else:
            filename = self.headers.get('X-File-Name', 'received_file')
            save_path = os.path.join(SHARE_DIR, filename)
            try:
                with open(save_path, 'wb') as f:
                    f.write(post_data)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'OK')
                print(f"\n[+] Automatically received pushed file: {filename}")
            except Exception as e:
                self.send_error(500, str(e))

class DiscoveryListener:
    def __init__(self):
        self.devices = {}

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info and info.addresses:
            all_addrs = [socket.inet_ntoa(a) for a in info.addresses]
            valid = []
            for addr in all_addrs:
                ip = ipaddress.ip_address(addr)
                if ip.is_loopback or ip.is_link_local:
                    continue
                if any(ip in net for net in EXCLUDED_NETWORKS):
                    continue
                if ip.is_private:
                    valid.append(addr)
            best = pick_best_ip(valid) if valid else all_addrs[0]
            alias = name.split('.')[0]
            self.devices[alias] = best

    def remove_service(self, zeroconf, type, name):
        pass

    def update_service(self, zeroconf, type, name):
        pass

class LocalSendShell(cmd.Cmd):
    intro = 'Welcome to PyLocalSend. Type help or ? to list commands.\n'
    prompt = '(pylocalsend) '

    def emptyline(self):
        pass

    def __init__(self, port, share_dir):
        super().__init__()
        self.port = port
        self.share_dir = share_dir
        self.discovered = {} # {id: (name, ip)}
        self.session = requests.Session()
        self.session.trust_env = False
        self.zc = Zeroconf() if Zeroconf else None
        if self.zc:
            self.register_self()

    def register_self(self):
        all_ips = get_local_ips()
        if not all_ips:
            all_ips = [self.get_ip()]
        hostname = socket.gethostname()
        info = ServiceInfo(
            SERVICE_TYPE,
            f"{hostname}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(ip) for ip in all_ips],
            port=self.port,
            properties={'alias': hostname}
        )
        self.zc.register_service(info)

    def get_ip(self):
        ips = get_local_ips()
        return pick_best_ip(ips)

    def do_scan(self, arg):
        '''Scan for PyLocalSend devices on the local network via mDNS.
Discovered devices are assigned numeric IDs for use with other commands.

Usage:  scan

Example:
  (pylocalsend) scan
  [+] Discovered devices:
    [1] MacBook-Pro (192.168.1.10)
    [2] Ubuntu-PC (192.168.1.20)'''
        if not self.zc:
            print("Error: zeroconf not available")
            return
        
        print("[*] Scanning...")
        listener = DiscoveryListener()
        browser = ServiceBrowser(self.zc, SERVICE_TYPE, listener)
        time.sleep(2)
        
        self.discovered = {}
        if not listener.devices:
            print("[-] No devices found.")
            return

        print("[+] Discovered devices:")
        for i, (name, ip) in enumerate(listener.devices.items(), 1):
            self.discovered[str(i)] = (name, ip)
            print(f"  [{i}] {name} ({ip})")

    def _resolve_ip(self, target):
        if target in self.discovered:
            return self.discovered[target][1]
        return target

    def do_list(self, arg):
        '''List shared files on a remote device.
The target can be a device ID from scan results or a direct IP address.

Usage:  list <ID_or_IP>

Examples:
  (pylocalsend) list 1
  (pylocalsend) list 192.168.1.10'''
        if not arg:
            print("Usage: list <ID_or_IP>")
            return
        target_ip = self._resolve_ip(arg)
        try:
            response = self.session.get(f"http://{target_ip}:{self.port}/list", timeout=5)
            if response.status_code == 200:
                files = response.json()
                print(f"[*] Files on {target_ip}:")
                for f in files: print(f"  - {f}")
            else:
                print(f"[-] Failed: {response.status_code}")
        except Exception as e:
            print(f"[-] Error: {e}")

    def do_pull(self, arg):
        '''Download a file from a remote device to the current directory.
Use "list" first to see available files on the remote device.

Usage:  pull <filename> <ID_or_IP>

Examples:
  (pylocalsend) pull report.pdf 1
  (pylocalsend) pull photo.jpg 192.168.1.10'''
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: pull <filename> <ID_or_IP>")
            return
        filename, target = parts[0], parts[1]
        target_ip = self._resolve_ip(target)
        print(f"[*] Pulling {filename} from {target_ip}...")
        try:
            response = self.session.get(f"http://{target_ip}:{self.port}/download/{filename}", stream=True)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
                print(f"[+] Downloaded to current directory.")
            else:
                print(f"[-] Download failed: {response.status_code}")
        except Exception as e:
            print(f"[-] Error: {e}")

    def do_push(self, arg):
        '''Push a local file to a remote device.
The file will be saved in the remote device's shared directory.

Usage:  push <local_path> <ID_or_IP>

Examples:
  (pylocalsend) push ./notes.txt 1
  (pylocalsend) push /home/user/photo.jpg 192.168.1.10'''
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: push <local_path> <ID_or_IP>")
            return
        file_path, target = parts[0], parts[1]
        target_ip = self._resolve_ip(target)
        if not os.path.exists(file_path):
            print(f"[-] File {file_path} not found.")
            return
        filename = os.path.basename(file_path)
        print(f"[*] Pushing {filename} to {target_ip}...")
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            headers = {'X-File-Name': filename}
            response = self.session.post(f"http://{target_ip}:{self.port}/", data=file_data, headers=headers)
            if response.status_code == 200: print("[+] Success!")
            else: print(f"[-] Failed: {response.status_code}")
        except Exception as e:
            print(f"[-] Error: {e}")

    def do_msg(self, arg):
        '''Send a text message to a remote device.

Usage:  msg <ID_or_IP> <message>

Examples:
  (pylocalsend) msg 1 Hello, are you there?
  (pylocalsend) msg 192.168.1.10 File is ready for download'''
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: msg <ID_or_IP> <message>")
            return
        target, text = parts[0], parts[1]
        target_ip = self._resolve_ip(target)
        payload = json.dumps({'sender': socket.gethostname(), 'text': text})
        try:
            response = self.session.post(
                f"http://{target_ip}:{self.port}/message",
                data=payload,
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            if response.status_code == 200:
                print("[+] Message sent!")
            else:
                print(f"[-] Failed: {response.status_code}")
        except Exception as e:
            print(f"[-] Error: {e}")

    def do_status(self, arg):
        '''Show current server status including IP, port, and shared directory.

Usage:  status

Example:
  (pylocalsend) status
  [*] Active IP: 192.168.1.5
  [*] All LAN IPs: 192.168.1.5, 10.0.0.2
  [*] Port: 53317
  [*] Sharing Directory: /home/user/shared'''
        all_ips = get_local_ips()
        print(f"[*] Active IP: {pick_best_ip(all_ips)}")
        if all_ips:
            print(f"[*] All LAN IPs: {', '.join(all_ips)}")
        print(f"[*] Port: {self.port}")
        print(f"[*] Sharing Directory: {os.path.abspath(self.share_dir)}")

    def do_setdir(self, arg):
        '''Change the local shared directory for serving and receiving files.
If the directory does not exist, it will be created automatically.

Usage:  setdir <path>

Examples:
  (pylocalsend) setdir ~/Downloads
  (pylocalsend) setdir /tmp/shared'''
        if not arg:
            print("Usage: setdir <path>")
            return
        new_dir = os.path.expanduser(arg)
        if not os.path.exists(new_dir):
            try:
                os.makedirs(new_dir)
                print(f"[+] Created directory: {new_dir}")
            except Exception as e:
                print(f"[-] Error creating directory: {e}")
                return
        
        if not os.path.isdir(new_dir):
            print(f"[-] Error: {new_dir} is not a directory.")
            return

        self.share_dir = new_dir
        global SHARE_DIR
        SHARE_DIR = new_dir
        print(f"[+] Shared directory updated to: {os.path.abspath(new_dir)}")

    def do_ls(self, arg):
        '''List all files in the local shared directory.
These are the files that other devices can see and download.

Usage:  ls

Example:
  (pylocalsend) ls
  [*] Local files in /home/user/shared:
    - report.pdf
    - photo.jpg'''
        print(f"[*] Local files in {os.path.abspath(self.share_dir)}:")
        try:
            files = [f for f in os.listdir(self.share_dir) if os.path.isfile(os.path.join(self.share_dir, f))]
            if not files:
                print("  (Empty)")
            for f in files:
                print(f"  - {f}")
        except Exception as e:
            print(f"[-] Error listing files: {e}")

    def do_exit(self, arg):
        '''Exit PyLocalSend and stop the file sharing server.

Usage:  exit / Ctrl+D'''
        print()
        if self.zc:
            self.zc.close()
        return True

    do_EOF = do_exit

def start_background_server(port, share_dir):
    global SHARE_DIR
    SHARE_DIR = share_dir
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("", port), FileServerHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    return httpd

def main():
    parser = argparse.ArgumentParser(description="PyLocalSend Interactive Mode")
    parser.add_argument("--dir", default=".", help="Directory to share/save files")
    parser.add_argument("--port", type=int, default=PORT, help="Port to listen on")
    args = parser.parse_args()

    # Create shared directory if it doesn't exist
    if not os.path.exists(args.dir):
        os.makedirs(args.dir)

    print(f"[*] Initializing PyLocalSend with shared directory: {os.path.abspath(args.dir)}")
    start_background_server(args.port, args.dir)
    
    # Start Interactive Shell
    LocalSendShell(args.port, args.dir).cmdloop()

if __name__ == "__main__":
    main()
