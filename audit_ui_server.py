#!/usr/bin/env python3
"""Local web UI for hotel test-case validation. No extra dependencies."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import traceback
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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


class AuditUIHandler(BaseHTTPRequestHandler):
    server_root: Path = ROOT
    temp_uploads: dict[str, Path] = {}  # session_id -> temp_dir

    def log_message(self, fmt: str, *args) -> None:
        print(f"[audit-ui] {self.address_string()} - {fmt % args}")

    def log_error(self, fmt: str, *args) -> None:
        """Override to log errors without HTML output."""
        print(f"[audit-ui ERROR] {fmt % args}", file=sys.stderr)

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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

            if path in ("/api/upload-folder", "/api/upload_folder", "/api/upload_folder.py"):
                self._handle_folder_upload()
                return

            if path != "/api/upload-zip":
                self._send_json(404, {"error": "Not found"})
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
