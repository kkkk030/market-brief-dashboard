#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
UPDATE_SCRIPT = ROOT / "scripts" / "update_data.py"
DATA_JSON = ROOT / "data" / "dashboard_data.json"

HOST = os.getenv("REFRESH_HOST", "127.0.0.1")
PORT = int(os.getenv("REFRESH_PORT", "8787"))
TOKEN = os.getenv("REFRESH_TOKEN", "")


def run(cmd: list[str], check: bool = True):
    return subprocess.run(cmd, cwd=ROOT, check=check, capture_output=True, text=True)


def refresh(coin: str, publish: bool):
    run(["python3", str(UPDATE_SCRIPT), coin])

    if publish:
        run(["git", "add", "data/dashboard_data.json"], check=False)
        run(["git", "commit", "-m", f"chore: refresh {coin} dashboard snapshot"], check=False)
        run(["git", "push", "origin", "main"], check=False)

    return json.loads(DATA_JSON.read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict):
        b = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type, x-refresh-token")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self._json(200, {"ok": True})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/refresh":
            return self._json(404, {"ok": False, "error": "not found"})

        if TOKEN:
            req_token = self.headers.get("x-refresh-token", "")
            if req_token != TOKEN:
                return self._json(401, {"ok": False, "error": "unauthorized"})

        q = parse_qs(u.query)
        coin = (q.get("coin", ["ETH"])[0] or "ETH").upper()
        if coin not in {"ETH", "XRP"}:
            return self._json(400, {"ok": False, "error": "coin must be ETH or XRP"})

        publish = (q.get("publish", ["1"])[0] == "1")

        try:
            data = refresh(coin, publish)
            self._json(200, {"ok": True, "coin": coin, "publish": publish, "data": data})
        except Exception as e:
            self._json(500, {"ok": False, "error": str(e)})


if __name__ == "__main__":
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"refresh api listening on http://{HOST}:{PORT}")
    srv.serve_forever()
