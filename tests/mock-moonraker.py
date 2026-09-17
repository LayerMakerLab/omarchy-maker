#!/usr/bin/env python3
"""A stand-in for a Klipper printer's Moonraker API, for testing the Printers widget without a printer.

    tests/mock-moonraker.py --port 7125 --name Voron

Answers the endpoints the widget reads, in Moonraker's documented shapes
(https://moonraker.readthedocs.io/en/latest/external_api/). Test controls:

    curl -X POST 'localhost:7125/mock/start?file=parts/cube.gcode&seconds=120&at=0.4'
    curl -X POST localhost:7125/mock/fail
    curl -X POST localhost:7125/mock/cancel
    curl -X POST localhost:7125/mock/shutdown      # Klipper reports an MCU shutdown
    curl -X POST localhost:7125/mock/ready
"""
import argparse, json, math, random, struct, time, zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

STATE = {"state": "standby", "file": "", "seconds": 120.0, "started": 0.0, "paused_at": 0.0, "paused_total": 0.0,
         "message": "", "klippy": "ready", "api_key": ""}

def png(size, rgb):
    raw = b""
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            edge = x < 4 or y < 4 or x >= size - 4 or y >= size - 4
            c = tuple(int(v * 0.6) for v in rgb) if edge else rgb
            row += bytes(c)
        raw += bytes(row)
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")

def elapsed():
    if STATE["state"] not in ("printing", "paused", "complete", "error", "cancelled"): return 0.0
    end = STATE["paused_at"] if STATE["state"] == "paused" else time.time()
    if STATE["state"] in ("complete", "error", "cancelled"): end = STATE["ended"]
    return max(0.0, end - STATE["started"] - STATE["paused_total"])

LOOP = {"seconds": 0.0}

def tick():
    if STATE["state"] == "printing" and elapsed() >= STATE["seconds"]:
        STATE["ended"] = STATE["started"] + STATE["paused_total"] + STATE["seconds"]
        STATE["state"] = "complete"
    # demo mode: rest a minute after each print, then start the next one
    if LOOP["seconds"] and STATE["state"] in ("complete", "standby") and time.time() - STATE.get("ended", 0) > 60:
        STATE.update(state="printing", file="demo/benchy_0.2mm_PLA.gcode", seconds=LOOP["seconds"], started=time.time(), paused_total=0.0, message="")

