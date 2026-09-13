"""Kleiner lokaler HTTP-Server für die bestehende Berechnungspipeline."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse

from rwa_engine.pipeline import RunRejected, run_dataset
from rwa_engine.workspace import default_workspace

from .catalog import CatalogError, DataCatalog

STATIC_ROOT = Path(__file__).resolve().parent / "static"


class RwaWebServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], data_root: Path):
        super().__init__(address, RwaRequestHandler)
        self.catalog = DataCatalog(data_root)
        self.run_locks: dict[str, Lock] = {}
        self.run_locks_guard = Lock()

    def lock_for(self, dataset_id: str) -> Lock:
        with self.run_locks_guard:
            return self.run_locks.setdefault(dataset_id, Lock())


class RwaRequestHandler(BaseHTTPRequestHandler):
    server: RwaWebServer

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                self._json({"status": "ok"})
            elif parsed.path == "/api/datasets":
                self._json({"datasets": self.server.catalog.datasets()})
            elif parsed.path == "/api/dataset":
                dataset_id = self._one(parse_qs(parsed.query), "dataset")
                self._json(self.server.catalog.detail(dataset_id))
            elif parsed.path == "/files":
                query = parse_qs(parsed.query)
                path = self.server.catalog.file_path(
                    self._one(query, "dataset"),
                    self._one(query, "area"),
                    self._one(query, "file"),
                    query.get("run", [None])[0],
                )
                self._download(path)
            elif parsed.path == "/" or parsed.path.startswith("/static/"):
                self._static("index.html" if parsed.path == "/" else parsed.path.removeprefix("/static/"))
            else:
                self._error(HTTPStatus.NOT_FOUND, "Route nicht gefunden")
        except CatalogError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except (KeyError, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # defensive HTTP boundary; no traceback to browser
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Serverfehler: {exc}")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self._error(HTTPStatus.NOT_FOUND, "Route nicht gefunden")
            return
        try:
            body = self._request_json()
            dataset_id = str(body.get("dataset", ""))
            dataset = self.server.catalog.dataset_path(dataset_id)
            lock = self.server.lock_for(dataset_id)
            if not lock.acquire(blocking=False):
                self._error(HTTPStatus.CONFLICT, "Für diesen Datensatz läuft bereits eine Berechnung")
                return
            try:
                output = run_dataset(dataset)
            finally:
                lock.release()
            self._json(
                {
                    "status": "CALCULATED",
                    "run_id": output.name,
                    "dataset": self.server.catalog.detail(dataset_id),
                }
            )
        except RunRejected as exc:
            self._error(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc))
        except CatalogError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, f"Ungültige Anfrage: {exc}")
        except Exception as exc:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Berechnung fehlgeschlagen: {exc}")

    @staticmethod
    def _one(query: dict[str, list[str]], key: str) -> str:
        values = query.get(key, [])
        if len(values) != 1 or not values[0]:
            raise ValueError(f"Parameter fehlt oder ist mehrdeutig: {key}")
        return values[0]

    def _request_json(self) -> dict[str, Any]:
        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            raise ValueError("Content-Type muss application/json sein")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 64 * 1024:
            raise ValueError("Ungültige Request-Größe")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON-Wurzel muss ein Objekt sein")
        return value

    def _json(self, value: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"status": "ERROR", "message": message}, status)

    def _static(self, name: str) -> None:
        if Path(name).name != name:
            self._error(HTTPStatus.NOT_FOUND, "Datei nicht gefunden")
            return
        path = STATIC_ROOT / name
        if not path.is_file():
            self._error(HTTPStatus.NOT_FOUND, "Datei nicht gefunden")
            return
        payload = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            f"{mime}; charset=utf-8"
            if mime.startswith("text/") or mime == "application/javascript"
            else mime,
        )
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _download(self, path: Path) -> None:
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Lokale Browser-Oberfläche der RWA Engine")
    value.add_argument("--data-root", type=Path, default=default_workspace().runs_root)
    value.add_argument("--host", default="127.0.0.1")
    value.add_argument("--port", type=int, default=8080)
    return value


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    if not 0 <= args.port <= 65535:
        raise SystemExit("Port muss zwischen 0 und 65535 liegen")
    server = RwaWebServer((args.host, args.port), args.data_root)
    host, port = server.server_address[:2]
    print(f"RWA Web App: http://{host}:{port}")
    print(f"Datenwurzel: {server.catalog.data_root}")
    print("Beenden mit Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRWA Web App beendet")
    finally:
        server.server_close()
