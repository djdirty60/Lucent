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
import threading
import time
import urllib.parse

import xbmc
import xbmcgui

import info  # TMDB helpers of the info page (same folder)

HOME_ID = 10000
HOME = xbmcgui.Window(HOME_ID)
RUNNING = "nuvio.trailer.service"   # heartbeat: time of the last loop round
PLAYING = "nuvio.trailer.playing"
ACTIVE = "nuvio.trailer.active"     # "1" from asking YouTube until the player has really stopped: a video add-on can
                                    # wait for it to be empty before it starts a film
QUIET = 10                          # seconds after a film (or another video) before a trailer may start again
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


def tmdb_trailers(focus):
    kind = "movie" if focus.dbtype == "movie" else "tv" if focus.dbtype in ("tvshow", "season", "episode") else ""
    tmdb_id = focus.tmdb
    if focus.dbtype in ("season", "episode") and focus.show_tmdb:
        tmdb_id = focus.show_tmdb
    if not kind or not tmdb_id.isdigit():
        return []
    lang = "nl" if xbmc.getLanguage(xbmc.ISO_639_1) == "nl" else "en"
    try:
        videos = info.tmdb(f"{kind}/{tmdb_id}/videos", include_video_language=f"{lang},en,null").get("results") or []
    except Exception as error:  # noqa: BLE001
        log(f"tmdb: {error}")
        return []
    videos = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
    videos.sort(key=lambda v: (TYPES.index(v.get("type")) if v.get("type") in TYPES else 99,
                               not v.get("official"), v.get("iso_639_1") != "en"))
    return [v["key"] for v in videos[:3]]


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
        self.cancelled_at = 0.0    # when we gave up a trailer that YouTube was still resolving
        self.spare = []            # other trailers of the same title, for when YouTube is slow with the first
        self.spare_label = ""
        self.film_until = 0.0      # a film or another video of someone else plays (or just stopped): hands off
        self.stopping_since = 0.0  # we asked the player to stop our trailer and it has not stopped yet
        self.played = set()        # cards whose trailer already played since Kodi started: not again

    # -- player callbacks: anything we did not start is not ours
    def onAVStarted(self):
        # the YouTube add-on needs a few seconds to resolve; anything that starts much
        # later than our request was started by someone else
        if not (self.ours or self.requested):
            if not self.is_youtube():
                self.hands_off("a video of someone else started")
                return
            if time.time() - self.cancelled_at < 45 and time.time() > self.film_until:
                # the trailer of a card you already left: YouTube only now got it going. Stop it at once,
                # instead of letting it play (and hold the screen) behind Home
                log("late trailer of a card you left: stop")
                self.cancelled_at = 0.0
                xbmc.executebuiltin("PlayerControl(Stop)")
            return
        if time.time() - self.started_at > 45:
            self.let_go()
        else:
            self.adopt()

    def adopt(self):
        """The trailer we asked for is playing: the skin shows the video (and expands the card) from now on."""
        if not self.av_started:
            log("trailer is playing")
            if self.focus_key:
                self.played.add(self.focus_key)     # once per title: coming back to this card does not start it again
        self.ours = True
        self.av_started = True
        self.failures = 0
        HOME.setProperty(PLAYING, "1")

    def hands_off(self, why):
        """A film (or any video we did not start) plays: the trailers do nothing at all until it is over, so nothing
        stops or starts the player while the TV switches to Dolby Vision / HDR."""
        if time.time() > self.film_until:
            log(f"{why}: trailers wait")
        self.film_until = time.time() + QUIET
        self.spare = []
        self.ours = self.requested = self.av_started = False
        HOME.clearProperty(PLAYING)
        HOME.clearProperty(ACTIVE)
        self.stopping_since = 0.0

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
        if not self.stopping_since:
            HOME.clearProperty(ACTIVE)

    def stop_ours(self):
        self.spare = []
        if self.ours or self.requested:
            log("stop")
            if not self.av_started:
                self.cancelled_at = time.time()
            playing = self.av_started or self.isPlayingVideo()
            if playing:
                self.stopping_since = time.time()               # ACTIVE stays set until the player has stopped
            self.let_go()                   # the skin hides the video at once
            if playing:
                xbmc.executebuiltin("PlayerControl(Stop)")      # does not wait for the player

    def prefetch(self, focus):
        """Looks the trailer up while the delay counts down, so it can start as soon as the delay is over."""
        if focus.key in self.cache:
            return

        def find():
            try:
                self.cache[focus.key] = self.candidates(focus)
            except Exception as error:  # noqa: BLE001
                log(f"prefetch: {error}")
        threading.Thread(target=find, daemon=True).start()

    def candidates(self, focus):
        """The trailers of a title: the one of the list item first, then up to three from TMDB."""
        found = [youtube_id(focus.trailer)] if youtube_id(focus.trailer) else []
        for key in tmdb_trailers(focus):
            if key not in found:
                found.append(key)
        return found

    def start(self, video_id, label_text):
        log(f"play {video_id} for {label_text}")
        self.video_id = video_id
        self.started_at = time.time()
        self.ours = True
        self.requested = True
        self.av_started = False
        HOME.setProperty(ACTIVE, "1")
        item = xbmcgui.ListItem(label_text)
        item.setProperty("nuvio.trailer", "1")
        self.play(YT + video_id, item, windowed=True)

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
        HOME.clearProperty(ACTIVE)

    def tick(self):
        mode = skin("nuvio.posterfocus")
        if self.stopping_since and (not self.isPlaying() or time.time() - self.stopping_since > 10):
            self.stopping_since = 0.0
            if not (self.ours or self.requested):
                HOME.clearProperty(ACTIVE)
        # a film or another video that is not our trailer: do nothing at all while it plays and shortly after
        if self.isPlayingVideo() and not (self.ours or self.requested) and not self.is_youtube():
            self.hands_off("a video of someone else plays")
            return
        if time.time() < self.film_until:
            dbg("a film played just now: waiting")
            return
        if self.close_error_dialog():
            return
        window = xbmcgui.getCurrentWindowId()
        on_home = window == HOME_ID
        dialog = xbmc.getCondVisibility("[System.HasVisibleModalDialog | Window.IsActive(contextmenu)]"
                                        " + !Window.IsVisible(busydialog) + !Window.IsVisible(busydialognocancel)")
        # Back on Home makes the trailer full screen. Kodi switches the window before Window.IsActive says so: also go
        # by the window id, or the trailer was stopped as "you left Home" and the full screen stayed black
        fullscreen = window in (12005, 12901) or xbmc.getCondVisibility("Window.IsActive(fullscreenvideo) | Window.IsActive(videoosd)")
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
        if busy and not self.av_started and xbmc.getCondVisibility("Window.IsVisible(busydialog) | Window.IsVisible(busydialognocancel)"):
            # YouTube is getting the trailer: Kodi's busy circle has the focus for a moment, the card is still yours.
            # Counting that as "you left the card" stopped the trailer and started it again, over and over.
            dbg("YouTube is busy: waiting")
            return
        focus = Focus()
        if not focus.valid():
            # the row refreshes now and then (add-ons reload widgets): the card is gone for a moment.
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
            if mode and not xbmc.getCondVisibility("Skin.HasSetting(nuvio.trailer.test)"):
                self.prefetch(focus)
            return
        if (self.requested or self.ours) and not HOME.getProperty(PLAYING) and self.isPlayingVideo():
            # the callback was missed (it is on some boxes): a video is playing and we asked for it, so it is ours
            self.adopt()
        if busy and not self.av_started and self.spare and time.time() - self.started_at > 12:
            # YouTube is slow or stuck with this video: try the next trailer of the same title
            log(f"no picture after 12s, next trailer ({len(self.spare)} left)")
            self.cancelled_at = time.time()
            self.start(self.spare.pop(0), self.spare_label)
            return
        if busy and not HOME.getProperty(PLAYING) and time.time() - self.started_at > 45:
            log("YouTube did not start the trailer")
            self.let_go()
            busy = False
        dbg(f"busy={busy} req={self.requested} ours={self.ours} av={self.av_started} playing={self.isPlayingVideo()} tried={focus.key == self.tried}")
        if busy or focus.key == self.tried or focus.key in self.played:
            return
        if time.time() < self.pause_until:
            dbg(f"PAUSED {int(self.pause_until - time.time())}s (YouTube failed 3 times)")
            return
        if self.isPlaying() and not busy:
            dbg("something else is playing: not starting")
            return                  # something else is playing (music, a video in the background)
        try:
            delay = float(skin("nuvio.trailer.delay") or 2)
        except ValueError:
            delay = 2.0
        waited = time.time() - self.focus_since
        if waited < delay:
            dbg(f"counting {waited:.0f}s of {delay:.0f}s")
            return
        self.tried = focus.key
        dbg("starting")
        test = xbmc.getCondVisibility("Skin.HasSetting(nuvio.trailer.test)")
        found = ["live-test"] if test else self.cache.get(focus.key)
        if found is None:
            found = self.candidates(focus)
            self.cache[focus.key] = found
        video_id = found[0] if found else ""
        if not video_id:
            log(f"no trailer found for {focus.label} (tmdb {focus.tmdb or '-'}, {focus.dbtype or '-'})")
        # the user may have moved on while TMDB answered
        if not video_id or Focus().key != focus.key or xbmcgui.getCurrentWindowId() != HOME_ID:
            return
        if test:
            self.video_id = video_id
            self.started_at = time.time()
            self.ours = True
            self.requested = True
            self.av_started = False
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
        self.spare, self.spare_label = list(found[1:]), focus.label
        self.start(video_id, focus.label)


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
