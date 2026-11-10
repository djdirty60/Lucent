# -*- coding: utf-8 -*-
"""Background service: resume point, Trakt scrobbling and the next episode."""
import json
import threading
import time

import xbmc

import alerts
import dialogs
import learn
import library
import libwatch
import player
import newseason
import prefetch
import remote
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
        util.HOME.clearProperty("lucent.video.memory")
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
        self.learned = False
        self.buffering, self.stalls, self.asked_lighter = 0, [], False
        self.total = self.getTotalTime() or 0.0
        if now.get("resume"):
            self.seekTime(float(now["resume"]))
            self.position = float(now["resume"])
        self._scrobble("start")
        self.streams = None
        threading.Thread(target=self._series_streams, args=(now,), daemon=True).start()

    def _series_streams(self, meta):
        import streammem
        import introskip
        if streammem.has_memory(meta):
            util.HOME.setProperty("lucent.video.memory", "1")      # the general language rules (subwatch.py) step aside
        try:
            introskip.prepare(meta)
        except Exception as error:      # noqa: BLE001
            util.log("intro skip: %s" % type(error).__name__)
        if not xbmc.Monitor().waitForAbort(7) and self.current is meta:
            try:
                streammem.apply(meta)
            except Exception as error:      # noqa: BLE001 - never break playback
                util.log("series sound/subtitle: %s" % type(error).__name__)

    def watch_buffering(self, meta):
        """Keeps loading? Offer once to continue with a much smaller version of the same title, at the same place."""
        if getattr(self, "asked_lighter", True) or not meta.get("lighter") or not util.flag("lighter"):
            return
        if xbmc.getCondVisibility("Player.Caching"):
            self.buffering += 1
            return
        if self.buffering >= 2 and self.position > 30:
            self.stalls = [t for t in self.stalls if time.time() - t < 180] + [time.time()]
        long_stall = self.buffering >= 12 and self.position > 30
        self.buffering = 0
        if long_stall or len(self.stalls) >= 3:
            self.asked_lighter = True
            threading.Thread(target=self._offer_lighter, args=(meta,), daemon=True).start()

    def _offer_lighter(self, meta):
        import xbmcgui
        if not xbmcgui.Dialog().yesno("Lucent", util.T("De video blijft haperen. Verder kijken met een lichtere versie, op dezelfde plek?",
                                                      "The video keeps buffering. Continue with a lighter version, at the same place?")):
            return
        if self.current is not meta:
            return
        position, self.current = self.position, None
        self.close_dialog()
        if not player.resume_elsewhere(meta, position, lighter=True):
            util.notify(util.T("Geen lichtere versie gevonden", "No lighter version found"))

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
        if percent >= WATCHED_AT and meta.get("together"):
            import together
            threading.Thread(target=together.mark, args=(dict(meta), meta["together"]), daemon=True).start()
        self._scrobble("stop", meta, percent)
        import streammem
        streammem.remember(meta, getattr(self, "streams", None))
        libwatch.played(meta)
        libwatch.sync_soon()
        tracker.forget_lists()
        import widgets
        threading.Timer(15, widgets.mark_old, args=(True,)).start()     # the account knows it a few seconds later
        if percent >= WATCHED_AT and meta.get("kind") == "movie":
            import kompas
            kompas.after_film(meta)
        xbmc.executebuiltin("Container.Refresh")

    def play_next(self, meta):
        following, self.following = self.following, None
        self.auto_next = False
        xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="play", type="episode", tmdb=meta["tmdb"], season=following["season"],
                                                           episode=following["episode"], autoplay=1, **{"with": ",".join(meta.get("together") or [])}))

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
        learn.record((now or json.loads(util.HOME.getProperty(player.HANDOFF) or "{}")).get("learn"), False)
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
        go = bool(meta and self.following and self.auto_next) and not (meta or {}).get("bedtime_last")
        self.finish()
        if meta and meta.get("bedtime_last"):
            import bedtime
            threading.Thread(target=bedtime.after_last, daemon=True).start()
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
        if meta.get("bedtime_last"):          # the last one for today: no next episode
            return
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
        self.watch_buffering(meta)
        if meta.get("kind") == "episode" and int(self.position) % 20 == 0 and self.position > 15:
            import streammem
            self.streams = streammem.snapshot() or getattr(self, "streams", None)
        if not getattr(self, "learned", True) and self.position - float(meta.get("resume") or 0) >= learn.GOOD_AFTER:
            self.learned = True
            learn.record(meta.get("learn"), True)
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


