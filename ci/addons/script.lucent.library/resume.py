# -*- coding: utf-8 -*-
"""Lucent Library: remember where you stopped a film or episode, on this device.

Seren keeps its resume points on Trakt and only uses them when asked, and a library title (a .strm file) gave Kodi
nothing to remember: you always started at the beginning. So while a video plays, its position is written every
few seconds to addon_data/script.lucent.library/resume.json, keyed by what the video is (film: its TMDb / IMDb id;
episode: the series' id + season + episode - the same for a library title, a Seren row or the series page).

  - Stopped between 1 minute and 92 %: the point is kept, and the film / episode in the Kodi library gets it as its
    resume point too (so Kodi shows the progress bar and offers "Resume").
  - Watched to the end: the point is removed.
  - The same title starts again (from the library, a row, Seren ...) and it starts near the beginning: it jumps to
    the saved point, with a short notice. When Seren already resumed it, nothing happens.
"""
import json
import os
import time

import xbmc
import xbmcgui
import xbmcvfs

ADDON_ID = "script.lucent.library"
FILE = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}/resume.json")
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
MIN_POS = 60            # seconds: earlier is not worth remembering
DONE = 92               # percent: later counts as watched
KEEP = 200              # at most this many points are kept (oldest go first)


def log(text):
    xbmc.log(f"[{ADDON_ID}] resume: {text}", xbmc.LOGINFO)


def rpc(method, params=None):
    try:
        res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})))
        return res.get("result") or {}
    except Exception:  # noqa: BLE001
        return {}


def load():
    try:
        with open(FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save(data):
    try:
        if len(data) > KEEP:
            for key in sorted(data, key=lambda k: data[k].get("time", 0))[:len(data) - KEEP]:
                data.pop(key, None)
        os.makedirs(os.path.dirname(FILE), exist_ok=True)
        tmp = FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, FILE)
    except OSError as error:
        log(f"save: {error}")


def ids_key(uniqueid):
    for name in ("tmdb", "imdb", "tvdb", "trakt"):
        value = str((uniqueid or {}).get(name) or "")
        if value and value not in ("0", "None"):
            return f"{name}{value}"
    return ""


def playing_item():
    """(key, info) of the video that plays, or ("", {})."""
    item = (rpc("Player.GetItem", {"playerid": 1, "properties": ["uniqueid", "season", "episode", "tvshowid", "showtitle",
                                                                  "title", "file"]}) or {}).get("item") or {}
    kind = item.get("type") or ""
    ids = ids_key(item.get("uniqueid"))
    if kind == "episode" or (item.get("season", -1) not in (-1, None) and item.get("episode", -1) not in (-1, None) and item.get("showtitle")):
        show_ids = ""
        if item.get("tvshowid", -1) not in (-1, None):              # a library episode: the series' own ids
            show = rpc("VideoLibrary.GetTVShowDetails", {"tvshowid": item["tvshowid"], "properties": ["uniqueid"]}).get("tvshowdetails") or {}
            show_ids = ids_key(show.get("uniqueid"))
        show_ids = show_ids or ids or f"title{(item.get('showtitle') or '').lower()}"
        key = f"ep:{show_ids}:{item.get('season')}:{item.get('episode')}"
        return key, {"kind": "episode", "show": item.get("showtitle"), "season": item.get("season"), "episode": item.get("episode")}
    if ids:
        return f"movie:{ids}", {"kind": "movie", "title": item.get("title")}
    return "", {}


class Keeper:
    """Called from the service: started(), tick() every second, stopped()."""

    def __init__(self, player):
        self.player = player
        self.key, self.info = "", {}
        self.pos = self.total = 0.0
        self.last_write = 0.0
        self.checked = False
        self.since = 0.0

    def started(self):
        self.key, self.info = playing_item()
        self.pos = self.total = 0.0
        self.checked = False
        self.since = time.time()
        log(f"playing {self.key or '(unknown)'}")

    def tick(self):
        if not self.key:
            return
        try:
            if not self.player.isPlayingVideo():
                return
            self.pos, self.total = self.player.getTime(), self.player.getTotalTime()
        except RuntimeError:
            return
        if not self.checked and self.total > 0 and time.time() - self.since > 4:   # Seren / Kodi resume first
            self.checked = True
            self.jump()
        if time.time() - self.last_write > 15:
            self.last_write = time.time()
            self.store()

    def jump(self):
        """Started near the beginning while a point is saved: go there."""
        point = load().get(self.key) or {}
        target = float(point.get("pos") or 0)
        if target < MIN_POS or self.pos > 45 or abs(self.pos - target) < 30:
            return                                   # nothing saved, or Seren / Kodi already resumed it
        if self.total and target > self.total * DONE / 100:
            return
        self.player.seekTime(max(0.0, target - 5))
        mins, secs = divmod(int(target), 60)
        hours, mins = divmod(mins, 60)
        stamp = f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"
        xbmcgui.Dialog().notification("Lucent", (f"Verder vanaf {stamp}" if NL else f"Continuing from {stamp}"),
                                      xbmcgui.NOTIFICATION_INFO, 3000)
        log(f"jumped to {stamp} for {self.key}")

    def store(self, final=False):
        if not self.key or self.total <= 0:
            return
        data = load()
        pct = self.pos / self.total * 100
        if pct >= DONE:
            if data.pop(self.key, None) is not None:
                save(data)
            if final:
                self.library(0, 0)
            return
        if self.pos < MIN_POS:
            return
        data[self.key] = {"pos": round(self.pos, 1), "total": round(self.total, 1), "time": time.time(), **self.info}
        save(data)
        if final:
            self.library(self.pos, self.total)

    def stopped(self):
        if self.key:
            self.store(final=True)
            log(f"stopped {self.key} at {int(self.pos)} of {int(self.total)} s")
        self.key = ""

    def library(self, pos, total):
        """The same point as Kodi's own resume point of the library title (progress bar, 'Resume')."""
        resume = {"position": round(pos, 1), "total": round(total, 1)}
        try:
            if self.info.get("kind") == "movie":
                want = self.key.split(":", 1)[1]
                for m in rpc("VideoLibrary.GetMovies", {"properties": ["uniqueid", "file"]}).get("movies") or []:
                    if ADDON_ID in (m.get("file") or "") and any(f"{k}{v}" == want for k, v in (m.get("uniqueid") or {}).items()):
                        rpc("VideoLibrary.SetMovieDetails", {"movieid": m["movieid"], "resume": resume})
                        return
            elif self.info.get("kind") == "episode":
                _ep, show, season, episode = self.key.split(":", 3)
                for s in rpc("VideoLibrary.GetTVShows", {"properties": ["uniqueid"]}).get("tvshows") or []:
                    if any(f"{k}{v}" == show for k, v in (s.get("uniqueid") or {}).items()):
                        eps = rpc("VideoLibrary.GetEpisodes", {"tvshowid": s["tvshowid"], "season": int(season),
                                                               "properties": ["episode", "file"]}).get("episodes") or []
                        for e in eps:
                            if str(e.get("episode")) == str(episode) and ADDON_ID in (e.get("file") or ""):
                                rpc("VideoLibrary.SetEpisodeDetails", {"episodeid": e["episodeid"], "resume": resume})
                                return
        except Exception as error:  # noqa: BLE001
            log(f"library point: {error}")