def status():
    tick()
    e = elapsed()
    running = STATE["state"] in ("printing", "paused")
    progress = min(1.0, e / STATE["seconds"]) if STATE["file"] else 0.0
    hot_target = 215.0 if running else 0.0
    bed_target = 60.0 if running else 0.0
    layers = 100
    return {
        "webhooks": {"state": STATE["klippy"], "state_message": "Printer is ready" if STATE["klippy"] == "ready" else "MCU 'mcu' shutdown: Timer too close"},
        "print_stats": {"filename": STATE["file"], "total_duration": e + 5, "print_duration": e, "filament_used": 1234.5 * progress,
                        "state": STATE["state"], "message": STATE["message"],
                        "info": {"total_layer": layers if STATE["file"] else None, "current_layer": int(progress * layers) if STATE["file"] else None}},
        "virtual_sdcard": {"progress": progress, "is_active": STATE["state"] == "printing", "file_position": int(progress * 100000)},
        "display_status": {"progress": progress, "message": None},
        "extruder": {"temperature": (hot_target or 24.0) + random.uniform(-0.6, 0.6), "target": hot_target, "power": 0.4 if running else 0},
        "heater_bed": {"temperature": (bed_target or 23.5) + random.uniform(-0.3, 0.3), "target": bed_target, "power": 0.2 if running else 0},
    }

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if self.server.verbose: print("%.1f %s" % (time.time(), fmt % args), flush=True)

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def authorized(self):
        if not STATE["api_key"]: return True
        if self.headers.get("X-Api-Key") == STATE["api_key"]: return True
        self.send_json(401, {"error": {"code": 401, "message": "Unauthorized"}})
        return False

    def do_GET(self):
        url = urlparse(self.path); q = parse_qs(url.query, keep_blank_values=True)
        if not self.authorized(): return
        if url.path == "/printer/info":
            return self.send_json(200, {"result": {"state": STATE["klippy"], "state_message": "Printer is ready", "hostname": self.server.printer_name.lower(), "software_version": "v0.12.0-mock"}})
        if url.path == "/printer/objects/query":
            if STATE["klippy"] == "disconnected":
                return self.send_json(503, {"error": {"code": 503, "message": "Klippy Host not connected"}})
            wanted = list(q.keys()) or ["print_stats"]
            full = status()
            return self.send_json(200, {"result": {"eventtime": time.monotonic(), "status": {k: full[k] for k in wanted if k in full}}})
        if url.path == "/server/files/metadata":
            name = (q.get("filename") or [""])[0]
            if not name or name != STATE["file"]:
                return self.send_json(404, {"error": {"code": 404, "message": "Metadata not available for " + name}})
            stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            return self.send_json(200, {"result": {"filename": name, "size": 123456, "slicer": "OrcaSlicer", "slicer_version": "2.4.2",
                "estimated_time": STATE["seconds"], "layer_height": 0.2, "object_height": 20.0, "filament_total": 1234.5,
                "thumbnails": [{"width": 32, "height": 32, "size": 900, "relative_path": ".thumbs/%s-32x32.png" % stem},
                               {"width": 300, "height": 300, "size": 9000, "relative_path": ".thumbs/%s-300x300.png" % stem}]}})
        if url.path.startswith("/server/files/gcodes/") and url.path.endswith(".png"):
            size = 300 if "300x300" in url.path else 32
            body = png(size, (43, 140, 124))
            self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        self.send_json(404, {"error": {"code": 404, "message": "Not found"}})

    def do_POST(self):
        url = urlparse(self.path); q = parse_qs(url.query)
        now = time.time()
        if url.path == "/mock/start":
            seconds = float((q.get("seconds") or ["120"])[0])
            at = min(0.99, max(0.0, float((q.get("at") or ["0"])[0])))  # start part-way through, for screenshots
            STATE.update(state="printing", file=(q.get("file") or ["parts/cube.gcode"])[0], seconds=seconds,
                         started=now - at * seconds, paused_total=0.0, message="", klippy="ready")
        elif url.path in ("/mock/fail", "/mock/cancel"):
            tick(); STATE["ended"] = now; STATE["state"] = "error" if url.path.endswith("fail") else "cancelled"
            STATE["message"] = "Heater extruder not heating at expected rate" if url.path.endswith("fail") else ""
        elif url.path in ("/mock/pause", "/printer/print/pause"):
            if STATE["state"] == "printing": STATE.update(state="paused", paused_at=now)
        elif url.path in ("/mock/resume", "/printer/print/resume"):
            if STATE["state"] == "paused": STATE["paused_total"] += now - STATE["paused_at"]; STATE["state"] = "printing"
        elif url.path == "/mock/shutdown": STATE["klippy"] = "shutdown"
        elif url.path == "/mock/disconnect": STATE["klippy"] = "disconnected"
        elif url.path == "/mock/ready": STATE["klippy"] = "ready"
        elif url.path == "/mock/idle": STATE.update(state="standby", file="", message="")
        elif url.path == "/mock/key": STATE["api_key"] = (q.get("value") or [""])[0]
        else: return self.send_json(404, {"error": {"code": 404, "message": "Not found"}})
        self.send_json(200, {"result": "ok"})

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7125)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--name", default="Mock")
    ap.add_argument("--log", action="store_true", help="print every request")
    ap.add_argument("--loop", type=float, default=0, help="keep printing a demo file of this many seconds, forever")
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.printer_name = args.name
    server.verbose = args.log
    LOOP["seconds"] = args.loop
    print("mock moonraker %s on %s:%d" % (args.name, args.bind, args.port), flush=True)
    server.serve_forever()
