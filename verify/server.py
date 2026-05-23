"""HTTP server and request handler for the verification UI."""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .session import VerificationSession

DEFAULT_PORT = 8765

_HTML = (Path(__file__).parent / "ui.html").read_text(encoding="utf-8")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        pass

    def do_GET(self) -> None:
        if self.path == "/":
            self._send_html(_HTML)
        elif self.path == "/api/session":
            session: VerificationSession = self.server.session  # type: ignore[attr-defined]
            self._send_json(session.to_dict())
        elif self.path == "/api/status":
            session = self.server.session  # type: ignore[attr-defined]
            self._send_json(session.status_data())
        elif self.path.startswith("/api/audio"):
            self._proxy_audio()
        else:
            self.send_response(404)
            self.end_headers()

    def _proxy_audio(self) -> None:
        """Proxy audio from the remote listen_url, forwarding Range headers for seeking."""
        from urllib.parse import urlparse, parse_qs
        import requests as req
        query = parse_qs(urlparse(self.path).query)
        urls = query.get("url", [])
        if not urls:
            self.send_response(400)
            self.end_headers()
            return
        url = urls[0]
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; librevox-verify/1.0)",
            }
            if "Range" in self.headers:
                headers["Range"] = self.headers["Range"]
            r = req.get(url, stream=True, timeout=30, headers=headers)
            r.raise_for_status()
            status = 206 if r.status_code == 206 else 200
            self.send_response(status)
            self.send_header("Content-Type", r.headers.get("Content-Type", "audio/mpeg"))
            self.send_header("Accept-Ranges", "bytes")
            for h in ("Content-Length", "Content-Range"):
                if h in r.headers:
                    self.send_header(h, r.headers[h])
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                for chunk in r.iter_content(chunk_size=8192):
                    self.wfile.write(chunk)
            except BrokenPipeError:
                pass  # browser cancelled the request (e.g. during seek)
        except BrokenPipeError:
            pass
        except Exception as exc:
            try:
                self.send_response(502)
                self.end_headers()
                self.wfile.write(str(exc).encode())
            except BrokenPipeError:
                pass

    def do_POST(self) -> None:
        session: VerificationSession = self.server.session  # type: ignore[attr-defined]
        if self.path == "/api/approve":
            session.approve()
            print(f"[verify] approved ({session.approved}/{len(session.chapters)})")
            self._send_json(session.to_dict())
            if session.status != "active":
                threading.Thread(target=self.server.shutdown, daemon=True).start()
        elif self.path == "/api/deny":
            length = int(self.headers.get("Content-Length", 0))
            feedback = json.loads(self.rfile.read(length)) if length else {}
            session.deny(feedback)
            chapter = session.current_chapter()
            print(f"[verify] denied — {chapter.get('chapter_title', '?') if chapter else '?'}")
            self._send_json(session.to_dict())
            if session.status != "active":
                threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()

    def _send_html(self, content: str) -> None:
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_verification(
    candidates: list[dict],
    repo_path: Path,
    verify_file_path: Path,
    override: bool = False,
    port: int = DEFAULT_PORT,
) -> VerificationSession:
    """Start the verification web server, block until done, return the session."""
    session = VerificationSession(candidates, repo_path, verify_file_path, override)

    if not candidates:
        print("No chapters to verify. Run main.py first to generate new chapters.")
        return session

    class _ReuseAddrServer(HTTPServer):
        allow_reuse_address = True

    server = _ReuseAddrServer(("localhost", port), _Handler)
    server.session = session  # type: ignore[attr-defined]

    url = f"http://localhost:{port}"
    print(f"Verification UI: {url}")
    print("Waiting for your input in the browser... (Ctrl-C to abort)")

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    webbrowser.open(url)
    server_thread.join()

    return session
