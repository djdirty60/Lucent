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


_DBG = {"last": "", "next": 0.0}


def dbg(text):
    """Shown in the yellow test line on Home. Only written while the test switch is on, and only when the text changes
    (every property write makes Home redraw, which a weak box feels)."""
    if text == _DBG["last"]:
        return
    now = time.time()
    if now < _DBG["next"]:
        return
    if not xbmc.getCondVisibility("Skin.HasSetting(nuvio.trailer.test)"):
        if _DBG["last"]:
            HOME.clearProperty("nuvio.trailer.dbg")
            _DBG["last"] = ""
        return
    _DBG["next"] = now + 0.5
    _DBG["last"] = text
    HOME.setProperty("nuvio.trailer.dbg", text)


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
        self.requested = False     # we asked YouTube for a trailer and it has not ended yet
        self.av_started = False
        self.video_id = ""
        self.started_at = 0.0
        self.focus_key = ""
        self.focus_since = 0.0
        self.tried = ""            # the card we already tried during this visit
        self.cache = {}
        self.failures = 0          # trailers in a row that YouTube could not play
        self.stray_since = 0.0     # since when a video without an owner plays behind Home
        self.lost_since = 0.0      # since when the focused card is not readable
        self.pause_until = 0.0     # after repeated failures we stop trying for a while

    # -- player callbacks: anything we did not start is not ours
    def onAVStarted(self):
        # the YouTube add-on needs a few seconds to resolve; anything that starts much
        # later than our request was started by someone else
        if not (self.ours or self.requested):
            return
        if time.time() - self.started_at > 45:
            self.let_go()
        else:
            self.adopt()

    def adopt(self):
        """The trailer we asked for is playing: the skin shows the video (and expands the card) from now on."""
        if not self.av_started:
            log("trailer is playing")
        self.ours = True
        self.av_started = True
        self.failures = 0
        HOME.setProperty(PLAYING, "1")

    def onPlayBackStopped(self):
        self.ended("stopped")

    def onPlayBackEnded(self):
        self.ended("ended")

    def ended(self, why):
        # the YouTube add-on can send a stop of its own while it resolves the video:
        # an early stop event is not the end of our trailer
        if (self.ours or self.requested) and not self.av_started and time.time() - self.started_at < 5:
            log(f"ignored early '{why}' event")
            return
        self.let_go()

    def onPlayBackError(self):
        if self.ours or self.requested:
            self.failed("playback error")
        self.let_go()

    def failed(self, why):
        self.failures += 1
        log(f"trailer failed ({why}), {self.failures} in a row")
        if self.failures >= 3:
            self.pause_until = time.time() + 600
            log("YouTube keeps failing: no more trailers for 10 minutes. "
                "Update the YouTube and InputStream Adaptive add-ons.")

    def close_error_dialog(self):
        """YouTube / InputStream Adaptive shows an OK pop-up when a trailer cannot be played.
        While we are waiting for our own trailer, close it and count the failure."""
        if ((self.ours or self.requested) and not HOME.getProperty(PLAYING) and time.time() - self.started_at < 60
                and xbmc.getCondVisibility("Window.IsActive(okdialog)")):
            xbmc.executebuiltin("Dialog.Close(okdialog,true)")
            self.failed("error pop-up")
            self.let_go()
            return True
        return False

    def is_youtube(self):
        text = " ".join([label("Player.Filenameandpath"), label("Player.Folderpath")]).lower()
        return "plugin.video.youtube" in text or "googlevideo.com" in text

    def let_go(self):
        self.ours = False
        self.requested = False
        self.av_started = False
        HOME.clearProperty(PLAYING)

    def stop_ours(self):
        if self.ours or self.requested:
            log("stop")
            self.let_go()
            self.stop()

    # -- main loop
    def run(self):
        log("started")
        dbg("service started")
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
        if self.close_error_dialog():
            return
        on_home = xbmcgui.getCurrentWindowId() == HOME_ID
        dialog = xbmc.getCondVisibility("[System.HasVisibleModalDialog | Window.IsActive(contextmenu)]"
                                        " + !Window.IsVisible(busydialog) + !Window.IsVisible(busydialognocancel)")
        fullscreen = xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)")
        busy = self.ours or self.requested
        # safety net: a YouTube video that plays behind the Home screen and that we do not own is a stray trailer
        # (it lost its owner, for example after a window change): stop it after a few seconds
        if on_home and not busy and not fullscreen and self.isPlayingVideo() and self.is_youtube():
            self.stray_since = self.stray_since or time.time()
            if time.time() - self.stray_since > 3:
                log("stopping a stray YouTube video behind Home")
                self.stray_since = 0.0
                self.stop()
                return
        else:
            self.stray_since = 0.0
        if busy and fullscreen:
            dbg("fullscreen: let go")
            self.let_go()          # the user made it full screen: it is a normal video now
            return
        if not mode or not on_home or dialog:
            dbg(f"waiting: mode={mode or '-'} home={on_home} dialog={dialog}")
            self.stop_ours()
            self.focus_key = ""
            return
        focus = Focus()
        if not focus.valid():
            # the row refreshes now and then (Seren reloads widgets): the card is gone for a moment.
            # Only let go when it stays gone.
            if not self.lost_since:
                self.lost_since = time.time()
            if time.time() - self.lost_since < 2.0 and (self.focus_key or busy):
                dbg(f"focus gone for a moment: row={focus.row or '-'} label={focus.label or '-'}")
                return
            dbg(f"no focus: row={focus.row or '-'} label={focus.label or '-'}")
            self.stop_ours()
            self.focus_key = ""
            return
        self.lost_since = 0.0
        if focus.key != self.focus_key:
            dbg(f"new card: {self.focus_key[:28]} -> {focus.key[:28]}")
            self.stop_ours()
            self.focus_key = focus.key
            self.focus_since = time.time()
            self.tried = ""
            return
        if (self.requested or self.ours) and not HOME.getProperty(PLAYING) and self.isPlayingVideo():
            # the callback was missed (it is on some boxes): a video is playing and we asked for it, so it is ours
            self.adopt()
        if busy and not HOME.getProperty(PLAYING) and time.time() - self.started_at > 45:
            log("YouTube did not start the trailer")
            self.let_go()
            busy = False
        dbg(f"busy={busy} req={self.requested} ours={self.ours} av={self.av_started} playing={self.isPlayingVideo()} tried={focus.key == self.tried}")
        if busy or focus.key == self.tried:
            return
        if time.time() < self.pause_until:
            dbg(f"PAUSED {int(self.pause_until - time.time())}s (YouTube failed 3 times)")
            return
        if self.isPlaying() and not busy:
            dbg("something else is playing: not starting")
            return                  # something else is playing (music, a video in the background)
        try:
            delay = float(skin("nuvio.trailer.delay") or 3)
        except ValueError:
            delay = 3.0
        waited = time.time() - self.focus_since
        if waited < delay:
            dbg(f"counting {waited:.0f}s of {delay:.0f}s")
            return
        self.tried = focus.key
        dbg("starting")
        test = xbmc.getCondVisibility("Skin.HasSetting(nuvio.trailer.test)")
        video_id = "live-test" if test else self.cache.get(focus.key)
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
        self.requested = True
        self.av_started = False
        if test:
            # TEST: a live channel in the same place instead of a YouTube trailer
            import sport_epg as epg  # only for the test mode
            found = epg.channels()
            if not found:
                log("test: no TV channels")
                self.let_go()
                return
            log(f"test: playing channel {found[0].get('label') or found[0].get('channelid')}")
            if not epg.play_windowed(found[0]["channelid"]):
                epg.play(found[0]["channelid"])
            return
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
