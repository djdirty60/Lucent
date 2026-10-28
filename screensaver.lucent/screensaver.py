# -*- coding: utf-8 -*-
"""Lucent screensaver: slowly zooming key art with the title logo and genres bottom left.

Pictures come from TMDB (trending films / series) or from the Kodi library. Two slots (a and b) take turns;
the window XML fades one out through black and the other in, and zooms it slowly.
"""
import json
import random
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()
PATH = ADDON.getAddonInfo("path")
TMDB = "https://api.themoviedb.org/3/"
IMG = "https://image.tmdb.org/t/p/"
KEY = "9f3ca569aa46b6fb13931ec96ab8ae7e"       # the public key Seren also uses by default
LANG = "nl-NL" if xbmc.getLanguage(xbmc.ISO_639_1) == "nl" else "en-US"


def log(text):
    xbmc.log(f"[screensaver.lucent] {text}", xbmc.LOGINFO)


def seren_key():
    try:
        return xbmcaddon.Addon("plugin.video.seren").getSetting("tmdb.apikey") or KEY
    except Exception:  # noqa: BLE001 - Seren not installed
        return KEY


def tmdb(path, **params):
    params["api_key"] = seren_key()
    params.setdefault("language", LANG)
    request = urllib.request.Request(f"{TMDB}{path}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "screensaver.lucent"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def pick_logo(images):
    logos = [x for x in (images or {}).get("logos") or [] if x.get("file_path") and not x["file_path"].lower().endswith(".svg")]
    for lang in ("nl", "en", None):
        for logo in logos:
            if logo.get("iso_639_1") == lang:
                return f"{IMG}w500{logo['file_path']}"
    return f"{IMG}w500{logos[0]['file_path']}" if logos else ""


# ----------------------------------------------------------------------------- where the pictures come from
def trending(kind):
    """[(kind, tmdb id)] of what is popular right now."""
    out = []
    for page in (1, 2):
        try:
            for entry in tmdb(f"trending/{kind}/week", page=page).get("results") or []:
                if entry.get("backdrop_path"):
                    out.append((kind, entry["id"]))
        except Exception as error:  # noqa: BLE001
            log(f"trending {kind}: {error}")
            break
    return out


def tmdb_item(kind, tmdb_id):
    data = tmdb(f"{kind}/{tmdb_id}", append_to_response="images", include_image_language="nl,en,null")
    if not data.get("backdrop_path"):
        return None
    return {
        "fanart": f"{IMG}original{data['backdrop_path']}",
        "logo": pick_logo(data.get("images")),
        "title": data.get("title") or data.get("name") or "",
        "genres": "  ·  ".join(g["name"] for g in (data.get("genres") or [])[:3]),
    }


def library_items():
    """Items of the Kodi library that have fanart: [(None, dict)]."""
    out = []
    for method, key, field in (("VideoLibrary.GetMovies", "movies", "movies"), ("VideoLibrary.GetTVShows", "tvshows", "tvshows")):
        query = {"jsonrpc": "2.0", "id": 1, "method": method, "params": {"properties": ["art", "genre", "title"]}}
        try:
            result = json.loads(xbmc.executeJSONRPC(json.dumps(query))).get("result", {}).get(field) or []
        except Exception as error:  # noqa: BLE001
            log(f"library {key}: {error}")
            continue
        for entry in result:
            art = entry.get("art") or {}
            if art.get("fanart"):
                out.append((None, {"fanart": art["fanart"], "logo": art.get("clearlogo", ""), "title": entry.get("title", ""),
                                   "genres": "  ·  ".join((entry.get("genre") or [])[:3])}))
    return out


def build_queue(source):
    if source == 3:
        return library_items()
    queue = []
    if source in (0, 1):
        queue += trending("movie")
    if source in (0, 2):
        queue += trending("tv")
    if not queue:                          # offline: use the library instead
        return library_items()
    return queue


# ----------------------------------------------------------------------------- the window
class Screensaver(xbmcgui.WindowXMLDialog):
    class ExitMonitor(xbmc.Monitor):
        def __init__(self, callback):
            super().__init__()
            self.callback = callback

        def onScreensaverDeactivated(self):  # noqa: N802 - Kodi callback name
            self.callback()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stop = False
        self.monitor = None

    def onInit(self):  # noqa: N802
        self.monitor = self.ExitMonitor(self.exit)
        self.setProperty("showgenres", "1" if ADDON.getSettingBool("genres") else "")
        self.setProperty("showclock", "1" if ADDON.getSettingBool("clock") else "")
        self.run()

    def onAction(self, action):  # noqa: N802
        self.exit()

    def exit(self):
        self.stop = True
        self.close()

    def show(self, slot, item):
        # restart the slow zoom and drift of this slot: switch it off while it is hidden, then on again
        self.clearProperty(f"{slot}.go")
        xbmc.Monitor().waitForAbort(0.2)
        self.setProperty(f"{slot}.fanart", item["fanart"])
        self.setProperty(f"{slot}.logo", item["logo"])
        self.setProperty(f"{slot}.title", item["title"])
        self.setProperty(f"{slot}.genres", item["genres"])
        self.setProperty("slot", slot)
        self.setProperty(f"{slot}.go", "1")

    def run(self):
        seconds = max(8, ADDON.getSettingInt("seconds") or 18)
        queue = build_queue(ADDON.getSettingInt("source"))
        if not queue:
            log("nothing to show")
            self.exit()
            return
        random.shuffle(queue)
        monitor = xbmc.Monitor()
        slot, index, shown = "a", 0, 0
        while not self.stop and not monitor.abortRequested():
            kind, ref = queue[index % len(queue)]
            index += 1
            try:
                item = ref if kind is None else tmdb_item(kind, ref)
            except Exception as error:  # noqa: BLE001 - skip this one
                log(f"{kind} {ref}: {error}")
                item = None
                if monitor.waitForAbort(1):
                    break
                if index > len(queue) * 2 and not shown:
                    break
                continue
            if not item:
                continue
            self.show(slot, item)
            shown += 1
            slot = "b" if slot == "a" else "a"
            waited = 0.0
            while waited < seconds and not self.stop and not monitor.abortRequested():
                if monitor.waitForAbort(0.5):
                    break
                waited += 0.5
        self.exit()


if __name__ == "__main__":
    window = Screensaver("screensaver-lucent.xml", PATH, "default", "")
    window.doModal()
    del window
