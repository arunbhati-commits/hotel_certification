#!/usr/bin/env python3
"""Local web UI for hotel test-case validation. No extra dependencies."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
import shutil
import sys
import tempfile
import traceback
import urllib.error
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import auth

ROOT = Path(__file__).resolve().parent
UI_DIR = ROOT / "audit_ui"

sys.path.insert(0, str(ROOT))
from validate_hotel_test_cases import (  # noqa: E402
    apply_cancel_coverage,
    discover_cases,
    to_json_report,
    validate_case,
)


import re as _re


_SERVER_BINARY_SUFFIXES = {
    ".jpg",".jpeg",".png",".gif",".bmp",".ico",".svg",".webp",".tiff",
    ".mp3",".mp4",".mov",".avi",".mkv",".wav",".flac",
    ".pdf",".doc",".docx",".xls",".xlsx",".ppt",".pptx",
    ".zip",".rar",".7z",".tar",".gz",".bz2",
    ".exe",".dll",".so",".dylib",".bin",".dat",".db",".sqlite",".mdb",
    ".class",".jar",".pyc",".o",".a",
}


def _has_data_files(d: Path) -> bool:
    """True if directory d directly contains at least one readable (non-binary) file."""
    try:
        for p in d.iterdir():
            if not p.is_file() or p.name.startswith('.') or p.name.startswith('~'):
                continue
            if p.suffix.lower() not in _SERVER_BINARY_SUFFIXES:
                return True
    except PermissionError:
        pass
    return False


def _is_test_case_dir_by_name(name: str) -> bool:
    """True if folder name looks like a test case by name."""
    n = name.lower()
    return (
        name.startswith("Test Case") or
        ("test" in n and "case" in n) or
        bool(_re.match(r'^\d{1,3}$', name)) or                   # pure number: 1, 2, 01
        bool(_re.match(r'^(tc|case|test)[_\s-]?\d+', n)) or       # TC1, Case1, Test_01
        bool(_re.match(r'^(hotel|booking|scenario)[_\s-]?\d+', n)) # Hotel1, Scenario_01
    )


def _is_case_dir(p: Path) -> bool:
    """True if path is a directory that looks like a test case folder
    (by name OR by containing data files directly)."""
    if not p.is_dir() or p.name.startswith('.'):
        return False
    return _is_test_case_dir_by_name(p.name) or _has_data_files(p)


def find_test_cases_root(base_dir: Path) -> Path | None:
    """Return the directory whose direct children are test-case folders.

    Detection is content-based when name-based matching fails — any directory
    that directly contains JSON/TXT files is treated as a test case folder.
    This supports any folder naming convention.
    """
    # Check base_dir itself first
    try:
        cases = [p for p in base_dir.iterdir() if _is_case_dir(p)]
        if cases:
            return base_dir
    except PermissionError:
        pass

    # BFS to find the nearest containing directory
    queue = [base_dir]
    visited: set[Path] = {base_dir}
    while queue:
        current = queue.pop(0)
        try:
            children = [p for p in current.iterdir()
                        if p.is_dir() and not p.name.startswith('.')]
        except PermissionError:
            continue
        for child in children:
            if _is_case_dir(child):
                return current
            if child not in visited:
                visited.add(child)
                queue.append(child)
    return None


def _parse_multipart(content_type: str, body: bytes, fields: dict | None = None) -> list[tuple[str, bytes]]:
    """Parse multipart/form-data. Returns list of (relative_path, content).
    Plain text fields (no filename) are stored in `fields` when it is given."""
    boundary = None
    for part in content_type.split(';'):
        part = part.strip()
        if part.lower().startswith('boundary='):
            boundary = part[9:].strip('"').strip("'")
            break
    if not boundary:
        return []

    delimiter = ('--' + boundary).encode()
    files: list[tuple[str, bytes]] = []

    parts = body.split(delimiter)
    for raw in parts[1:]:
        if raw.lstrip(b'\r\n').startswith(b'--'):
            break
        # split headers from body
        sep = b'\r\n\r\n' if b'\r\n\r\n' in raw else b'\n\n'
        if sep not in raw:
            continue
        header_bytes, content = raw.split(sep, 1)
        content = content.rstrip(b'\r\n')

        header_str = header_bytes.decode('utf-8', errors='replace')
        filename = None
        field_name = None
        for line in header_str.splitlines():
            line = line.strip()
            if line.lower().startswith('content-disposition:'):
                for token in line.split(';'):
                    token = token.strip()
                    if token.lower().startswith('filename='):
                        filename = token[9:].strip('"').strip("'")
                    elif token.lower().startswith('name='):
                        field_name = token[5:].strip('"').strip("'")
        if filename:
            files.append((filename, content))
        elif field_name and fields is not None:
            fields[field_name] = content.decode('utf-8', errors='replace').strip()[:200]
    return files


def build_audit_payload(root: Path, only_case: str | None, strict_option_id: bool) -> dict:
    case_dirs = discover_cases(root, only_case)
    results = [validate_case(c, strict_option_id=strict_option_id) for c in case_dirs]
    apply_cancel_coverage(results)
    rows = to_json_report(results)

    errors = warnings = passed = failed = 0
    for row in rows:
        errs = sum(1 for f in row["findings"] if f["severity"] == "ERROR")
        warns = sum(1 for f in row["findings"] if f["severity"] == "WARN")
        errors += errs
        warnings += warns
        if row["status"] == "PASS":
            passed += 1
        else:
            failed += 1

    return {
        "root": str(root),
        "summary": {
            "cases": len(rows),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "warnings": warnings,
        },
        "results": rows,
    }


CERT_CASES = range(1, 15)
CERT_NOTIFY_TO = "aryan.singh@tripjack.com,arun.bhati@tripjack.com"  # comma-separated


def _case_number(name: str) -> int | None:
    """Same rule as the UI: number after case/tc/test, else the last number in the name."""
    m = re.search(r"(?:case|tc|test)[\s_-]*0*(\d{1,2})(?!\d)", name, re.I)
    if m:
        return int(m.group(1))
    nums = re.findall(r"\d{1,2}(?!\d)", name)
    return int(nums[-1]) if nums else None


def all_cases_passed(result: dict) -> bool:
    """True only when every certification case 1-14 is present and PASS."""
    status: dict[int, str] = {}
    for row in result.get("results", []):
        n = _case_number(str(row.get("case", "")))
        if n in CERT_CASES and n not in status:
            status[n] = row.get("status")
    return all(status.get(n) == "PASS" for n in CERT_CASES)


MAILERCLOUD_URL = "https://email-api.mailercloud.com/email-api"


def _ssl_context() -> ssl.SSLContext:
    """python.org Python on macOS ships without CA certs; fall back to the system bundle."""
    paths = ssl.get_default_verify_paths()
    if not (paths.cafile or (paths.capath and os.listdir(paths.capath))) and os.path.exists("/etc/ssl/cert.pem"):
        return ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    return ssl.create_default_context()


def _send_via_mailercloud(api_key: str, sender: str, to: str, reply_to: str, subject: str, text: str) -> None:
    payload = {
        "email": {
            "from": sender,
            "fromName": os.environ.get("MAIL_FROM_NAME", "Tripjack Certification"),
            "subject": subject,
            "text": text,
            "html": "<html><body><pre style=\"font-family:Menlo,Consolas,monospace;font-size:13px\">"
                    + html.escape(text) + "</pre></body></html>",
            "recipients": {"to": [{"name": "Tripjack Certification", "email": to}]},
        },
        "metadata": {"campaignType": "TRANSACTIONAL"},
        "version": "1.0",
    }
    if reply_to:
        payload["email"]["replyTo"] = [reply_to]
    req = urllib.request.Request(
        MAILERCLOUD_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": api_key, "Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "TripjackCertificationV3/1.0"},  # Cloudflare blocks the default Python-urllib agent
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as res:
            print(f"[cert-mail] mailercloud {res.status}: {res.read(300).decode('utf-8', 'replace')}", flush=True)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Mailercloud HTTP {e.code}: {e.read(500).decode('utf-8', 'replace')}") from None


def _send_via_webhook(url: str, partner: dict, outcome: str, to: str, subject: str, text: str) -> None:
    """Post to a Google Apps Script web app that emails from the script owner's Gmail (no SMTP or DNS)."""
    payload = {"to": to, "subject": subject, "text": text, "outcome": outcome, **partner}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "TripjackCertificationV3/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as res:
        body = res.read(300).decode("utf-8", "replace")
    if '"ok":true' not in body.replace(" ", ""):
        raise RuntimeError(f"webhook replied: {body}")


