"""CI stand-in for TMDb: streaming services, their lists, details and pictures."""
import json
import struct
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer


def png(rgb, w=300, h=300):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


COLOURS = {"n": (200, 20, 30), "d": (20, 40, 160), "p": (10, 140, 200), "x": (90, 110, 140)}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/t/p/"):
            name = path.rsplit("/", 1)[-1]
            return self.send(png(COLOURS.get(name[:1], COLOURS["x"])), "image/png")
        if "/watch/providers/" in path:
            return self.send(json.dumps({"results": [
                {"provider_id": 8, "provider_name": "Netflix", "logo_path": "/n.png", "display_priorities": {"US": 1, "NL": 1}},
                {"provider_id": 337, "provider_name": "Disney Plus", "logo_path": "/d.png", "display_priorities": {"US": 2, "NL": 2}},
                {"provider_id": 119, "provider_name": "Prime Video", "logo_path": "/p.png", "display_priorities": {"US": 3, "NL": 3}}]}).encode(), "application/json")
        if "/discover/" in path:
            tv = "/tv" in path
            res = [{"id": 1000 + i, ("name" if tv else "title"): f"{'Serie' if tv else 'Film'} {i}", "overview": "plot",
                    ("first_air_date" if tv else "release_date"): "2026-10-01", "vote_average": 7.1, "vote_count": 321,
                    "poster_path": f"/x{i}.png", "backdrop_path": f"/x{i}b.png"} for i in range(1, 21)]
            return self.send(json.dumps({"results": res}).encode(), "application/json")
        return self.send(json.dumps({"images": {"logos": []}, "genres": [{"name": "Drama"}], "runtime": 100, "vote_count": 321,
                                     "production_companies": []}).encode(), "application/json")


HTTPServer(("127.0.0.1", 8765), H).serve_forever()