class Events(xbmc.Monitor):
    def onNotification(self, sender, method, data):
        if method == "VideoLibrary.OnUpdate":
            try:
                libwatch.on_notification(method, data)
            except Exception as error:      # noqa: BLE001
                util.log("library event: %s" % type(error).__name__)


class SubtitleJobs:
    """Subtitles, spoken language and skip intro for every video (taken over from the Lucent skin)."""

    def __init__(self):
        import subconf
        import subwatch
        self.swap_at = 0.0
        for job in (subconf.migrate, self.switch_once, subconf.publish):
            try:
                job()
            except Exception as error:      # noqa: BLE001 - the service must start anyway
                util.log("subtitles start: %s" % type(error).__name__)
        self.watcher = subwatch.Watcher()      # a player listener: looks when any video starts

    @staticmethod
    def switch_once():
        import subwatch
        if util.setting("subs_switched") != "true" and xbmc.getCondVisibility("System.HasAddon(service.subtitles.lucent)"):
            subwatch.switch_once()

    def swap(self):
        """Kodi's own subtitle search opened (for example by another add-on's auto-search): Lucent's list instead."""
        import subconf
        now = time.time()
        if now - self.swap_at < 8 or not xbmc.getCondVisibility("Window.IsActive(subtitlesearch)"):
            return
        if subconf.on("lucent.subs.native.off") or not xbmc.getCondVisibility("Player.HasVideo"):
            return
        self.swap_at = now
        xbmc.executebuiltin("Dialog.Close(subtitlesearch,true)")
        try:
            started = float(util.HOME.getProperty("lucent.play.start") or 0)
        except ValueError:
            started = 0
        if subconf.text("lucent.subs.mode") == "background" and now - started < 90:
            xbmc.executebuiltin("RunPlugin(plugin://plugin.video.lucent/?action=subs_background)")
            util.log("Kodi's subtitle search -> Lucent background pick")
        else:
            xbmc.executebuiltin("RunPlugin(plugin://plugin.video.lucent/?action=subs_auto)")
            util.log("Kodi's subtitle search -> Lucent live list")

    def tick(self, seconds, playing):
        try:
            self.swap()
            if seconds % 3600 == 1800 and not playing:
                import subs_extra
                threading.Thread(target=subs_extra.check_wanted, daemon=True).start()
            if seconds % 600 == 300 and not playing and xbmc.getCondVisibility(
                    "System.HasAddon(plugin.video.seren) + System.HasAddon(plugin.video.tidb) + Window.IsVisible(home)"):
                import skipdup
                util.log("skip twice: %s" % skipdup.check())
                import subconf
                subconf.publish()
        except Exception as error:      # noqa: BLE001
            util.log("subtitle jobs: %s" % type(error).__name__)


def run():
    monitor = Events()
    watcher = Watcher()
    seconds = 0
    library.publish_status()
    threading.Thread(target=library.publish_counts, daemon=True).start()
    import kompas
    kompas.publish()
    subtitle_jobs = SubtitleJobs()
    while not monitor.waitForAbort(1):
        seconds += 1
        try:
            watcher.tick()
            if remote.wanted():
                remote.start()
            remote.tidy()
            subtitle_jobs.tick(seconds, watcher.isPlayingVideo())
            # first check two minutes after starting, then every minute; never during a video
            if seconds >= 120 and seconds % 60 == 0 and not watcher.isPlaying() and library.due():
                threading.Thread(target=library.run, daemon=True).start()
            if seconds >= 180 and seconds % 60 == 0 and not watcher.isPlaying() and libwatch.sync_due() and not library.due():
                threading.Thread(target=libwatch.periodic, daemon=True).start()
            if seconds >= 600 and seconds % 600 == 0 and not watcher.isPlaying() and newseason.due():
                threading.Thread(target=newseason.run, daemon=True).start()
            if seconds >= 240 and seconds % 60 == 0 and not watcher.isPlaying() and prefetch.due():
                threading.Thread(target=prefetch.run, daemon=True).start()
            if seconds >= 150 and seconds % 600 == 150 and not watcher.isPlaying() and kompas.due():
                threading.Thread(target=kompas.run, daemon=True).start()
            if seconds >= 300 and seconds % 300 == 0 and not watcher.isPlaying() and alerts.due():
                threading.Thread(target=alerts.run, daemon=True).start()
        except Exception as error:  # noqa: BLE001  a failing tick must never stop the service
            util.log("tick: %s" % type(error).__name__, xbmc.LOGERROR)
