from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def _slugify(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    return slug or "track"


def _track(query: str, suffix: int) -> dict[str, object]:
    title = query.strip() or "System Test Song"
    slug = _slugify(title)
    return {
        "id": f"system-{slug}-{suffix}",
        "name": title if suffix == 1 else f"{title} Remix",
        "artists": [{"name": "System Test Artist"}],
        "duration_ms": 180000 if suffix == 1 else 200000,
        "album": {
            "name": "System Test Album",
            "images": [{"url": f"https://example.test/system-track-{suffix}.jpg"}],
        },
        "external_urls": {"spotify": f"https://example.test/tracks/{slug}-{suffix}"},
    }


class _Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/api/token":
            self._send_json(404, {"detail": "Not found"})
            return
        self._send_json(
            200,
            {
                "access_token": "system-test-search-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/v1/search":
            self._send_json(404, {"detail": "Not found"})
            return
        query = parse_qs(parsed.query).get("q", [""])[0]
        self._send_json(
            200,
            {"tracks": {"items": [_track(query, 1), _track(query, 2)]}},
        )

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9090"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    server.serve_forever()
