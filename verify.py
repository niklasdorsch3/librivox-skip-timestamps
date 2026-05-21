#!/usr/bin/env python3
"""Verification Script — browser UI for confirming pipeline output before PR submission."""

import argparse
import json
import random
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

import repository

CHAPTERS_TO_VERIFY_FILE = Path("chapters_to_verify.json")
REPOSITORY_FILE = Path("repository.json")
REQUIRED_VERIFICATIONS = 10
DEFAULT_PORT = 8765

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LibriVox Verification</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; color: #222; }
    h1 { font-size: 1.4rem; margin-bottom: 0.5rem; }
    .progress { color: #666; font-size: 0.9rem; margin-bottom: 1rem; }
    .card { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 1.25rem; margin: 1rem 0; }
    .card h2 { margin: 0 0 0.5rem; font-size: 1.1rem; }
    .card p { margin: 0.25rem 0; font-size: 0.95rem; }
    .card a { color: #0d6efd; word-break: break-all; }
    .skip-time { font-size: 1.1rem; font-weight: bold; margin: 0.5rem 0; }
    .outlier { background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; padding: 0.5rem 0.75rem; margin: 0.5rem 0; font-weight: 600; }
    audio { width: 100%; margin: 0.75rem 0; }
    .btn-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin: 0.75rem 0; }
    button { padding: 0.6rem 1.25rem; font-size: 0.95rem; border: none; border-radius: 5px; cursor: pointer; }
    .btn-approve { background: #198754; color: #fff; font-size: 1rem; padding: 0.75rem 2rem; }
    .btn-deny { background: #dc3545; color: #fff; font-size: 1rem; padding: 0.75rem 2rem; }
    .btn-before { background: #0d6efd; color: #fff; }
    .btn-seek { background: #6c757d; color: #fff; }
    .message { padding: 1rem; border-radius: 8px; margin: 1rem 0; font-size: 1rem; }
    .msg-success { background: #d1e7dd; color: #0a3622; border: 1px solid #a3cfbb; }
    .msg-error { background: #f8d7da; color: #58151c; border: 1px solid #f1aeb5; }
    .msg-info { background: #cff4fc; color: #055160; border: 1px solid #9eeaf9; }
    #done { display: none; }
    .spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid #f3f3f3; border-top: 3px solid #0d6efd; border-radius: 50%; animation: spin 1s linear infinite; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    #loading { display: none; margin: 1rem 0; font-size: 1rem; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
  </style>
</head>
<body>
  <h1>LibriVox Verification</h1>
  <div class="progress" id="progress"></div>

  <div id="verify">
    <div class="card">
      <h2 id="book-title"></h2>
      <p id="chapter-label"></p>
      <p><a id="listen-url" href="" target="_blank"></a></p>
      <p class="skip-time">Skip to: <span id="skip-seconds"></span>s</p>
      <div id="outlier" class="outlier" style="display:none;"></div>
    </div>
    <audio id="player" controls></audio>
    <div class="btn-row">
      <button class="btn-before" onclick="playBefore()" id="btn-before">Play from 5s before</button>
      <button class="btn-seek" onclick="seekToSkip()" id="btn-seek">Seek to skip time</button>
    </div>
    <div id="loading"><span class="spinner"></span> Processing...</div>
    <div class="btn-row">
      <button class="btn-approve" onclick="doAction('approve')" id="btn-approve">Approve ✓</button>
      <button class="btn-deny" onclick="doAction('deny')" id="btn-deny">Deny ✗</button>
    </div>
  </div>

  <div id="done">
    <div id="done-msg" class="message"></div>
    <div id="chapter-details" style="display: none; margin-top: 2rem;">
      <h2>Chapter Details</h2>
      <div class="card">
        <p><strong>Title:</strong> <span id="detail-title"></span></p>
        <p><strong>Chapter:</strong> <span id="detail-chapter"></span></p>
        <p><strong>Listen URL:</strong> <a id="detail-url" href="" target="_blank"></a></p>
        <p><strong>Skip Time (detected):</strong> <span id="detail-skip"></span>s</p>
        <p><strong>Anchor Word:</strong> <span id="detail-anchor"></span></p>
        <p><strong>Is Outlier:</strong> <span id="detail-outlier"></span></p>
      </div>
    </div>
  </div>

  <script>
    var skipTime = 0;

    function render(data) {
      try {
        console.log('render() called, status:', data.status);
        if (data.status !== 'active') {
          console.log('Status not active, showing done message');
          document.getElementById('verify').style.display = 'none';
          document.getElementById('done').style.display = 'block';
          var cls = data.status === 'complete' ? 'msg-success'
                  : data.status === 'denied'   ? 'msg-error'
                  : 'msg-info';
          var el = document.getElementById('done-msg');
          el.className = 'message ' + cls;
          el.textContent = data.message || 'Done.';

          if (data.status === 'denied' && data.chapter) {
            try {
              var ch = data.chapter;
              console.log('Showing chapter details for denied chapter:', ch);
              document.getElementById('chapter-details').style.display = 'block';
              document.getElementById('detail-title').textContent = ch.title || '';
              document.getElementById('detail-chapter').textContent = 'Chapter ' + ch.chapter_index + ': ' + ch.chapter_title;
              var urlEl = document.getElementById('detail-url');
              urlEl.href = ch.listen_url;
              urlEl.textContent = ch.listen_url;
              document.getElementById('detail-skip').textContent = ch.exact_audio_skip_seconds.toFixed(2);
              document.getElementById('detail-anchor').textContent = ch.detected_disclaimer_anchor_word || '(none)';
              document.getElementById('detail-outlier').textContent = ch.is_outlier ? 'Yes' : 'No';
              console.log('Chapter details displayed');
            } catch (e) {
              console.error('Error displaying chapter details:', e);
            }
          }
          return;
        }
        var ch = data.chapter;
        skipTime = ch.exact_audio_skip_seconds;
        console.log('Updating progress to chapter', data.current_index + 1, 'of', data.total);
        document.getElementById('progress').textContent =
          'Chapter ' + (data.current_index + 1) + ' of ' + data.total
          + ' — Approved: ' + data.approved;
        console.log('Updated progress');
        document.getElementById('book-title').textContent = ch.title || '';
        document.getElementById('chapter-label').textContent =
          'Chapter ' + ch.chapter_index + ': ' + ch.chapter_title;
        var urlEl = document.getElementById('listen-url');
        urlEl.href = ch.listen_url;
        urlEl.textContent = ch.listen_url;
        document.getElementById('skip-seconds').textContent = skipTime.toFixed(2);
        var outlierEl = document.getElementById('outlier');
        if (ch.is_outlier) {
          outlierEl.textContent = '[OUTLIER: high delta flagged during pipeline run — verify carefully]';
          outlierEl.style.display = '';
        } else {
          outlierEl.style.display = 'none';
        }
        var audio = document.getElementById('player');
        audio.src = '/api/audio?url=' + encodeURIComponent(ch.listen_url);
        console.log('Set audio src, calling load()');
        audio.load();
        audio.addEventListener('loadedmetadata', function() {
          audio.currentTime = skipTime;
        }, {once: true});
        console.log('render() complete');
      } catch (err) {
        console.error('Error in render():', err);
      }
    }

    function load() {
      fetch('/api/session').then(function(r) { return r.json(); }).then(render).catch(function(err) { console.error('Load error:', err); });
    }

    function doAction(action) {
      console.log('doAction called with:', action);
      document.getElementById('loading').style.display = 'block';
      document.getElementById('btn-approve').disabled = true;
      document.getElementById('btn-deny').disabled = true;
      document.getElementById('btn-before').disabled = true;
      document.getElementById('btn-seek').disabled = true;
      var url = '/api/' + action;
      console.log('Fetching:', url);
      fetch(url, {method: 'POST'})
        .then(function(r) {
          console.log('Got response, status:', r.status);
          if (!r.ok) {
            console.error('Response not ok:', r.statusText);
            throw new Error('Response status: ' + r.status);
          }
          return r.json();
        })
        .then(function(data) {
          console.log('Got JSON data:', data);
          render(data);
          document.getElementById('loading').style.display = 'none';
          document.getElementById('btn-approve').disabled = false;
          document.getElementById('btn-deny').disabled = false;
          document.getElementById('btn-before').disabled = false;
          document.getElementById('btn-seek').disabled = false;
        })
        .catch(function(err) {
          console.error('Caught error:', err);
          document.getElementById('loading').style.display = 'none';
          document.getElementById('btn-approve').disabled = false;
          document.getElementById('btn-deny').disabled = false;
          document.getElementById('btn-before').disabled = false;
          document.getElementById('btn-seek').disabled = false;
        });
    }

    function playBefore() {
      var audio = document.getElementById('player');
      audio.currentTime = Math.max(0, skipTime - 5);
      audio.play();
    }

    function seekToSkip() {
      var audio = document.getElementById('player');
      audio.currentTime = skipTime;
    }

    load();
  </script>
</body>
</html>"""


def load_verification_candidates(
    repo_path: Path, verify_file_path: Path
) -> list[dict]:
    """Return chapters from this run with full metadata merged from repository."""
    if not verify_file_path.exists():
        print(f"Error: {verify_file_path} not found. Run main.py first.")
        sys.exit(1)

    listen_urls: list[str] = json.loads(verify_file_path.read_text())
    listen_url_set = set(listen_urls)

    repo = repository.load(repo_path)
    candidates = []

    for book_data in repo.values():
        book_meta = book_data.get("book_metadata", {})
        for chapter in book_data.get("chapters", []):
            if chapter["listen_url"] in listen_url_set:
                candidates.append({**chapter, "title": book_meta.get("title", "")})

    return candidates


def select_chapters(
    candidates: list[dict], max_count: int = REQUIRED_VERIFICATIONS
) -> list[dict]:
    """Select up to max_count chapters: all outliers first, then random non-outliers."""
    outliers = [c for c in candidates if c.get("is_outlier")]
    non_outliers = [c for c in candidates if not c.get("is_outlier")]

    random.shuffle(outliers)
    random.shuffle(non_outliers)

    selected = outliers[:max_count]
    remaining = max_count - len(selected)
    if remaining > 0:
        selected.extend(non_outliers[:remaining])

    return selected


class _VerificationSession:
    """State for a single verification run."""

    def __init__(
        self,
        chapters: list[dict],
        repo_path: Path,
        override: bool = False,
    ) -> None:
        self.chapters = chapters
        self.repo_path = repo_path
        self.override = override
        self.current_index = 0
        self.approved = 0
        self.status = "active"
        self.message = ""

    def current_chapter(self) -> Optional[dict]:
        if self.current_index < len(self.chapters):
            return self.chapters[self.current_index]
        return None

    def approve(self) -> None:
        if self.status != "active":
            return
        chapter = self.chapters[self.current_index]
        repository.mark_verified(chapter["listen_url"], self.repo_path)
        self.approved += 1
        self.current_index += 1
        if self.current_index >= len(self.chapters):
            self._check_completion()

    def deny(self) -> None:
        self.status = "denied"
        self.message = (
            "Verification failed: Pipeline produced incorrect result. "
            "File a bug and fix the pipeline before rerunning."
        )

    def _check_completion(self) -> None:
        if self.approved >= REQUIRED_VERIFICATIONS or (
            self.override and self.approved >= 1
        ):
            self.status = "complete"
            self.message = (
                f"Verified {self.approved} chapters from "
                f"{len(self.chapters)} total new entries. Ready to submit."
            )
        else:
            self.status = "not_enough"
            self.message = (
                f"Only {self.approved} chapters verified (need 10 minimum). "
                f"Run `python verify.py --override` to create a PR anyway. "
                f"10 verified entries ensures quality — proceeding with fewer is not recommended."
            )


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        pass

    def do_GET(self) -> None:
        if self.path == "/":
            self._send_html(_HTML)
        elif self.path == "/api/session":
            session: _VerificationSession = self.server.session  # type: ignore[attr-defined]
            self._send_json({
                "status": session.status,
                "current_index": session.current_index,
                "total": len(session.chapters),
                "approved": session.approved,
                "chapter": session.current_chapter(),
                "message": session.message,
            })
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
            headers = {}
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
        session: _VerificationSession = self.server.session  # type: ignore[attr-defined]
        if self.path == "/api/approve":
            session.approve()
            response = {
                "status": session.status,
                "current_index": session.current_index,
                "total": len(session.chapters),
                "approved": session.approved,
                "chapter": session.current_chapter(),
                "message": session.message,
            }
            if session.status != "active":
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            self._send_json(response)
        elif self.path == "/api/deny":
            session.deny()
            response = {
                "status": session.status,
                "current_index": session.current_index,
                "total": len(session.chapters),
                "approved": session.approved,
                "chapter": session.current_chapter(),
                "message": session.message,
            }
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            self._send_json(response)
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
    override: bool = False,
    port: int = DEFAULT_PORT,
) -> _VerificationSession:
    """Start the verification web server, block until done, return the session."""
    selected = select_chapters(candidates)
    session = _VerificationSession(selected, repo_path, override)

    if not selected:
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


def _offer_pr(session: _VerificationSession) -> None:
    """Offer to commit repository.json and open a PR via gh."""
    titles = sorted({ch.get("title", "") for ch in session.chapters if ch.get("title")})
    title_str = ", ".join(titles[:3])
    if len(titles) > 3:
        title_str += f" and {len(titles) - 3} more"

    commit_msg = f"Add {session.approved} verified chapters from {title_str}"
    pr_title = f"Add {session.approved} verified LibriVox chapters"
    pr_body = (
        "## Summary\n\n"
        f"- Verified {session.approved} chapters from {len(session.chapters)} new entries\n"
        f"- Books: {title_str}\n\n"
        "## Verification\n\n"
        "All entries manually confirmed correct via `verify.py`."
    )

    answer = input("\nCreate PR now? (y/n): ").strip().lower()
    if answer == "y":
        try:
            subprocess.run(["git", "add", "repository.json"], check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(
                ["gh", "pr", "create", "--title", pr_title, "--body", pr_body],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(f"Error creating PR: {exc}")
            sys.exit(1)
    else:
        print("\nRun these commands to submit manually:")
        print("  git add repository.json")
        print(f"  git commit -m {json.dumps(commit_msg)}")
        print(f"  gh pr create --title {json.dumps(pr_title)} --body '...'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify pipeline output before submitting a PR."
    )
    parser.add_argument(
        "--override",
        action="store_true",
        help="Allow PR creation with fewer than 10 verified chapters (but >= 1).",
    )
    parser.add_argument("--repo-path", type=Path, default=REPOSITORY_FILE)
    parser.add_argument("--verify-file", type=Path, default=CHAPTERS_TO_VERIFY_FILE)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    candidates = load_verification_candidates(args.repo_path, args.verify_file)
    session = run_verification(candidates, args.repo_path, args.override, args.port)

    if session.status == "denied":
        print(f"\n{session.message}")
        sys.exit(1)

    if session.status == "not_enough":
        print(f"\n{session.message}")
        sys.exit(0)

    if session.status == "complete":
        print(f"\n{session.message}")
        _offer_pr(session)


if __name__ == "__main__":
    main()
