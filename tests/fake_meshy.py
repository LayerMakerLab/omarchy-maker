"""A stand-in for Meshy's API (https://docs.meshy.ai), for tests: every task finishes on its second status check.

    python3 tests/fake_meshy.py --model open.stl [--repaired closed.stl] [--watertight] [--port 8765]

Then run maker-meshy with MESHY_API_BASE=http://127.0.0.1:PORT MESHY_API_KEY=test-key MESHY_POLL_START=0.2.
"""
import argparse
import http.server
import json
import re
import struct
import sys
import threading
import time
import zlib

KEY = "test-key"
CREATE = {"/openapi/v2/text-to-3d": "text", "/openapi/v1/image-to-3d": "image", "/openapi/v1/multi-image-to-3d": "views",
          "/openapi/v1/print/analyze": "analyze", "/openapi/v1/print/repair": "repair"}


def tiny_png():
    raw = b"\x00\xff\xff\xff"
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class FakeMeshy:
    def __init__(self, model, repaired=None, watertight=False, port=0, fail=False):
        self.files = {"model.stl": model, "repaired.stl": repaired or model, "preview.png": tiny_png()}
        self.watertight, self.fail = watertight, fail
        self.streams, self.streamed = True, 0
        self.calls, self.polls, self.bodies, self.tasks = [], {}, {}, 0
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), self.handler())
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def start(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def task(self, kind, task_id):
        self.polls[task_id] = self.polls.get(task_id, 0) + 1
        if self.polls[task_id] == 1:
            return {"id": task_id, "status": "IN_PROGRESS", "progress": 40}
        if self.fail and kind in ("text", "image", "views"):
            return {"id": task_id, "status": "FAILED", "progress": 0, "task_error": {"message": "The test server said no"}}
        done = {"id": task_id, "status": "SUCCEEDED", "progress": 100}
        if kind in ("text", "image", "views"):
            done.update(model_urls={"stl": self.url + "/files/model.stl", "glb": self.url + "/files/model.glb"},
                        thumbnail_url=self.url + "/files/preview.png", consumed_credits=20)
        elif kind == "analyze":
            closed = self.watertight
            done["printability"] = {"status": "ok" if closed else "warning", "issue_count": 0 if closed else 2,
                                    "metrics": {"is_watertight": closed, "holes": 0 if closed else 1, "non_manifold_edges": 0}}
        elif kind == "repair":
            done.update(model_urls={"stl": self.url + "/files/repaired.stl"}, consumed_credits=10)
        return done

    def handler(self):
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, body, kind="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def stream_task(self, path):
                found = re.match(r"^(/openapi/v[12]/[a-z0-9/-]+?)/([a-z]+-\d+)$", path)
                if not (found and CREATE.get(found.group(1))):
                    return self.reply(404, {"message": "no such task"})
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for task in (fake.task(CREATE[found.group(1)], found.group(2)), fake.task(CREATE[found.group(1)], found.group(2))):
                    brief = task if task["status"] in ("SUCCEEDED", "FAILED") else {k: task[k] for k in ("id", "status", "progress")}
                    self.wfile.write(b"event: message\ndata: " + json.dumps(brief).encode() + b"\n\n")
                    self.wfile.flush()
                    time.sleep(0.05)
                fake.streamed += 1

            def authorized(self):
                if self.headers.get("Authorization") != "Bearer " + KEY:
                    self.reply(401, {"message": "Invalid API key"})
                    return False
                return True

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                fake.calls.append(("POST", self.path, body))
                if not self.authorized():
                    return
                kind = CREATE.get(self.path)
                if not kind:
                    return self.reply(404, {"message": "no such endpoint"})
                fake.tasks += 1
                task_id = "%s-%d" % (kind, fake.tasks)
                fake.bodies[task_id] = body
                self.reply(202, {"result": task_id})

            def do_GET(self):
                fake.calls.append(("GET", self.path, None))
                if self.path.endswith("/stream"):
                    if not fake.streams:
                        return self.reply(404, {"message": "no stream here"})
                    if not self.authorized():
                        return
                    return self.stream_task(self.path[:-len("/stream")])
                if self.path.startswith("/files/"):
                    name = self.path[len("/files/"):]
                    return self.reply(200, fake.files[name], "application/octet-stream") if name in fake.files else self.reply(404, {})
                if not self.authorized():
                    return
                if self.path == "/openapi/v1/balance":
                    return self.reply(200, {"balance": 1000})
                found = re.match(r"^(/openapi/v[12]/[a-z0-9/-]+?)/([a-z]+-\d+)$", self.path)
                if found and CREATE.get(found.group(1)) and found.group(2).startswith(CREATE[found.group(1)] + "-"):
                    return self.reply(200, fake.task(CREATE[found.group(1)], found.group(2)))
                self.reply(404, {"message": "no such task"})

        return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--repaired")
    parser.add_argument("--watertight", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    read = lambda path: open(path, "rb").read() if path else None
    fake = FakeMeshy(read(args.model), read(args.repaired), args.watertight, args.port)
    print(fake.url, flush=True)
    try:
        fake.server.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
