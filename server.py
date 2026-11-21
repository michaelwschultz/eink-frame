"""HTTP control server for triggering e-ink frame changes remotely.

Designed to sit behind Pangolin / Newt so the web UI can tell the Pi to:
- Switch to any frame by name: POST /frame/<name> or POST /frame {"frame": "<name>"}
- Advance to the next frame:   POST /next
- Go back to the previous:     POST /prev (or POST /previous)
- Inspect status / health:     GET /status, GET /health
"""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
from urllib.parse import parse_qs, unquote, urlparse

from fetch_and_display_image import (
    display_frame,
    fetch_frame_list,
    get_current_state,
    is_valid_frame_name,
    read_state,
    set_named_state,
    set_next_state,
)

DEFAULT_HOST = os.environ.get("EINK_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.environ.get("EINK_PORT", "8080"))
API_TOKEN = os.environ.get("EINK_API_TOKEN", "")
CORS_ORIGIN = os.environ.get("EINK_CORS_ORIGIN", "*")


class FrameController:
    """Coordinates frame selection and serialized background e-ink refreshes."""

    def __init__(self):
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._pending_frame = None
        self._stopped = False
        self._state = {
            "busy": False,
            "current_frame": read_state().get("last_frame"),
            "last_updated": None,
            "last_error": None,
        }
        self._worker = threading.Thread(
            target=self._worker_loop, name="epd-worker", daemon=True
        )
        self._worker.start()

    def stop(self):
        """Signal the background worker thread to exit."""
        with self._condition:
            self._stopped = True
            self._condition.notify_all()

    def get_status(self):
        """Return a snapshot of controller and persisted frame state."""
        persisted = read_state()
        with self._lock:
            busy = self._state["busy"]
            return {
                "status": "updating" if busy else "idle",
                "busy": busy,
                "current_frame": self._state["current_frame"] or persisted.get("last_frame"),
                "pending_frame": self._pending_frame,
                "last_displayed": persisted.get("last_displayed", 0),
                "last_updated": self._state["last_updated"],
                "last_error": self._state["last_error"],
            }

    def schedule_step(self, step):
        """Advance (+1) or rewind (-1) through the backend frame list."""
        frame_list = fetch_frame_list()
        with self._condition:
            current_index = get_current_state(frame_list)
            next_index = set_next_state(frame_list, current_index, step=step)
            frame_name = frame_list[next_index]
            self._enqueue_locked(frame_name)
        return {"frame": frame_name, "index": next_index, "frames": frame_list}

    def schedule_frame(self, frame_name):
        """Switch to a specific frame by name."""
        if not is_valid_frame_name(frame_name):
            raise ValueError(f"Invalid frame name: {frame_name!r}")

        frame_list = fetch_frame_list()
        with self._condition:
            index = set_named_state(frame_list, frame_name)
            self._enqueue_locked(frame_name)
        return {"frame": frame_name, "index": index, "frames": frame_list}

    def wait_until_idle(self, timeout=60):
        """Block until the active and pending refreshes finish."""
        with self._condition:
            return self._condition.wait_for(
                lambda: not self._state["busy"] and self._pending_frame is None,
                timeout=timeout,
            )

    def _enqueue_locked(self, frame_name):
        """Queue frame_name as the latest pending target (must hold _condition)."""
        self._pending_frame = frame_name
        self._condition.notify_all()

    def _worker_loop(self):
        """Continuously render the latest pending frame one at a time."""
        while True:
            with self._condition:
                while self._pending_frame is None and not self._stopped:
                    self._condition.wait()
                if self._stopped:
                    return
                target_frame = self._pending_frame
                self._pending_frame = None
                self._state["busy"] = True

            error_msg = None
            success = False
            try:
                success = display_frame(target_frame)
                if not success:
                    error_msg = f"Failed to fetch or display frame '{target_frame}'"
            except Exception as err:  # pylint: disable=broad-exception-caught
                error_msg = str(err)
                print(f"Error displaying frame '{target_frame}': {err}")

            with self._condition:
                self._state["busy"] = False
                if success:
                    self._state["current_frame"] = target_frame
                    self._state["last_updated"] = datetime.now(timezone.utc).isoformat()
                    self._state["last_error"] = None
                else:
                    self._state["last_error"] = error_msg
                self._condition.notify_all()


class ControlHandler(BaseHTTPRequestHandler):
    """HTTP request handler exposing frame control endpoints."""

    controller: FrameController = None
    api_token: str = API_TOKEN
    cors_origin: str = CORS_ORIGIN

    def do_OPTIONS(self):  # pylint: disable=invalid-name
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):  # pylint: disable=invalid-name
        """Serve health and status endpoints."""
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        if not self._is_authorized():
            self._send_json(401, {"error": "Unauthorized"})
            return

        if path in ("/", "/status"):
            self._send_json(200, self.controller.get_status())
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self):  # pylint: disable=invalid-name
        """Handle frame navigation and direct frame selection requests."""
        if not self._is_authorized():
            self._send_json(401, {"error": "Unauthorized"})
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)
        sync = query.get("sync", ["false"])[0].lower() in ("1", "true", "yes")

        if path in ("/next", "/frame/next"):
            result = self.controller.schedule_step(step=1)
            self._respond_after_schedule("next", result, sync)
        elif path in ("/prev", "/previous", "/frame/prev", "/frame/previous"):
            result = self.controller.schedule_step(step=-1)
            self._respond_after_schedule("prev", result, sync)
        elif path == "/frame":
            frame_name = self._read_frame_from_body()
            if not frame_name:
                self._send_json(400, {"error": "Missing 'frame' in JSON body"})
            else:
                self._handle_named_frame(frame_name, sync)
        elif path.startswith("/frame/"):
            frame_name = unquote(path[len("/frame/"):]).strip()
            self._handle_named_frame(frame_name, sync)
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_named_frame(self, frame_name, sync):
        """Validate and schedule a specific frame by name."""
        try:
            result = self.controller.schedule_frame(frame_name)
        except ValueError as err:
            self._send_json(400, {"error": str(err)})
            return
        self._respond_after_schedule("set", result, sync)

    def _respond_after_schedule(self, action, result, sync):
        """Return 202 immediately, or wait for completion if sync=true."""
        payload = {
            "status": "accepted",
            "action": action,
            "frame": result["frame"],
            "index": result["index"],
        }
        if not sync:
            self._send_json(202, payload)
            return

        finished = self.controller.wait_until_idle(timeout=60)
        status = self.controller.get_status()
        if not finished:
            self._send_json(504, {"error": "Timed out waiting for display refresh", **payload})
            return
        if status["last_error"]:
            self._send_json(502, {"error": status["last_error"], **payload})
            return

        payload["status"] = "displayed"
        self._send_json(200, payload)

    def _read_frame_from_body(self):
        """Parse {'frame': '<name>'} from a JSON request body."""
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if content_length <= 0 or content_length > 4096:
            return None
        raw = self.rfile.read(content_length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if isinstance(data, dict):
            value = data.get("frame")
            return value.strip() if isinstance(value, str) else None
        return None

    def _is_authorized(self):
        """Check Bearer or X-API-Key token when api_token is configured."""
        if not self.api_token:
            return True
        auth_header = self.headers.get("Authorization", "")
        if auth_header == f"Bearer {self.api_token}":
            return True
        if self.headers.get("X-API-Key", "") == self.api_token:
            return True
        return False

    def _send_cors_headers(self):
        """Attach CORS headers for browser-based UI requests."""
        if self.cors_origin:
            self.send_header("Access-Control-Allow-Origin", self.cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization, X-API-Key",
            )

    def _send_json(self, status_code, payload):
        """Serialize payload as JSON and write the HTTP response."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ControlHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that carries a reference to its FrameController."""

    def __init__(self, server_address, handler_cls, controller):
        super().__init__(server_address, handler_cls)
        self.controller = controller


def create_server(host=DEFAULT_HOST, port=DEFAULT_PORT, controller=None, api_token=API_TOKEN):
    """Create a configured ControlHTTPServer bound to host:port."""
    active_controller = controller or FrameController()

    class BoundHandler(ControlHandler):
        """Handler bound to a specific FrameController instance."""

    BoundHandler.controller = active_controller
    BoundHandler.api_token = api_token
    return ControlHTTPServer((host, port), BoundHandler, active_controller)


def main():
    """Run the e-ink frame HTTP control server."""
    parser = argparse.ArgumentParser(
        description="HTTP control server for remotely switching e-ink frames."
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Bind host (default: {DEFAULT_HOST})")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Bind port (default: {DEFAULT_PORT})"
    )
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port)
    print(f"eink-frame control server listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down control server...")
    finally:
        server.controller.stop()
        server.server_close()


if __name__ == "__main__":
    main()
