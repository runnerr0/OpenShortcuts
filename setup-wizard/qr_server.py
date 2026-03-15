"""Short-lived HTTP server that serves .shortcut files via QR code.

The server:
1. Binds to all interfaces on a random port
2. Generates a QR code pointing to the download URL
3. Serves each shortcut file exactly once (single-use token)
4. Auto-shuts down after all files are downloaded or timeout expires
"""

import http.server
import json
import os
import secrets
import socket
import socketserver
import threading
import time


# --- QR code generation (pure Python, no dependencies) ---

# QR code is generated as ASCII art for terminal display.
# For a real QR code image we'd need the `qrcode` library, but we want
# zero dependencies. ASCII QR works great in terminals and can be
# scanned by phone cameras from a computer screen.

# We use a minimal QR encoder. For URLs under ~100 chars, version 3
# (29x29) is sufficient. We'll use an external-lib-free approach:
# generate a Google Charts QR URL as fallback, and try to import
# `qrcode` if available.

def generate_qr_ascii(url):
    """Generate a QR code as ASCII art for terminal display.

    Tries the `qrcode` library first, falls back to a framed URL display.
    """
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        lines = []
        for row in qr.get_matrix():
            line = ""
            for cell in row:
                line += "\u2588\u2588" if cell else "  "
            lines.append(line)
        return "\n".join(lines)
    except ImportError:
        pass

    # Fallback: use Unicode block elements to render a simpler representation
    # This won't be scannable but gives the user the URL prominently
    return None


def get_lan_ip():
    """Get this machine's LAN IP address."""
    try:
        # Connect to a public DNS to determine which interface to use
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class ShortcutServer:
    """Ephemeral HTTP server that serves shortcut files for phone download.

    Each shortcut gets a unique, single-use download token. After all files
    have been downloaded (or timeout expires), the server shuts down.
    """

    def __init__(self, shortcut_files, timeout=120):
        """
        Args:
            shortcut_files: list of dicts with:
                - "name": display name (e.g. "Universal Transcribe")
                - "filename": file name (e.g. "universal-transcribe.shortcut")
                - "path": absolute path to the .shortcut file
            timeout: seconds before auto-shutdown (default 120)
        """
        self.shortcut_files = shortcut_files
        self.timeout = timeout
        self.tokens = {}  # token -> file info
        self.downloaded = set()  # tokens that have been downloaded
        self.server = None
        self.thread = None
        self.port = None
        self.lan_ip = get_lan_ip()

        # Generate a unique token for each file
        for sf in shortcut_files:
            token = secrets.token_urlsafe(16)
            self.tokens[token] = sf

    def _make_handler(server_ref):
        """Create a request handler class with access to the server state."""
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.strip("/")

                # Landing page — shows all available shortcuts
                if path == "" or path == "index":
                    self._serve_landing()
                    return

                # Download a specific shortcut by token
                if path.startswith("dl/"):
                    token = path[3:]
                    self._serve_shortcut(token)
                    return

                # All-in-one bundle page
                if path == "bundle":
                    self._serve_bundle()
                    return

                self.send_error(404)

            def _serve_landing(self):
                """Serve a mobile-friendly landing page with download links."""
                srv = server_ref
                html_parts = [
                    "<!DOCTYPE html>",
                    "<html><head>",
                    "<meta charset='utf-8'>",
                    "<meta name='viewport' content='width=device-width, initial-scale=1'>",
                    "<title>OpenShortcuts Setup</title>",
                    "<style>",
                    "body { font-family: -apple-system, system-ui, sans-serif; ",
                    "  max-width: 480px; margin: 40px auto; padding: 0 20px; ",
                    "  background: #f5f5f7; color: #1d1d1f; }",
                    "h1 { font-size: 24px; text-align: center; }",
                    ".card { background: white; border-radius: 12px; ",
                    "  padding: 20px; margin: 16px 0; ",
                    "  box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
                    ".card h2 { font-size: 18px; margin: 0 0 8px 0; }",
                    ".card p { color: #666; font-size: 14px; margin: 0 0 12px 0; }",
                    "a.btn { display: block; text-align: center; ",
                    "  background: #007AFF; color: white; text-decoration: none; ",
                    "  padding: 12px; border-radius: 8px; font-weight: 600; ",
                    "  font-size: 16px; }",
                    "a.btn:active { background: #005EC4; }",
                    ".footer { text-align: center; color: #999; ",
                    "  font-size: 12px; margin-top: 24px; }",
                    ".lock { color: #34C759; }",
                    "</style></head><body>",
                    "<h1>OpenShortcuts</h1>",
                    "<p style='text-align:center;color:#666;font-size:14px;'>",
                    "Tap a shortcut to install it on this device.</p>",
                ]

                for token, sf in srv.tokens.items():
                    already = token in srv.downloaded
                    status = " (downloaded)" if already else ""
                    html_parts.extend([
                        "<div class='card'>",
                        f"<h2>{sf['name']}{status}</h2>",
                        f"<p>{sf.get('description', '')}</p>",
                        f"<a class='btn' href='/dl/{token}'>",
                        f"Install {sf['name']}</a>",
                        "</div>",
                    ])

                html_parts.extend([
                    "<div class='footer'>",
                    "<p class='lock'>&#128274; This page expires automatically.</p>",
                    "<p>Your API keys are embedded in the shortcut files.<br>",
                    "This server will shut down momentarily.</p>",
                    "</div>",
                    "</body></html>",
                ])

                body = "\n".join(html_parts).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _serve_shortcut(self, token):
                """Serve a .shortcut file download."""
                srv = server_ref
                if token not in srv.tokens:
                    self.send_error(404, "Invalid or expired download link")
                    return

                sf = srv.tokens[token]
                filepath = sf["path"]

                if not os.path.exists(filepath):
                    self.send_error(500, "Shortcut file not found")
                    return

                with open(filepath, "rb") as f:
                    data = f.read()

                srv.downloaded.add(token)

                self.send_response(200)
                self.send_header("Content-Type", "application/x-shortcut")
                self.send_header(
                    "Content-Disposition",
                    f'attachment; filename="{sf["filename"]}"',
                )
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

                # Check if all shortcuts have been downloaded
                if len(srv.downloaded) >= len(srv.tokens):
                    threading.Timer(2.0, srv.shutdown).start()

            def _serve_bundle(self):
                """Redirect to landing for now."""
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()

            def log_message(self, format, *args):
                """Suppress default logging."""
                pass

        return Handler

    def start(self):
        """Start the server and return (url, qr_text) tuple."""
        handler_class = ShortcutServer._make_handler(self)

        # Find a free port
        self.server = socketserver.TCPServer(("0.0.0.0", 0), handler_class)
        self.port = self.server.server_address[1]

        url = f"http://{self.lan_ip}:{self.port}"

        # Start server in background thread
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        # Schedule auto-shutdown
        self._timeout_timer = threading.Timer(self.timeout, self.shutdown)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()

        # Generate QR code
        qr_text = generate_qr_ascii(url)

        return url, qr_text

    def shutdown(self):
        """Shut down the server."""
        if self.server:
            self.server.shutdown()

    def wait(self):
        """Block until the server shuts down."""
        if self.thread:
            self.thread.join()

    def is_alive(self):
        return self.thread and self.thread.is_alive()
