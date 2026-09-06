"""Lightweight HTTP server for the ImpactIQ analyzer API.

Uses only Python standard library (http.server).
Serves both the UI static files and the /api/analyze endpoint.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Ensure the project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analyzer import analyze
from src.ai import explain_analysis, get_ai_status
from src.ai.explanation import _ensure_env_loaded
from src.serializer import serialize_analysis

# Load environment configuration from .env and .env.local if present
_ensure_env_loaded()

DEFAULT_PACKAGE = "demo/OrderProcessing"
DEFAULT_PORT = 8765


# In-memory analysis cache so /api/explain does not re-compute what /api/analyze already computed
_analysis_cache: dict[tuple[str, str, str], dict] = {}


class ImpactIQHandler(SimpleHTTPRequestHandler):
    """Handler that serves the UI and exposes the analyzer API."""

    def __init__(self, *args, **kwargs):
        # Serve files from the ui/ directory
        ui_dir = str(PROJECT_ROOT / "ui")
        super().__init__(*args, directory=ui_dir, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/analyze":
            self._handle_analyze(parsed)
        elif parsed.path == "/api/explain":
            self._handle_explain(parsed)
        elif parsed.path == "/api/ai-status":
            self._handle_ai_status()
        elif parsed.path == "/api/commits":
            self._handle_commits()
        else:
            super().do_GET()

    def _handle_analyze(self, parsed):
        """Run the analyzer and return JSON."""
        params = parse_qs(parsed.query)
        base = params.get("base", [""])[0].strip()
        target = params.get("target", [""])[0].strip()
        package = params.get("package", [DEFAULT_PACKAGE])[0].strip()

        if not base or not target:
            self._json_error(400, "Missing required parameters: base and target")
            return

        cache_key = (base, target, package)
        if cache_key in _analysis_cache:
            self._json_response(200, _analysis_cache[cache_key])
            return

        try:
            result = analyze(
                repository_path=PROJECT_ROOT,
                package_path=package,
                base_revision=base,
                target_revision=target,
            )
            data = serialize_analysis(result)
            _analysis_cache[cache_key] = data
            self._json_response(200, data)
        except Exception as exc:
            self._json_error(500, f"Analysis failed: {exc}")

    def _handle_explain(self, parsed):
        """Return an AI explanation for the analysis."""
        params = parse_qs(parsed.query)
        base = params.get("base", [""])[0].strip()
        target = params.get("target", [""])[0].strip()
        package = params.get("package", [DEFAULT_PACKAGE])[0].strip()

        if not base or not target:
            self._json_error(400, "Missing required parameters: base and target")
            return

        cache_key = (base, target, package)
        data = _analysis_cache.get(cache_key)

        if data is None:
            try:
                result = analyze(
                    repository_path=PROJECT_ROOT,
                    package_path=package,
                    base_revision=base,
                    target_revision=target,
                )
                data = serialize_analysis(result)
                _analysis_cache[cache_key] = data
            except Exception as exc:
                self._json_error(500, f"Analysis failed: {exc}")
                return

        try:
            explanation = explain_analysis(data)
            self._json_response(200, {"explanation": explanation.to_dict()})
        except Exception as exc:
            self._json_error(500, f"Explanation failed: {exc}")

    def _handle_ai_status(self):
        """Return the current AI configuration status."""
        try:
            status = get_ai_status()
            self._json_response(200, status)
        except Exception as exc:
            self._json_error(500, f"Status check failed: {exc}")

    def _handle_commits(self):
        """List available Git commits."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--all", "-50"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            commits = []
            for line in result.stdout.strip().splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    commits.append({
                        "id": parts[0],
                        "label": line,
                        "description": parts[1],
                    })
            self._json_response(200, {"commits": commits})
        except Exception as exc:
            self._json_error(500, f"Unable to list commits: {exc}")

    def _json_response(self, status: int, data: dict):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status: int, message: str):
        self._json_response(status, {"error": message})

    def log_message(self, format, *args):
        """Quieter logging — only show errors and API calls."""
        message = str(args[0]) if args else ""
        if "/api/" in message:
            super().log_message(format, *args)


def main():
    port = int(os.environ.get("IMPACTIQ_PORT", DEFAULT_PORT))
    server = ThreadingHTTPServer(("", port), ImpactIQHandler)
    print(f"ImpactIQ server running at http://localhost:{port}")
    print(f"API:  http://localhost:{port}/api/analyze?base=02ccdc8&target=5d26f89")
    print(f"UI:   http://localhost:{port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
