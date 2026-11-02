"""Vercel serverless entry point: runs the same upload handler as the local server."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit_ui_server import AuditUIHandler as handler  # noqa: E402,F401
