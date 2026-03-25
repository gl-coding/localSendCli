import os
import sys
import socket
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
ALREADY_DISCOVERED = {} # {id: (name, ip)}

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
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
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
        if info:
            ip = socket.inet_ntoa(info.addresses[0])
            alias = name.split('.')[0]
            self.devices[alias] = ip

class LocalSendShell(cmd.Cmd):
    intro = 'Welcome to PyLocalSend. Type help or ? to list commands.\n'
    prompt = '(pylocalsend) '

    def __init__(self, port, share_dir):
        super().__init__()
        self.port = port
        self.share_dir = share_dir
        self.discovered = {} # {id: (name, ip)}
        self.zc = Zeroconf() if Zeroconf else None
        if self.zc:
            self.register_self()

    def register_self(self):
        ip = self.get_ip()
        hostname = socket.gethostname()
        info = ServiceInfo(
            SERVICE_TYPE,
            f"{hostname}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(ip)],
            port=self.port,
            properties={'alias': hostname}
        )
        self.zc.register_service(info)

    def get_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def do_scan(self, arg):
        '''Scan for devices in the local network'''
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
        '''List files on a remote device: list <ID_or_IP>'''
        if not arg:
            print("Usage: list <ID_or_IP>")
            return
        target_ip = self._resolve_ip(arg)
        try:
            response = requests.get(f"http://{target_ip}:{self.port}/list", timeout=5)
            if response.status_code == 200:
                files = response.json()
                print(f"[*] Files on {target_ip}:")
                for f in files: print(f"  - {f}")
            else:
                print(f"[-] Failed: {response.status_code}")
        except Exception as e:
            print(f"[-] Error: {e}")

    def do_pull(self, arg):
        '''Download a file from a remote device: pull <filename> <ID_or_IP>'''
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: pull <filename> <ID_or_IP>")
            return
        filename, target = parts[0], parts[1]
        target_ip = self._resolve_ip(target)
        print(f"[*] Pulling {filename} from {target_ip}...")
        try:
            response = requests.get(f"http://{target_ip}:{self.port}/download/{filename}", stream=True)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
                print(f"[+] Downloaded to current directory.")
            else:
                print(f"[-] Download failed: {response.status_code}")
        except Exception as e:
            print(f"[-] Error: {e}")

    def do_push(self, arg):
        '''Push a file to a remote device: push <local_path> <ID_or_IP>'''
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
                headers = {'X-File-Name': filename}
                response = requests.post(f"http://{target_ip}:{self.port}/", data=f, headers=headers)
            if response.status_code == 200: print("[+] Success!")
            else: print(f"[-] Failed: {response.status_code}")
        except Exception as e:
            print(f"[-] Error: {e}")

    def do_status(self, arg):
        '''Show current server status'''
        print(f"[*] IP: {self.get_ip()}")
        print(f"[*] Port: {self.port}")
        print(f"[*] Sharing Directory: {os.path.abspath(self.share_dir)}")

    def do_setdir(self, arg):
        '''Update the local shared directory: setdir <path>'''
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
        '''List files in the local shared directory'''
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
        '''Exit the application'''
        if self.zc:
            self.zc.close()
        return True

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
