"""CI stand-in for TMDb: streaming services, their lists, details and pictures."""
import json
import urllib.parse
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
        if path.startswith("/omdb"):
            if "apikey=badkey" in self.path:
                return self.send(json.dumps({"Response": "False", "Error": "Invalid API key!"}).encode(), "application/json")
            return self.send(json.dumps({"Response": "True", "imdbRating": "6.5", "imdbVotes": "282,345", "Metascore": "81",
                                         "Ratings": [{"Source": "Internet Movie Database", "Value": "6.5/10"},
                                                     {"Source": "Rotten Tomatoes", "Value": "87%"}]}).encode(), "application/json")
        if path.startswith("/mdblist/"):                    # MDBList: /mdblist/imdb/<movie|show>/<tt...>
            if "apikey=badkey" in self.path:
                return self.send(json.dumps({"error": "Invalid API key"}).encode(), "application/json")
            return self.send(json.dumps({"title": "CI", "ratings": [
                {"source": "imdb", "value": 6.5, "score": 65, "votes": 282345},
                {"source": "metacritic", "value": 81, "score": 81, "votes": 30},
                {"source": "metacriticuser", "value": 7.4, "score": 74, "votes": 541},
                {"source": "trakt", "value": 66, "score": 66, "votes": 1200},
                {"source": "tomatoes", "value": 87, "score": 87, "votes": 120},
                {"source": "popcorn", "value": 56, "score": 56, "votes": 250000},
                {"source": "letterboxd", "value": 3.4, "score": 68, "votes": 90000}]}).encode(), "application/json")
        if "/search/tv" in path:
            q = urllib.parse.unquote_plus(self.path.split("query=", 1)[-1].split("&")[0])
            # 2.1.13 (#19 Millennium): two series with the same name; the old one first, so a pick by name alone is wrong
            return self.send(json.dumps({"results": [{"id": 1499, "name": q, "first_air_date": "1996-10-25"},
                                                     {"id": 1500, "name": q, "first_air_date": "2010-03-21"}]}).encode(), "application/json")
        if "/tv/1499/season/" in path:                        # the old series: 22 episodes from 1997
            return self.send(json.dumps({"episodes": [{"episode_number": n, "name": f"Ep {n}", "air_date": "1997-11-%02d" % n} for n in range(1, 23)]}).encode(), "application/json")
        if "/season/" in path:                                # a season with 10 episodes
            return self.send(json.dumps({"episodes": [{"episode_number": n, "name": f"Ep {n}", "air_date": "2026-11-01",
                                                        "episode_type": "finale" if n == 10 else "standard"} for n in range(1, 11)]}).encode(), "application/json")
        if path.endswith("/external_ids"):
            return self.send(json.dumps({"imdb_id": "tt0185937"}).encode(), "application/json")
        if path.startswith("/t/p/"):
            name = path.rsplit("/", 1)[-1]
            return self.send(png(COLOURS.get(name[:1], COLOURS["x"])), "image/png")
        if "/watch/providers/" in path:
            region = "NL" if "watch_region=NL" in self.path else "US"
            names = (["Netflix", "Disney Plus", "HBO Max", "Apple TV Plus", "Videoland", "Amazon Prime Video", "Paramount Plus", "SkyShowtime"]
                     if region == "NL" else
                     ["Amazon Prime Video", "Netflix", "Hulu", "Starz", "Peacock Premium", "MGM Plus", "AMC+", "Discovery+", "Paramount Plus",
                      "Apple TV Plus", "HBO Max", "Disney Plus", "Tubi TV", "Fubo"])
            ids = {"Netflix": 8, "Disney Plus": 337, "HBO Max": 1899, "Apple TV Plus": 350, "Hulu": 15, "Starz": 43, "Paramount Plus": 531,
                   "Peacock Premium": 386, "MGM Plus": 34, "AMC+": 526, "Discovery+": 520}
            return self.send(json.dumps({"results": [{"provider_id": ids.get(n, 900 + i), "provider_name": n, "logo_path": f"/{n[0].lower()}.png",
                                                      "display_priorities": {region: i}} for i, n in enumerate(names)]}).encode(), "application/json")
        if "/search/company" in path:
            q = self.path.split("query=", 1)[-1].split("&")[0]
            hits = [{"id": 1, "name": "Netflix", "logo_path": "/nwide.png"}] if q == "Netflix" else []
            return self.send(json.dumps({"results": hits}).encode(), "application/json")
        if "/discover/" in path:
            tv = "/tv" in path
            res = [{"id": 1000 + i, ("name" if tv else "title"): f"{'Serie' if tv else 'Film'} {i}", "overview": "plot",
                    ("first_air_date" if tv else "release_date"): "2026-10-01", "vote_average": 7.1, "vote_count": 321,
                    "poster_path": f"/x{i}.png", "backdrop_path": f"/x{i}b.png"} for i in range(1, 21)]
            return self.send(json.dumps({"results": res}).encode(), "application/json")
        tid = int(path.rstrip("/").split("/")[3]) if path.count("/") >= 3 and path.split("/")[3].isdigit() else 0
        rel = {"results": [{"iso_3166_1": "US", "release_dates": [{"type": 3, "release_date": "2026-10-01T00:00:00.000Z"},
                                                                  {"type": 4, "release_date": ("2027-01-01" if tid % 2 else "2026-10-15") + "T00:00:00.000Z"}]}]}
        if path.endswith("/release_dates"):
            return self.send(json.dumps(rel).encode(), "application/json")
        return self.send(json.dumps({"images": {"logos": []}, "genres": [{"name": "Drama"}], "runtime": 100, "vote_count": 321,
                                     "production_companies": [], "release_dates": rel}).encode(), "application/json")


HTTPServer(("127.0.0.1", 8765), H).serve_forever()
