# -*- coding: utf-8 -*-
"""Lucent: poster focus trailers on the Home screen.

Started once from Home.xml (RunScript(special://skin/scripts/trailers.py)) and keeps
running in the background. When a widget card stays focused for a few seconds, it
looks up the YouTube trailer (ListItem.Trailer, or TMDB) and plays it in a window
on the Home screen through the YouTube add-on. Home.xml shows the video according
to Skin.String(nuvio.posterfocus): window | hero | expand.

Safety: it only ever stops a video it started itself, and only while you are still
on the Home screen; as soon as something else plays, it lets go.
"""
import time
import urllib.parse

import xbmc
import xbmcgui

import info  # TMDB helpers of the info page (same folder)

HOME_ID = 10000
HOME = xbmcgui.Window(HOME_ID)
RUNNING = "nuvio.trailer.service"   # heartbeat: time of the last loop round
PLAYING = "nuvio.trailer.playing"
TICK = 0.25
YT = "plugin://plugin.video.youtube/play/?video_id="
TYPES = ["Trailer", "Teaser", "Clip"]


def log(text):
    xbmc.log(f"[skin.lucent] trailers: {text}", xbmc.LOGINFO)


def label(name):
    return xbmc.getInfoLabel(name)


def skin(name):
    return xbmc.getInfoLabel(f"Skin.String({name})")


class Focus:
    """The card that has focus in a Home widget row, or None."""

    def __init__(self):
        self.row = HOME.getProperty("nuvio.row")
        prefix = f"Container({self.row}).ListItem."
        self.label = label(prefix + "Label")
        self.dbtype = label(prefix + "DBType")
        self.trailer = label(prefix + "Trailer")
        self.tmdb = label(prefix + "UniqueID(tmdb)") or label(prefix + "Property(tmdb_id)")
        self.show_tmdb = label(prefix + "Property(tvshow.tmdb_id)")
        self.key = f"{self.row}|{self.label}|{self.tmdb}|{self.dbtype}"

    def valid(self):
        return bool(self.row and self.label and xbmc.getCondVisibility(f"Control.HasFocus({self.row})"))


def youtube_id(path):
    """Video id from a YouTube plugin path or a youtube.com link, else ''."""
    if not path:
        return ""
    parsed = urllib.parse.urlparse(path)
    query = urllib.parse.parse_qs(parsed.query)
    for name in ("video_id", "videoid", "v"):
        if query.get(name):
            return query[name][0]
    if "youtu.be/" in path:
        return path.rsplit("/", 1)[-1].split("?")[0]
    return ""


def tmdb_trailer(focus):
    kind = "movie" if focus.dbtype == "movie" else "tv" if focus.dbtype in ("tvshow", "season", "episode") else ""
    tmdb_id = focus.tmdb
    if focus.dbtype in ("season", "episode") and focus.show_tmdb:
        tmdb_id = focus.show_tmdb
    if not kind or not tmdb_id.isdigit():
        return ""
    lang = "nl" if xbmc.getLanguage(xbmc.ISO_639_1) == "nl" else "en"
    try:
        videos = info.tmdb(f"{kind}/{tmdb_id}/videos", include_video_language=f"{lang},en,null").get("results") or []
    except Exception as error:  # noqa: BLE001
        log(f"tmdb: {error}")
        return ""
    videos = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
    videos.sort(key=lambda v: (TYPES.index(v.get("type")) if v.get("type") in TYPES else 99,
                               not v.get("official"), v.get("iso_639_1") != "en"))
    return videos[0]["key"] if videos else ""


class Trailers(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.monitor = xbmc.Monitor()
        self.ours = False          # the video playing now was started by us
        self.video_id = ""
        self.started_at = 0.0
        self.focus_key = ""
        self.focus_since = 0.0
        self.tried = ""            # the card we already tried during this visit
        self.cache = {}

    # -- player callbacks: anything we did not start is not ours
    def onAVStarted(self):
        # the YouTube add-on needs a few seconds to resolve; anything that starts much
        # later than our request was started by someone else
        if not self.ours:
            return
        if time.time() - self.started_at > 45:
            self.let_go()
        else:
            log("trailer is playing")
            HOME.setProperty(PLAYING, "1")   # the skin shows the video (and expands the card) from now on

    def onPlayBackStopped(self):
        self.let_go()

    def onPlayBackEnded(self):
        self.let_go()

    def onPlayBackError(self):
        self.let_go()

    def let_go(self):
        self.ours = False
        HOME.clearProperty(PLAYING)

    def stop_ours(self):
        if self.ours:
            log("stop")
            self.ours = False
            HOME.clearProperty(PLAYING)
            self.stop()

    # -- main loop
    def run(self):
        log("started")
        while not self.monitor.abortRequested():
            HOME.setProperty(RUNNING, f"{time.time():.1f}")
            try:
                self.tick()
            except Exception as error:  # noqa: BLE001 - never die silently in a loop
                log(f"error: {error}")
            if self.monitor.waitForAbort(TICK):
                break
        self.stop_ours()
        HOME.clearProperty(RUNNING)

    def tick(self):
        mode = skin("nuvio.posterfocus")
        on_home = xbmcgui.getCurrentWindowId() == HOME_ID
        dialog = xbmc.getCondVisibility("[System.HasVisibleModalDialog | Window.IsActive(contextmenu)]"
                                        " + !Window.IsVisible(busydialog) + !Window.IsVisible(busydialognocancel)")
        fullscreen = xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)")
        if self.ours and fullscreen:
            self.let_go()          # the user made it full screen: it is a normal video now
            return
        if not mode or not on_home or dialog:
            self.stop_ours()
            self.focus_key = ""
            return
        focus = Focus()
        if not focus.valid():
            self.stop_ours()
            self.focus_key = ""
            return
        if focus.key != self.focus_key:
            self.stop_ours()
            self.focus_key = focus.key
            self.focus_since = time.time()
            self.tried = ""
            return
        if self.ours and not HOME.getProperty(PLAYING) and time.time() - self.started_at > 45:
            log("YouTube did not start the trailer")
            self.let_go()
        if self.ours or focus.key == self.tried:
            return
        if self.isPlaying() and not self.ours:
            return                  # something else is playing (music, a video in the background)
        try:
            delay = float(skin("nuvio.trailer.delay") or 3)
        except ValueError:
            delay = 3.0
        if time.time() - self.focus_since < delay:
            return
        self.tried = focus.key
        video_id = self.cache.get(focus.key)
        if not video_id:
            video_id = youtube_id(focus.trailer) or tmdb_trailer(focus)
            self.cache[focus.key] = video_id
        if not video_id:
            log(f"no trailer found for {focus.label} (tmdb {focus.tmdb or '-'}, {focus.dbtype or '-'})")
        # the user may have moved on while TMDB answered
        if not video_id or Focus().key != focus.key or xbmcgui.getCurrentWindowId() != HOME_ID:
            return
        log(f"play {video_id} for {focus.label}")
        self.video_id = video_id
        self.started_at = time.time()
        self.ours = True
        item = xbmcgui.ListItem(focus.label)
        item.setProperty("nuvio.trailer", "1")
        self.play(YT + video_id, item, windowed=True)


def running():
    """True when another copy of this helper is alive (its heartbeat is recent)."""
    try:
        return time.time() - float(HOME.getProperty(RUNNING) or 0) < 3
    except ValueError:
        return False


if __name__ == "__main__":
    if running():
        log("already running")
    else:
        Trailers().run()
