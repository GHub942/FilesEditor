import json
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

if __package__:
    from .file_operations import OperationError, apply_preview, create_preview, preview_response
else:
    from file_operations import OperationError, apply_preview, create_preview, preview_response


WEB_DIR = Path(__file__).resolve().parent
PREVIEWS = {}
PREVIEW_LIFETIME_SECONDS = 900
MAX_REQUEST_BYTES = 5 * 1024 * 1024


class FilesEditorHandler(BaseHTTPRequestHandler):
    server_version = "FilesEditorWeb/1.0"

    def do_GET(self):
        routes = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/extensions": ("index.html", "text/html; charset=utf-8"),
            "/undo": ("index.html", "text/html; charset=utf-8"),
            "/settings": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/locales/en.json": ("locales/en.json", "application/json; charset=utf-8"),
            "/locales/fr.json": ("locales/fr.json", "application/json; charset=utf-8"),
        }
        route = routes.get(urlsplit(self.path).path)
        if route is None:
            self.send_error(404)
            return
        file_name, content_type = route
        try:
            content = (WEB_DIR / file_name).read_bytes()
        except OSError as error:
            self.send_error(500, f"Could not load the web interface: {error}")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if not self._is_local_request():
            self._send_json(403, {"error": "Requests must come from this local web app."})
            return
        try:
            payload = self._read_json()
            route = urlsplit(self.path).path
            if route == "/api/preview":
                self._preview(payload)
            elif route == "/api/apply":
                self._apply(payload)
            else:
                self._send_json(404, {"error": "Endpoint not found."})
        except OperationError as error:
            self._send_json(400, {"error": str(error)})
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Request body must contain valid JSON."})
        except OSError as error:
            self._send_json(500, {"error": f"A file operation failed: {error}"})

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise OperationError("Invalid request size.") from error
        if length < 1 or length > MAX_REQUEST_BYTES:
            raise OperationError("Request body is empty or too large.")
        data = self.rfile.read(length).decode("utf-8")
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise OperationError("Request body must be a JSON object.")
        return payload

    def _preview(self, payload):
        kind = payload.pop("kind", None)
        preview = create_preview(kind, payload)
        preview.created_at = time.monotonic()
        token = secrets.token_urlsafe(24)
        self._purge_expired_previews()
        PREVIEWS[token] = preview
        self._send_json(200, {"previewId": token, **preview_response(preview)})

    def _apply(self, payload):
        token = payload.get("previewId")
        preview = PREVIEWS.pop(token, None) if isinstance(token, str) else None
        if preview is None or time.monotonic() - preview.created_at > PREVIEW_LIFETIME_SECONDS:
            raise OperationError("This preview expired. Preview the changes again before applying them.")
        result = apply_preview(preview, payload.get("backups", {}))
        self._send_json(200, result)

    def _purge_expired_previews(self):
        now = time.monotonic()
        expired = [
            token for token, preview in PREVIEWS.items()
            if now - preview.created_at > PREVIEW_LIFETIME_SECONDS
        ]
        for token in expired:
            del PREVIEWS[token]

    def _is_local_request(self):
        try:
            host = urlsplit("//" + self.headers.get("Host", "")).hostname
            host_port = urlsplit("//" + self.headers.get("Host", "")).port
            origin = urlsplit(self.headers.get("Origin", ""))
        except ValueError:
            return False
        valid_hosts = {"127.0.0.1", "localhost"}
        return (
            host in valid_hosts
            and host_port == self.server.server_port
            and origin.scheme == "http"
            and origin.hostname == host
            and origin.port == self.server.server_port
        )

    def _send_json(self, status, payload):
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(content)

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")

    def log_message(self, format_string, *args):
        print(f"[Files Editor] {self.address_string()} - {format_string % args}")


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), FilesEditorHandler)
    print("Files Editor Web is running at http://127.0.0.1:8765")
    print("Keep this window open while using the app. Press Ctrl+C to stop.")
    try:
        if not webbrowser.open("http://127.0.0.1:8765"):
            print("Could not open a browser automatically. Use the address above.")
    except (OSError, webbrowser.Error) as error:
        print(f"Could not open a browser automatically: {error}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Files Editor Web.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
