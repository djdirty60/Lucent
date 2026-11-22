"""CI stand-in for TMDb: streaming services, their lists, details and pictures."""
import json
import os
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
        if path.startswith("/repo/"):                         # 2.1.33: the test repository (ci/updtest/make.py)
            f = os.path.join("/tmp/ci/repo", path[len("/repo/"):])
            if os.path.exists("/tmp/ci/repo/ready") and os.path.basename(f) in ("addons.xml", "addons.xml.md5"):
                f = f.replace("addons.xml", "addons_new.xml")
            if os.path.isfile(f):
                with open(f, "rb") as fh:
                    return self.send(fh.read(), "application/zip" if f.endswith(".zip") else "text/xml")
            self.send_response(404); self.end_headers(); return
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
        if "/trending/" in path:                             # screensaver 1.2.0
            tv = "/tv/" in path
            res = [{"id": 3000 + i + (100 if tv else 0), "backdrop_path": f"/{'rgbcm'[i % 5]}b{i}.png"} for i in range(4)]
            return self.send(json.dumps({"results": res if "page=1" in self.path else []}).encode(), "application/json")
        if path.rstrip("/").split("/")[-1].isdigit() and path.split("/")[2] in ("movie", "tv") and int(path.rstrip("/").split("/")[-1]) >= 3000:
            tid = int(path.rstrip("/").split("/")[-1])
            tv = path.split("/")[2] == "tv"
            return self.send(json.dumps({"id": tid, ("name" if tv else "title"): f"Saver {'Show' if tv else 'Film'} {tid}",
                                         "backdrop_path": f"/rb{tid}.png", "overview": " ".join(f"Part {n}: a man walks into a quiet town and finds out that the mine everyone lives on hides a secret." for n in range(1, 11)) if os.path.exists("/tmp/ci/longplot") else "A man walks into a quiet town and finds out that the mine everyone lives on hides a secret. Made up for the screenshots.",
                                         "vote_average": 7.4, "runtime": 112, "release_date": "2020-05-01", "first_air_date": "2021-01-01",
                                         "genres": [{"name": "Western"}, {"name": "Drama"}], "images": {"logos": []}}).encode(), "application/json")
        if "/search/person" in path:                         # 3.1.0: the Actors row of the search screen
            return self.send(json.dumps({"results": [{"id": 31 + i, "name": n, "profile_path": f"/{n[0].lower()}p.png"}
                                                     for i, n in enumerate(["Anna Actor", "Bram Bakker", "Carla Cast"])]}).encode(), "application/json")
        if "/search/tv" in path:
            q = urllib.parse.unquote_plus(self.path.split("query=", 1)[-1].split("&")[0])
            if q.startswith("Future"):                          # 2.1.16: a running season, episodes 8 and 9 still to come
                return self.send(json.dumps({"results": [{"id": 1600, "name": q, "first_air_date": "2010-01-01"}]}).encode(), "application/json")
            # 2.1.13 (#19 Millennium): two series with the same name; the old one first, so a pick by name alone is wrong
            return self.send(json.dumps({"results": [{"id": 1499, "name": q, "first_air_date": "1996-10-25"},
                                                     {"id": 1500, "name": q, "first_air_date": "2010-03-21"}]}).encode(), "application/json")
        if "/tv/1600/season/" in path:
            return self.send(json.dumps({"episodes": [{"episode_number": n, "name": f"Ep {n}", "episode_type": "standard",
                                                        "air_date": "2026-11-%02d" % n if n <= 7 else "2027-01-%02d" % n} for n in range(1, 10)]}).encode(), "application/json")
        if "/tv/1499/season/" in path:                        # the old series: 22 episodes from 1997
            return self.send(json.dumps({"episodes": [{"episode_number": n, "name": f"Ep {n}", "air_date": "1997-11-%02d" % n} for n in range(1, 23)]}).encode(), "application/json")
        if "/season/" in path:                                # a season with 10 episodes
            return self.send(json.dumps({"episodes": [{"episode_number": n, "name": f"Ep {n}", "air_date": "2026-11-01",
                                                        "episode_type": "finale" if n == 10 else "standard"} for n in range(1, 11)]}).encode(), "application/json")
        if path.endswith("/reviews"):                        # 2.1.30: the Reviews tab
            lang = "nl" if "language=nl" in self.path else "en"
            res = [] if lang == "nl" else [
                {"id": "r1", "author": "marieke_film", "author_details": {"rating": 8}, "created_at": "2026-11-12T10:00:00Z",
                 "content": "A slow start, but the last three episodes make up for everything. The **lead** is quiet and exactly right, and the harbour gives the whole series a mood of its own.\r\n\r\nSecond paragraph of a long review, so the screen has something to scroll."},
                {"id": "r2", "author": "Northlight", "author_details": {"rating": 6}, "created_at": "2026-11-09T10:00:00Z",
                 "content": "Nicely shot, but the story stays on the surface. Fine for an evening, not more than that."}]
            return self.send(json.dumps({"results": res, "total_results": len(res)}).encode(), "application/json")
        if path.startswith("/trakt/search/tmdb/"):
            return self.send(json.dumps([{"movie": {"ids": {"trakt": 4242}}, "show": {"ids": {"trakt": 4242}}}]).encode(), "application/json")
        if path.startswith("/trakt/") and "/comments/" in path:
            res = [{"comment": "Do not read on: the brother was hiding in the lighthouse the whole time, and the last scene shows it.", "spoiler": True,
                    "created_at": "2026-11-03T10:00:00Z", "user": {"username": "j.devries"}, "user_stats": {"rating": 9}},
                   {"comment": "Great!", "spoiler": False, "created_at": "2026-11-02T10:00:00Z", "user": {"username": "short"}, "user_stats": {}},
                   {"comment": "The ending had me thinking for days. Not perfect, but it stays with you, and the music fits every scene.", "spoiler": False,
                    "created_at": "2026-11-01T10:00:00Z", "user": {"username": "Ferryman"}, "user_stats": {"rating": 7}}]
            return self.send(json.dumps(res).encode(), "application/json")
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
        # 3.0.10: cinema rows, TMDb account, person page with credits
        def films(n, base=5000):
            return [{"id": base + i, "title": f"Bioscoopfilm {i}", "overview": "plot", "release_date": "2026-11-20",
                     "vote_average": 7.0 + i / 10, "vote_count": 100, "popularity": 50 - i,
                     "poster_path": f"/x{i}.png", "backdrop_path": f"/x{i}b.png"} for i in range(1, n + 1)]
        if path.endswith("/movie/now_playing") or path.endswith("/movie/upcoming"):
            return self.send(json.dumps({"results": films(12), "total_pages": 1}).encode(), "application/json")
        if path.endswith("/authentication/token/new"):
            return self.send(json.dumps({"success": True, "request_token": "tok123"}).encode(), "application/json")
        if path.endswith("/3/account"):
            return self.send(json.dumps({"id": 7, "username": "wilfried"}).encode(), "application/json")
        if "/3/account/7/" in path:
            return self.send(json.dumps({"results": films(6, 6000)}).encode(), "application/json")
        if "/3/person/" in path and path.rstrip("/").split("/")[-1].isdigit():
            credits = [{"id": 901, "media_type": "movie", "title": "Lib Film", "release_date": "2000-01-01", "popularity": 99,
                        "poster_path": "/x1.png", "character": "Hero"}] + \
                      [{"id": 7000 + i, "media_type": "movie", "title": f"Other Film {i}", "release_date": "2010-01-01",
                        "popularity": 50 - i, "poster_path": f"/x{i}.png"} for i in range(2, 8)]
            return self.send(json.dumps({"id": 31, "name": "Anna Actor", "birthday": "1980-05-01", "biography": "An actor.",
                                         "combined_credits": {"cast": credits, "crew": []}}).encode(), "application/json")
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
        main = {"images": {"logos": []}, "genres": [{"name": "Drama"}], "runtime": 100, "vote_count": 321,
                "production_companies": [], "release_dates": rel,
                "status": "Ended" if tid == 1499 else "Returning Series"}
        if "keywords" in self.path:                          # 3.0.10: the extras of the info page
            main["keywords"] = {("results" if "/tv/" in path else "keywords"): [{"id": 9, "name": "heist"}, {"id": 10, "name": "bank robbery"}]}
            main["release_dates"] = {"results": [{"iso_3166_1": "NL", "release_dates": [{"type": 3, "certification": "16"}]}]}
            main["content_ratings"] = {"results": [{"iso_3166_1": "NL", "rating": "12"}]}
            main["next_episode_to_air"] = {"air_date": "2026-11-27", "season_number": 3, "episode_number": 5}
            main["overview"] = "Een man loopt een stil dorp binnen en ontdekt dat de mijn waar iedereen van leeft een geheim verbergt."
        return self.send(json.dumps(main).encode(), "application/json")

    def do_POST(self):
        path = self.path.split("?")[0]
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if path.endswith("/validate_with_login"):
            if body.get("username") == "wilfried" and body.get("password") == "goed":
                return self.send(json.dumps({"success": True, "request_token": body.get("request_token")}).encode(), "application/json")
            self.send_response(401)
            self.end_headers()
            return None
        if path.endswith("/session/new"):
            return self.send(json.dumps({"success": True, "session_id": "sess1"}).encode(), "application/json")
        return self.send(b"{}", "application/json")

    def do_DELETE(self):
        return self.send(json.dumps({"success": True}).encode(), "application/json")


HTTPServer(("127.0.0.1", 8765), H).serve_forever()