GROUNDMAIL_URL = "https://api.groundmail.dev/emails"
GROUNDMAIL_SANDBOX_FROM = "noreply@mail.groundmail.dev"  # no domain needed; only delivers to the account's own email


def _send_via_groundmail(api_key: str, sender: str, to: str, subject: str, text: str) -> None:
    payload = {
        "from": sender, "to": to, "subject": subject, "text": text,
        "html": "<pre style=\"font-family:Menlo,Consolas,monospace;font-size:13px\">" + html.escape(text) + "</pre>",
    }
    req = urllib.request.Request(
        GROUNDMAIL_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "User-Agent": "TripjackCertificationV3/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as res:
            print(f"[cert-mail] groundmail {res.status}: {res.read(300).decode('utf-8', 'replace')}", flush=True)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Groundmail HTTP {e.code}: {e.read(500).decode('utf-8', 'replace')}") from None


def _send_via_smtp(host: str, user: str, password: str, sender: str, to: str, reply_to: str, subject: str, text: str) -> None:
    port = int(os.environ.get("SMTP_PORT", "587"))
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15, context=_ssl_context()) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls(context=_ssl_context())
            smtp.login(user, password)
            smtp.send_message(msg)


def send_certification_mail(partner: dict, result: dict) -> str:
    """Email Tripjack the partner's details and results.
    Uses Mailercloud when MAILERCLOUD_API_KEY and MAIL_FROM are set, otherwise SMTP
    (SMTP_HOST, SMTP_USER, SMTP_PASS, optional SMTP_PORT / MAIL_FROM). CERT_NOTIFY_TO (comma-separated) overrides the recipients.
    Returns "sent", "not_configured" or "failed"."""
    webhook = os.environ.get("CERT_WEBHOOK_URL")
    groundmail_key = os.environ.get("GROUNDMAIL_API_KEY")
    api_key = os.environ.get("MAILERCLOUD_API_KEY")
    host, user, password = (os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))
    sender = os.environ.get("MAIL_FROM") or user
    use_api = bool(api_key and sender)
    if not webhook and not groundmail_key and not use_api and not (host and user and password):
        print("[cert-mail] mail not configured (set GROUNDMAIL_API_KEY, CERT_WEBHOOK_URL, MAILERCLOUD_API_KEY + MAIL_FROM, or SMTP_*); mail not sent", flush=True)
        return "not_configured"
    recipients = [a.strip() for a in os.environ.get("CERT_NOTIFY_TO", CERT_NOTIFY_TO).split(",") if a.strip()]
    when = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %I:%M %p IST")

    # Status of each certification case 1-14 (a case that was not uploaded counts as failed)
    status: dict[int, str] = {}
    for row in result.get("results", []):
        n = _case_number(str(row.get("case", "")))
        if n in CERT_CASES and n not in status:
            status[n] = row.get("status") or "FAIL"
    passed = sum(1 for n in CERT_CASES if status.get(n) == "PASS")
    not_uploaded = sum(1 for n in CERT_CASES if n not in status)
    failed = len(CERT_CASES) - passed - not_uploaded
    outcome = "passed" if passed == len(CERT_CASES) else f"{passed}/{len(CERT_CASES)} passed"
    counts = f"{passed} passed, {failed} failed" + (f", {not_uploaded} not uploaded" if not_uploaded else "")
    subject = f"Hotel V3 certification {outcome} ({counts}) - {partner.get('company') or 'Unknown company'}"
    text = (
        f"A partner uploaded Hotel API V3 UAT test cases on the Tripjack Certification V3 Hotel checker.\n\n"
        f"RESULT       : {'ALL 14 PASSED - ready for certification' if passed == len(CERT_CASES) else 'NOT READY'}\n"
        f"Passed       : {passed} of {len(CERT_CASES)}\n"
        f"Failed       : {failed}\n"
        + (f"Not uploaded : {not_uploaded}\n" if not_uploaded else "")
        + "\n"
        f"Name         : {partner.get('name', '')}\n"
        f"Company      : {partner.get('company', '')}\n"
        f"TJ user ID   : {partner.get('tjUserId', '')}\n"
        f"Phone        : {partner.get('phone', '')}\n"
        f"Email        : {partner.get('email', '')}"
        + (f"  (signed in with {partner['loginVia']})" if partner.get("loginVia") else "") + "\n"
        f"Checked on   : {when}\n"
        f"Folder       : {result.get('source_folder', '')}\n\n"
        "Results:\n" + "\n".join(f"  Test Case {n}: {status.get(n, 'NOT UPLOADED')}" for n in CERT_CASES) + "\n"
    )
    reply_to = partner.get("email", "")
    sent: list[str] = []
    for to in recipients:  # one mail per recipient, so one bad address cannot block the others
        try:
            if groundmail_key:
                _send_via_groundmail(groundmail_key, os.environ.get("MAIL_FROM") or GROUNDMAIL_SANDBOX_FROM, to, subject, text)
                via = "groundmail"
            elif webhook:
                _send_via_webhook(webhook, partner, outcome, to, subject, text)
                via = "apps-script"
            elif use_api:
                _send_via_mailercloud(api_key, sender, to, reply_to, subject, text)
                via = "mailercloud"
            else:
                _send_via_smtp(host, user, password, sender, to, reply_to, subject, text)
                via = "smtp"
            print(f"[cert-mail] sent to {to} for {partner.get('company')} via {via}", flush=True)
            sent.append(to)
        except Exception as e:  # never fail the upload because of mail
            print(f"[cert-mail] failed for {to}: {e}", flush=True)
    return "sent" if sent else "failed"


