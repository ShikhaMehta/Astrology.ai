from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from astrology_app.chart_engine import PyHoraNotInstalledError
from astrology_app.models import BirthInput
from astrology_app.pipeline import generate_reading_session
from astrology_app.validation import ValidationError


ASSET_DIR = Path(__file__).resolve().parent / "web_assets"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


class AstrologyWebHandler(BaseHTTPRequestHandler):
    server_version = "AstrologyAiWeb/0.1"

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send_asset("index.html")
            return
        if self.path.startswith("/assets/"):
            self._send_asset(unquote(self.path.removeprefix("/assets/")))
            return
        self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path == "/api/readings":
            self._handle_generate_reading()
            return
        self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _handle_generate_reading(self) -> None:
        try:
            payload = self._read_json_body()
            session = generate_reading_session(
                birth_input=BirthInput(
                    date_of_birth=str(payload.get("date_of_birth", "")).strip(),
                    time_of_birth=str(payload.get("time_of_birth", "")).strip(),
                    birth_place=str(payload.get("birth_place", "")).strip(),
                    timezone=str(payload.get("timezone", "")).strip(),
                ),
                question=str(payload.get("question", "")).strip(),
                client_context=str(payload.get("client_context", "")).strip() or None,
                answer_style=str(payload.get("answer_style", "")).strip() or None,
                requested_chart_keys=_list_from_payload(payload.get("requested_chart_keys")),
                prediction_window=_prediction_window_from_payload(payload),
                comprehensive_reading=bool(payload.get("comprehensive_reading", False)),
                use_openai=bool(payload.get("use_openai", False)),
            )
        except (ValidationError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except PyHoraNotInstalledError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.FAILED_DEPENDENCY)
            return
        except Exception as exc:
            self._send_json(
                {"error": f"Unable to generate reading: {exc}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        context = session.get("interpretation_context", {})
        self._send_json(
            {
                "birth_input": session.get("birth_input", {}),
                "question": session.get("question", ""),
                "client_context": session.get("client_context", ""),
                "category": session.get("category", ""),
                "chart_source": session.get("chart_source", ""),
                "chart_status": session.get("chart_status", ""),
                "engine_notes": session.get("notes", []),
                "prediction_window": session.get("prediction_window"),
                "interpretation_answer": session.get("interpretation_answer", ""),
                "reading_input": context.get("reading_input", {}),
                "evidence_keys": sorted(context.get("evidence", {}).keys()),
                "llm_prompt": session.get("llm_prompt", ""),
                "export_paths": session.get("export_paths", {}),
            }
        )

    def _send_asset(self, relative_path: str) -> None:
        path = (ASSET_DIR / relative_path).resolve()
        try:
            path.relative_to(ASSET_DIR.resolve())
        except ValueError:
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return
        if not path.is_file():
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw_body = self.rfile.read(content_length)
        return json.loads(raw_body.decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), AstrologyWebHandler)
    print(f"Astrology.ai web app running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def _list_from_payload(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _prediction_window_from_payload(payload: dict[str, Any]) -> dict[str, str] | None:
    start_date = str(payload.get("prediction_start", "")).strip()
    end_date = str(payload.get("prediction_end", "")).strip()
    step = str(payload.get("prediction_step", "monthly")).strip() or "monthly"
    if not start_date and not end_date:
        return None
    return {
        "start_date": start_date,
        "end_date": end_date,
        "step": step,
        "source": "web_form",
    }


if __name__ == "__main__":
    run()
