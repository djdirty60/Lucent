# -*- coding: utf-8 -*-
"""Background service: resume point, Trakt scrobbling and the next episode."""
import json
import threading
import time

import xbmc

import dialogs
import library
import player
import scrapers
import tmdb
import tracker
import util

WATCHED_AT = 90.0     # percent
BROKEN_BEFORE_END = 180     # seconds
PREFETCH_BEFORE_END = 300   # seconds


class Watcher(xbmc.Player):
    def __init__(self):
        xbmc.Player.__init__(self)
        self.current = None
        self.position = 0.0
        self.total = 0.0
        self.asked_next = False
        self.dialog = None
        self.following = None     # the next episode, while it should still start
        self.auto_next = False    # start it when this video ends
        self.prefetched = False

    def percent(self):
        return min(100.0, self.position * 100.0 / self.total) if self.total else 0.0

    def _scrobble(self, state, meta=None, percent=None):
        meta = meta or self.current
        value = self.percent() if percent is None else percent
        if meta:
            threading.Thread(target=tracker.scrobble, args=(state, meta, value, self.position, self.total), daemon=True).start()

    def onAVStarted(self):
        raw = util.HOME.getProperty(player.HANDOFF)
        if not raw:
            self.current = None
            return
        now = json.loads(raw)
        if time.time() - now.get("started", 0) > 300:   # left over: this video is not ours
            self.current = None
            return
        util.HOME.clearProperty(player.HANDOFF)
        self.current, self.asked_next, self.following, self.auto_next, self.prefetched = now, False, None, False, False
        self.position = 0.0
        self.total = self.getTotalTime() or 0.0
        if now.get("resume"):
            self.seekTime(float(now["resume"]))
            self.position = float(now["resume"])
        self._scrobble("start")
        threading.Thread(target=self._subtitles, args=(now,), daemon=True).start()

    def _subtitles(self, meta):
        import subs
        if not xbmc.Monitor().waitForAbort(4) and self.current is meta:
            try:
                subs.check(self, meta)
            except Exception as error:      # never break playback
                util.log("subtitle check: %s" % type(error).__name__)

    def onPlayBackPaused(self):
        self._scrobble("pause")

    def onPlayBackResumed(self):
        self._scrobble("start")

    def close_dialog(self):
        if self.dialog:
            self.dialog.finish()
            self.dialog = None

    def finish(self):
        """Save where the video stopped. Safe to call twice."""
        self.close_dialog()
        meta, self.current = self.current, None
        if not meta:
            return
        percent = self.percent()
        progress = util.load_json(player.LOCAL, {})
        key = player.progress_key(meta)
        if self.position >= 60 and percent < WATCHED_AT:
            progress[key] = {"position": self.position, "total": self.total, "at": time.time()}
        else:
            progress.pop(key, None)
        util.save_json(player.LOCAL, progress)
        if percent >= WATCHED_AT and not tracker.logged_in():
            tracker.mark_local(meta, True)
        self._scrobble("stop", meta, percent)
        tracker.forget_lists()
        xbmc.executebuiltin("Container.Refresh")

    def play_next(self, meta):
        following, self.following = self.following, None
        self.auto_next = False
        xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="play", type="episode", tmdb=meta["tmdb"], season=following["season"],
                                                           episode=following["episode"], autoplay=1))

    def onPlayBackStopped(self):
        meta = self.current
        if meta and meta.get("alternates") and self.total - self.position > BROKEN_BEFORE_END and player.link_is_dead(meta, self.position, self.total):
            position, self.current = self.position, None
            self.close_dialog()
            self._try_elsewhere(meta, position)
            return
        self.following, self.auto_next = None, False
        self.finish()

    def _try_elsewhere(self, now, position):
        threading.Thread(target=player.resume_elsewhere, args=(now, position), daemon=True).start()

    def onPlayBackError(self):
        now, position = self.current, self.position
        if not now:                  # it did not even start
            raw = util.HOME.getProperty(player.HANDOFF)
            if not raw:
                return
            now, position = json.loads(raw), json.loads(raw).get("resume") or 0
            util.HOME.clearProperty(player.HANDOFF)
        self.close_dialog()
        self.current = None
        self._try_elsewhere(now, position)

    def onPlayBackEnded(self):
        meta = self.current
        if meta and self.total and self.total - self.position > BROKEN_BEFORE_END and meta.get("alternates"):
            position, self.current = self.position, None     # ended far too early: the link broke
            self.close_dialog()
            self._try_elsewhere(meta, position)
            return
        go = bool(meta and self.following and self.auto_next)
        self.finish()
        if go:
            util.HOME.setProperty(player.RUN, str(run_count() + 1))
            self.play_next(meta)

    def prefetch(self, meta):
        """Finds the sources of the next episode in advance, so it starts right away."""
        try:
            step = tmdb.next_episode(meta["tmdb"], int(meta["season"]), int(meta["episode"]))
            following = step and player.title_meta("episode", meta["tmdb"], step["season"], step["episode"])
            if following:
                scrapers.search(following)
        except util.HttpError:
            pass

    def open_next(self, meta):
        try:
            step = tmdb.next_episode(meta["tmdb"], int(meta["season"]), int(meta["episode"]))
            self.following = step and player.title_meta("episode", meta["tmdb"], step["season"], step["episode"])
        except util.HttpError:
            self.following = None
        if not self.following:
            return
        limit = util.number("still_after", 3)
        if limit and run_count() >= limit:
            self.dialog, self.auto_next = dialogs.still_dialog(self.following.get("show") or "", run_count() + 1), False
        else:
            self.dialog, self.auto_next = dialogs.next_dialog(self.following), True

    def follow_dialog(self, meta):
        """Handles a button that was pressed on the screen next to the video."""
        dialog = self.dialog
        if dialog.result is None:
            if not dialog.closed:
                dialog.countdown(self.total - self.position)
            return
        answer, self.dialog = dialog.result, None
        if answer == "now":
            util.HOME.clearProperty(player.RUN)
            self.finish()
            self.play_next(meta)
        elif answer == "stop" and isinstance(dialog, dialogs.Still):
            self.following = None
            self.stop()
        elif answer == "stop":
            self.following, self.auto_next = None, False
        elif answer == "continue":
            util.HOME.clearProperty(player.RUN)
            self.auto_next = True

    def tick(self):
        if not self.current or not self.isPlayingVideo():
            return
        try:
            self.position = self.getTime()
            self.total = self.getTotalTime() or self.total
        except RuntimeError:
            return
        meta = self.current
        if meta["kind"] == "episode" and not self.prefetched and util.flag("next_episode") and self.total and self.total - self.position <= PREFETCH_BEFORE_END:
            self.prefetched = True
            threading.Thread(target=self.prefetch, args=(meta,), daemon=True).start()
        if self.dialog:
            self.follow_dialog(meta)
            return
        if meta["kind"] == "episode" and not self.asked_next and util.flag("next_episode") and self.total \
                and self.total - self.position <= util.number("next_seconds", 45):
            self.asked_next = True
            self.open_next(meta)


def run_count():
    try:
        return int(util.HOME.getProperty(player.RUN) or 0)
    except ValueError:
        return 0


def run():
    monitor = xbmc.Monitor()
    watcher = Watcher()
    seconds = 0
    library.publish_status()
    while not monitor.waitForAbort(1):
        seconds += 1
        try:
            watcher.tick()
            # first check two minutes after starting, then every minute; never during a video
            if seconds >= 120 and seconds % 60 == 0 and not watcher.isPlaying() and library.due():
                threading.Thread(target=library.run, daemon=True).start()
        except Exception as error:  # noqa: BLE001  a failing tick must never stop the service
            util.log("tick: %s" % type(error).__name__, xbmc.LOGERROR)