class AuditUIHandler(BaseHTTPRequestHandler):
    server_root: Path = ROOT
    temp_uploads: dict[str, Path] = {}  # session_id -> temp_dir

    def log_message(self, fmt: str, *args) -> None:
        print(f"[audit-ui] {self.address_string()} - {fmt % args}")

    def log_error(self, fmt: str, *args) -> None:
        """Override to log errors without HTML output."""
        print(f"[audit-ui ERROR] {fmt % args}", file=sys.stderr)

    def _send_json(self, code: int, payload: dict, cookie: str | None = None) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        else:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _api_route(self) -> str:
        """'login' for /api/login, also when Vercel rewrites it to /api/upload_folder.py?__route=login."""
        parsed = urlparse(self.path)
        route = (parse_qs(parsed.query).get("__route") or [""])[0]
        return route or parsed.path.rstrip("/").rsplit("/", 1)[-1]

    def _user(self) -> dict | None:
        return auth.read_session(self.headers.get("Cookie"))

    def _is_https(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return self.headers.get("X-Forwarded-Proto") == "https" or host not in ("127.0.0.1", "localhost")

    def _auth_get(self, route: str) -> bool:
        if route == "config":
            ids = auth.client_ids()
            self._send_json(200, {"auth": auth.auth_enabled(), "google_client_id": ids["google"],
                                  "microsoft_client_id": ids["microsoft"]})
        elif route == "me":
            user = self._user()
            self._send_json(200 if user else 401, {"user": user} if user else {"error": "Not signed in"})
        else:
            return False
        return True

    def _auth_post(self, route: str) -> bool:
        if route == "login":
            try:
                body = json.loads(self.rfile.read(min(self._get_content_length(), 20000)) or b"{}")
                user = auth.verify_id_token(str(body.get("provider")), str(body.get("id_token", "")), str(body.get("nonce", "")))
            except ValueError as e:
                self._send_json(401, {"error": f"Sign-in failed: {e}"})
                return True
            except Exception as e:
                self._send_json(502, {"error": f"Sign-in could not be checked: {e}"})
                return True
            print(f"[auth] signed in {user['email']} via {user['provider']}", flush=True)
            self._send_json(200, {"user": user}, cookie=auth.session_cookie(auth.make_session(user), self._is_https()))
        elif route == "logout":
            self._send_json(200, {"ok": True}, cookie=auth.session_cookie("", self._is_https(), max_age=0))
        else:
            return False
        return True

    def _get_content_length(self) -> int:
        try:
            return int(self.headers.get("Content-Length", 0))
        except ValueError:
            return 0

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        # Handle cleanup API
        if path == "/api/cleanup":
            try:
                qs = parse_qs(parsed.query)
                session_id = (qs.get("session") or [None])[0]
                if session_id and session_id in self.temp_uploads:
                    temp_dir = self.temp_uploads[session_id]
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    del self.temp_uploads[session_id]
                    self._send_json(200, {"status": "cleaned"})
                else:
                    self._send_json(400, {"error": "Invalid session"})
            except Exception as e:
                self._send_json(500, {"error": f"Cleanup failed: {str(e)}"})
            return

        if path.startswith("/api/") and self._auth_get(self._api_route()):
            return

        # Reject other API paths
        if path.startswith("/api/"):
            self._send_json(404, {"error": f"Not found: {path}"})
            return

        # Handle static files
        if path in ("/", "/index.html"):
            file_path = UI_DIR / "index.html"
        elif path.startswith("/"):
            file_path = (UI_DIR / path.lstrip("/")).resolve()
            if not str(file_path).startswith(str(UI_DIR.resolve())):
                self.send_error(403)
                return
        else:
            self.send_error(404)
            return

        if not file_path.is_file():
            self.send_error(404)
            return

        suffix = file_path.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".zip": "application/zip",
        }.get(suffix, "application/octet-stream")
        self._send_bytes(200, file_path.read_bytes(), ctype)

    def do_POST(self) -> None:
        """Handle ZIP or folder upload."""
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            if path.startswith("/api/") and self._auth_post(self._api_route()):
                return

            if path in ("/api/upload-folder", "/api/upload_folder", "/api/upload_folder.py"):
                if auth.auth_enabled() and not self._user():
                    self._send_json(401, {"error": "Please sign in again."})
                    return
                self._handle_folder_upload()
                return

            if path != "/api/upload-zip":
                self._send_json(404, {"error": "Not found"})
                return

            if auth.auth_enabled() and not self._user():
                self._send_json(401, {"error": "Please sign in again."})
                return

            content_length = self._get_content_length()
            if content_length == 0:
                self._send_json(400, {"error": "No file provided (Content-Length: 0)"})
                return
            
            if content_length > 100 * 1024 * 1024:  # 100MB limit
                self._send_json(413, {"error": "File too large (max 100MB)"})
                return

            # Read the file data
            body = self.rfile.read(content_length)
            
            if not body:
                self._send_json(400, {"error": "Empty file body"})
                return
            
            # Validate it's a ZIP file
            if not body.startswith(b'PK\x03\x04'):
                self._send_json(400, {"error": "Not a valid ZIP file (invalid magic header)"})
                return
            
            # Create temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix="audit_upload_"))
            
            # Save ZIP file
            zip_path = temp_dir / "upload.zip"
            zip_path.write_bytes(body)
            
            # Try to extract
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(temp_dir)
            except zipfile.BadZipFile as e:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self._send_json(400, {"error": f"Invalid ZIP file: {str(e)}"})
                return
            except Exception as e:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self._send_json(400, {"error": f"Failed to extract ZIP: {str(e)}"})
                return
            
            # Find test case folders - use more flexible search
            case_dirs = []
            try:
                # First try direct pattern match
                for item in temp_dir.rglob("Test Case *"):
                    if item.is_dir():
                        case_dirs.append(item)
                
                # If no matches found, provide diagnostic info
                if not case_dirs:
                    # List all directories to understand structure
                    all_dirs = list(temp_dir.rglob("*"))
                    dir_names = [d.name for d in all_dirs if d.is_dir()]
                    
                    # Try case-insensitive search
                    import fnmatch
                    for item in temp_dir.rglob("*"):
                        if item.is_dir() and fnmatch.fnmatch(item.name.lower(), "test case *"):
                            case_dirs.append(item)
            except Exception as e:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self._send_json(400, {"error": f"Failed to scan folders: {str(e)}"})
                return
            
            if not case_dirs:
                # Provide better error message with what was found
                try:
                    # Get immediate subdirectories
                    immediate = [d.name for d in temp_dir.iterdir() if d.is_dir()]
                    # Also check nested one level deeper
                    nested = []
                    for subdir in temp_dir.iterdir():
                        if subdir.is_dir():
                            nested.extend([d.name for d in subdir.iterdir() if d.is_dir()][:5])
                    
                    all_found = immediate + nested
                    found_msg = str(all_found[:10]) if all_found else "None"
                    
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self._send_json(400, {
                        "error": f"No 'Test Case N' folders found. Searched: {found_msg}"
                    })
                except:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self._send_json(400, {"error": "No 'Test Case N' folders found in ZIP"})
                return
            
            # Store session
            session_id = str(temp_dir.name)
            self.temp_uploads[session_id] = temp_dir

            # Use the actual root that contains "Test Case N" folders (handles nested ZIPs)
            actual_root = find_test_cases_root(temp_dir) or temp_dir

            # Run validation
            try:
                result = build_audit_payload(actual_root, None, False)
                result["session_id"] = session_id
                self._send_json(200, result)
            except Exception as e:
                self._send_json(500, {"error": f"Validation failed: {str(e)}"})
            finally:
                # Results are already in the response; never keep partner files on disk
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.temp_uploads.pop(temp_dir.name, None)

        except Exception as e:
            self._send_json(500, {"error": f"Server error: {str(e)}"})

    def _handle_folder_upload(self) -> None:
        """Accept multipart/form-data folder upload (webkitdirectory) and validate."""
        try:
            content_type = self.headers.get("Content-Type", "")
            content_length = self._get_content_length()

            if content_length == 0:
                self._send_json(400, {"error": "No files received"})
                return
            if content_length > 300 * 1024 * 1024:
                self._send_json(413, {"error": "Folder too large (max 300 MB)"})
                return

            body = self.rfile.read(content_length)
            fields: dict = {}
            files = _parse_multipart(content_type, body, fields)
            partner = {k: fields.get(k, "") for k in ("name", "company", "tjUserId", "phone", "email")}
            user = self._user()
            if user:  # the signed-in account is the trusted identity
                partner["email"] = user["email"]
                partner["loginVia"] = user["provider"].title()

            if not files:
                self._send_json(400, {"error": "No files parsed from upload. Ensure the folder contains JSON files."})
                return

            temp_dir = Path(tempfile.mkdtemp(prefix="audit_folder_"))
            try:
                json_count = 0
                for rel_path, content in files:
                    # Sanitise: normalise separators, strip leading slashes, block traversal
                    parts = [p for p in rel_path.replace("\\", "/").split("/") if p and p != ".."]
                    if not parts:
                        continue
                    # Reject known binary/media formats; accept everything else
                    _fname = parts[-1]
                    if _fname.startswith(".") or _fname.startswith("~") or _fname.startswith("$"):
                        continue
                    _ext = _fname.rsplit(".", 1)[-1].lower() if "." in _fname else ""
                    _BINARY = {
                        "jpg","jpeg","png","gif","bmp","ico","svg","webp","tiff",
                        "mp3","mp4","mov","avi","mkv","wav","flac",
                        "pdf","doc","docx","xls","xlsx","ppt","pptx",
                        "zip","rar","7z","tar","gz","bz2",
                        "exe","dll","so","dylib","bin","dat","db","sqlite","mdb",
                        "class","jar","pyc","o","a",
                    }
                    if _ext in _BINARY:
                        continue
                    dest = temp_dir.joinpath(*parts)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(content)
                    json_count += 1

                if json_count == 0:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    received = [r for r, _ in files[:10]]
                    self._send_json(400, {
                        "error": f"No usable files found among the {len(files)} uploaded file(s). "
                                 f"First files received: {received}. "
                                 f"Make sure the folder contains .txt or .json test case files."
                    })
                    return

                # discover_cases is now recursive — pass temp_dir directly;
                # it will find case folders at any nesting depth.
                from validate_hotel_test_cases import discover_cases as _dc
                probe = _dc(temp_dir, None)
                print(f"[folder-upload] saved {json_count} file(s); discovered {len(probe)} case(s): "
                      + ", ".join(c.name for c in probe[:20]))
                if not probe:
                    all_dirs = sorted(
                        p.relative_to(temp_dir).as_posix()
                        for p in temp_dir.rglob("*") if p.is_dir() and not p.name.startswith('.')
                    )[:20]
                    print(f"[folder-upload] dirs in temp: {all_dirs}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self._send_json(400, {
                        "error": (
                            "No test case sub-folders found. "
                            "Upload a folder that contains individual test case "
                            "sub-folders (any naming is accepted — e.g. 'Test Case 1', "
                            "'TC1', '1', 'Case_01', 'TJ test Hotel Case 1', etc.). "
                            "Each sub-folder must contain the JSON/TXT request and "
                            "response files for that test case."
                            + (f"  Folders found: {all_dirs}" if all_dirs else "")
                        )
                    })
                    return

                session_id = temp_dir.name
                self.temp_uploads[session_id] = temp_dir

                result = build_audit_payload(temp_dir, None, False)
                print(f"[folder-upload] audit complete — {result['summary']['cases']} case(s) in response")
                result["session_id"] = session_id
                result["source_folder"] = parts[0] if files else "uploaded"
                result["partner"] = partner
                result["certified"] = all_cases_passed(result)
                # For now mail on every upload; to mail only on 14/14, wrap this in `if result["certified"]:`
                result["certification_mail"] = send_certification_mail(partner, result)
                summary = result["summary"]
                print("[upload] " + json.dumps({**partner, "passed": summary.get("passed"), "failed": summary.get("failed")}), flush=True)
                self._send_json(200, result)

            except Exception as e:
                traceback.print_exc()
                self._send_json(500, {"error": f"Validation failed: {str(e)}"})
            finally:
                # Results are already in the response; never keep partner files on disk
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.temp_uploads.pop(temp_dir.name, None)

        except Exception as e:
            traceback.print_exc()
            self._send_json(500, {"error": f"Server error: {str(e)}"})

    def do_OPTIONS(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Handle OPTIONS for any endpoint
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description="Hotel test-case audit web UI")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--root", type=Path, default=ROOT, help="Test cases root folder")
    parser.add_argument("--no-open", action="store_true", help="Do not open browser")
    args = parser.parse_args()

    if not UI_DIR.is_dir():
        print(f"Missing UI folder: {UI_DIR}", file=sys.stderr)
        return 1

    handler = AuditUIHandler
    handler.server_root = args.root.resolve()

    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Hotel audit UI: {url}")
    print(f"Test cases root: {handler.server_root}")
    print("Press Ctrl+C to stop.")

    if not args.no_open:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
