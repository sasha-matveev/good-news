from __future__ import annotations

import argparse
import json
import socketserver
import threading
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

EVENTS: list[dict[str, Any]] = []
LOCK = threading.Lock()


def record(event: dict[str, Any]) -> None:
    with LOCK:
        EVENTS.append(event)


class BoundaryHandler(BaseHTTPRequestHandler):
    def do_DELETE(self) -> None:
        if self.path != "/events":
            self.send_error(404)
            return
        with LOCK:
            EVENTS.clear()
        self._json(200, {"cleared": True})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"status": "ok"})
            return
        if parsed.path == "/events":
            backend = parse_qs(parsed.query).get("backend", [None])[0]
            with LOCK:
                events = [event for event in EVENTS if backend is None or event.get("backend") == backend]
            self._json(200, {"events": events})
            return
        if parsed.path.startswith("/source/"):
            backend = self.headers.get("X-Good-News-Contract-Backend")
            record({"kind": "source-fetch", "backend": backend, "path": parsed.path})
            self._send(200, b"<html><body><article>Deterministic fixture</article></body></html>", "text/html")
            return
        self.send_error(404)

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        backend = self.headers.get("X-Good-News-Contract-Backend")
        if self.path.startswith("/gemini/"):
            record({"kind": "gemini", "backend": backend, "request": json.loads(body or b"{}")})
            self._json(
                200,
                {
                    "candidates": [{
                        "content": {
                            "parts": [{
                                "text": json.dumps({
                                    "summary_ru": "Детерминированный ответ",
                                    "topics": ["platform"],
                                    "format": "article",
                                    "technical_depth": "medium",
                                    "verdict": "interesting",
                                    "verdict_reason": "Useful.",
                                    "relevance_score": 8
                                })
                            }]
                        }
                    }]
                },
            )
            return
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: object) -> None:
        self._send(status, json.dumps(payload, sort_keys=True).encode(), "application/json")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class SmtpHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.wfile.write(b"220 contract-smtp ESMTP\r\n")
        message = bytearray()
        data_mode = False
        backend = None
        while line := self.rfile.readline():
            command = line.decode(errors="replace").rstrip()
            if data_mode:
                if command == ".":
                    parsed = BytesParser().parsebytes(bytes(message))
                    record({
                        "kind": "smtp",
                        "backend": backend or parsed.get("X-Good-News-Contract-Backend"),
                        "from": parsed.get("From"),
                        "to": parsed.get("To"),
                        "subject": parsed.get("Subject"),
                    })
                    self.wfile.write(b"250 queued\r\n")
                    data_mode = False
                    continue
                message.extend(line)
            elif command.upper().startswith(("EHLO", "HELO")):
                self.wfile.write(b"250-contract-smtp\r\n250 OK\r\n")
            elif command.upper().startswith("DATA"):
                data_mode = True
                self.wfile.write(b"354 end with <CRLF>.<CRLF>\r\n")
            elif command.upper().startswith("XBACKEND "):
                backend = command.split(" ", 1)[1]
                self.wfile.write(b"250 OK\r\n")
            elif command.upper().startswith("QUIT"):
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 OK\r\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--http-port", type=int, default=8090)
    parser.add_argument("--smtp-port", type=int, default=2525)
    args = parser.parse_args()
    http = ThreadingHTTPServer(("0.0.0.0", args.http_port), BoundaryHandler)
    smtp = socketserver.ThreadingTCPServer(("0.0.0.0", args.smtp_port), SmtpHandler)
    threading.Thread(target=smtp.serve_forever, daemon=True).start()
    http.serve_forever()


if __name__ == "__main__":
    main()

