# -*- coding: utf-8 -*-
"""Your phone as keyboard: a small web page, served by Lucent Video on your own network, to search and send a title
to the TV. The TV shows a QR code with the address and a 4-digit code; without the code the page does nothing.
It only runs after you opened 'Type with your phone', and only inside your home network. After 5 wrong codes from one
device that device waits a minute, and after three such pauses there is a new code. The page stops by itself when it
was not used for 30 minutes."""
import json
import os
import random
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import xbmc

import util

T = util.T
PORT = 8742
WANT = "lucent.video.remote.want"
CODE = "lucent.video.remote.code"
LAST = "lucent.video.remote.last"
SEEN = "lucent.video.remote.seen"
IDLE = 30 * 60
TRIES, PAUSE, NEW_CODE_AFTER = 5, 60, 3
_server = {"http": None}
_fails = {}              # ip -> {"count", "until", "pauses"}


def touch():
    util.HOME.setProperty(SEEN, str(int(time.time())))


def _blocked(ip):
    entry = _fails.get(ip)
    return bool(entry and entry.get("until", 0) > time.time())


def _wrong(ip):
    entry = _fails.setdefault(ip, {"count": 0, "until": 0, "pauses": 0})
    entry["count"] += 1
    if entry["count"] >= TRIES:
        entry.update(count=0, until=time.time() + PAUSE, pauses=entry["pauses"] + 1)
        if entry["pauses"] >= NEW_CODE_AFTER:
            util.HOME.clearProperty(CODE)              # a new code: the TV screen shows it next time
            entry["pauses"] = 0
            util.log("phone keyboard: too many wrong codes, new code made")


def address():
    ip = xbmc.getInfoLabel("Network.IPAddress") or ""
    if not ip or ip.startswith("127."):
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.connect(("10.255.255.255", 1))
            ip = probe.getsockname()[0]
            probe.close()
        except OSError:
            ip = "127.0.0.1"
    return "http://%s:%d" % (ip, PORT)


def code():
    value = util.HOME.getProperty(CODE)
    if not value:
        value = "%04d" % random.randint(0, 9999)
        util.HOME.setProperty(CODE, value)
    return value


def _search(query):
    import tmdb
    out = []
    for api, kind in (("movie", "movie"), ("tv", "tvshow")):
        for row in (tmdb.get("search/" + api, ttl=3600, query=query, include_adult="false").get("results") or [])[:8]:
            date = row.get("release_date") or row.get("first_air_date") or ""
            out.append({"type": kind, "id": row["id"], "title": row.get("title") or row.get("name") or "", "year": date[:4],
                        "poster": tmdb.image(row.get("poster_path"), "w185"), "pop": row.get("popularity") or 0})
    out.sort(key=lambda r: -r["pop"])
    return out[:12]


def _title(kind, tmdb_id):
    import tmdb
    meta = tmdb.details(kind, tmdb_id) or {}
    return {"type": kind, "id": tmdb_id, "title": meta.get("title"), "year": meta.get("year"), "plot": meta.get("plot"),
            "fanart": meta.get("fanart"), "genres": (meta.get("genres") or [])[:2], "runtime": meta.get("runtime")}


def _do(kind, tmdb_id, what, title):
    if what == "play":
        if kind == "movie":
            xbmc.executebuiltin("PlayMedia(%s)" % util.url_for(action="play", type="movie", tmdb=tmdb_id))
        else:
            xbmc.executebuiltin("ActivateWindow(Videos,%s,return)" % util.url_for(action="seasons", tmdb=tmdb_id))
        done = T("Afspelen", "Play")
    elif what == "watchlist":
        import tracker
        tracker.set_watchlist({"kind": kind, "tmdb": tmdb_id}, True)
        done = T("Op kijklijst", "On watchlist")
    elif what == "tonight" and kind == "movie":
        import prefetch
        prefetch.add_tonight({"type": "movie", "tmdb": tmdb_id})
        done = T("Klaargezet voor vanavond", "Ready for tonight")
    else:
        return False
    util.HOME.setProperty(LAST, "%s · %s" % (title or "", done))
    util.notify(T("Van je telefoon: %s", "From your phone: %s") % (title or ""))
    return True


PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remote.html")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):          # never log addresses or codes
        pass

    def _send(self, status, body, kind="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _ok(self, query):
        return self._check((query.get("code") or [""])[0])

    def _check(self, given):
        ip = self.client_address[0]
        if _blocked(ip):
            return False
        if str(given) == code():
            _fails.pop(ip, None)
            touch()
            return True
        _wrong(ip)
        return False

    def do_GET(self):
        parts = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parts.query)
        if parts.path in ("/", "/index.html"):
            with open(PAGE, encoding="utf-8") as handle:
                page = handle.read().replace("{{LANG}}", "nl" if util.NL else "en")
            return self._send(200, page, "text/html")
        if _blocked(self.client_address[0]):
            return self._send(429, json.dumps({"error": "wait"}))
        if not self._ok(query):
            return self._send(403, json.dumps({"error": "code"}))
        try:
            if parts.path == "/api/search":
                return self._send(200, json.dumps(_search((query.get("q") or [""])[0])))
            if parts.path == "/api/title":
                return self._send(200, json.dumps(_title((query.get("type") or ["movie"])[0], (query.get("id") or [""])[0])))
        except util.HttpError:
            return self._send(502, json.dumps({"error": "tmdb"}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        parts = urllib.parse.urlsplit(self.path)
        length = min(int(self.headers.get("Content-Length") or 0), 4096)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ValueError:
            body = {}
        if _blocked(self.client_address[0]):
            return self._send(429, json.dumps({"error": "wait"}))
        if parts.path != "/api/do" or not self._check(body.get("code")):
            return self._send(403, json.dumps({"error": "code"}))
        ok = _do(body.get("type"), str(body.get("id")), body.get("what"), body.get("title"))
        return self._send(200 if ok else 400, json.dumps({"ok": ok}))


def wanted():
    return util.HOME.getProperty(WANT) == "1"


def start():
    if _server["http"]:
        return
    try:
        server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    except OSError as error:
        util.log("phone keyboard: port %d not free (%s)" % (PORT, type(error).__name__))
        return
    server.daemon_threads = True
    _server["http"] = server
    threading.Thread(target=server.serve_forever, daemon=True).start()
    util.log("phone keyboard is on")


def stop():
    if _server["http"]:
        _server["http"].shutdown()
        _server["http"] = None


def tidy():
    """Called every second by the service: stop the page when nobody used it for 30 minutes."""
    if not _server["http"]:
        return
    try:
        seen = int(util.HOME.getProperty(SEEN) or 0)
    except ValueError:
        seen = 0
    if time.time() - seen > IDLE:
        util.HOME.clearProperty(WANT)
        stop()
        util.log("phone keyboard is off (not used)")


# ------------------------------------------------------------------ the TV screen
def open_screen():
    import dialogs
    import ranking_ui
    util.HOME.setProperty(WANT, "1")
    touch()
    url = "%s/?code=%s" % (address(), code())
    picture = os.path.join(util.PROFILE, "remote_qr.png")
    try:
        import segno
        segno.make(url, error="m").save(picture, scale=12, border=2, dark="#0B1119", light="#FFFFFF")
    except Exception as error:      # noqa: BLE001
        util.log("phone keyboard QR: %s" % type(error).__name__)
    for _ in range(30):              # the service starts the page within a second or two
        if xbmc.Monitor().waitForAbort(0.1):
            return

    class Screen(dialogs.Base):
        def onInit(self):
            self.fill({"rtitle": T("Typ met je telefoon", "Type with your phone"),
                       "rtext": T("Scan de code met de camera van je telefoon. Je telefoon moet op hetzelfde wifi-netwerk zitten.",
                                  "Scan the code with your phone's camera. Your phone must be on the same wifi network."),
                       "qr": picture, "raddr": T("Of ga naar %s en vul code %s in", "Or go to %s and enter code %s") % (address(), code()),
                       "rlast": util.HOME.getProperty(LAST), "rclose": T("Sluiten", "Close")})
            self.setFocusId(10)

        def onClick(self, _control):
            self.close()
    ranking_ui.open_screen(Screen, "lucent_remote.xml")
