# -*- coding: utf-8 -*-
"""Lucent: one background helper for everything.

Before, every part had its own Python process (calendar, sport, updates, Tonight for you, poster colour,
subtitles). Each one costs memory, so now this single helper does all the jobs in turn:

  every ~0.25 s   poster colour (not in light mode)
  every 30 s      sport: refresh, reminders / switching / recording, the card on Home (only with TV channels)
  every 60 s      Tonight for you (works from its saved list; asks TMDB a few times a day)
  every 120 s     calendar pop-ups
  every 6 h       check for a new version of Lucent
  always          automatic subtitle search when a video starts (only when switched on)

Started from Home.xml; a second start does nothing while the first one is running.

The slow jobs (they ask the internet) run one after another in a worker thread, so the poster colour and the
subtitle swap never wait for them. A small heartbeat thread tells a new start that this helper is still alive,
also while a job takes long. After a skin update (lucent.helper.stop) this helper stops so the new one can start.
"""
import hashlib
import json
import os
import threading
import time
import urllib.parse

import xbmc
import xbmcgui
import xbmcvfs

HOME = xbmcgui.Window(10000)
RUNNING = "lucent.helper"
STOP = "lucent.helper.stop"


def log(text):
    xbmc.log(f"[skin.lucent] helper: {text}", xbmc.LOGINFO)


def cond(text):
    return xbmc.getCondVisibility(text)


class Job:
    def __init__(self, name, every, first, func, when=None):
        self.name, self.every, self.func, self.when = name, every, func, when
        self.next = time.time() + first

    def maybe(self, now):
        if now < self.next:
            return
        self.next = now + self.every
        if self.when and not self.when():
            return
        try:
            self.func()
        except Exception as error:  # noqa: BLE001 - one job may fail, the helper goes on
            log(f"{self.name}: {error}")


def run():
    if HOME.getProperty(STOP):                      # right after a skin update: give the old helper a moment to stop
        waiter = xbmc.Monitor()
        for _ in range(20):
            if not HOME.getProperty(RUNNING) or waiter.waitForAbort(0.5):
                break
    last = HOME.getProperty(RUNNING)
    if last and time.time() - float(last) < 60:
        return
    log("started")
    monitor = xbmc.Monitor()

    import agenda_core
    import foryou
    import tint
    import updater

    sport_state = {}
    colour = tint.TintJob()
    subs = {"watcher": None}

    def sport():
        import sport_plan                           # only loaded on boxes with TV channels
        sport_plan.tick(sport_state, monitor)

    def calendar():
        agenda_core.check_notifications()

    def xtream_list():
        import xbmcvfs
        if xbmcvfs.exists("special://profile/addon_data/skin.lucent/xtream.json"):
            import xtream
            xtream.refresh_file()

    def auto_backup():
        if cond("!String.IsEmpty(Skin.String(lucent.backup.auto.dir))"):
            import backup
            backup.auto_backup()

    def channel_filter():
        import xbmcvfs
        if xbmcvfs.exists("special://profile/addon_data/skin.lucent/channel_filter.json"):
            import channels
            channels.refresh()

    def catchup_tick():
        if cond("Skin.HasSetting(lucent.catchup.off)"):
            return
        if subs.get("catchup") is None:
            import catchup
            subs["catchup"] = catchup.Watcher()            # a Kodi player listener, like the subtitle one
        subs["catchup"].tick()

    def subtitles():
        if cond("Skin.HasSetting(nuvio.autosubs)"):
            if subs["watcher"] is None:
                import subtitles as s
                subs["watcher"] = s.Watcher()       # a Kodi player listener: looks when a video starts
        else:
            subs["watcher"] = None

    slow = [                                        # network work: in the worker thread
        Job("sport", 30, 15, sport, lambda: cond("Pvr.HasTVChannels")),
        Job("for you", 60, 20, foryou.update, lambda: not cond("Skin.HasSetting(lucent.fy.off)")),
        Job("calendar", 120, 60, calendar),
        Job("update", 6 * 3600, 90, updater.check, lambda: not cond("Skin.HasSetting(nuvio.update.off)")),
        Job("auto backup", 3600, 600, auto_backup),         # a weekly backup into the folder you chose (checked every hour)
        Job("xtream list", 24 * 3600, 300, xtream_list),             # the channel list Lucent builds itself: once a day
        Job("channel filter", 24 * 3600, 420, channel_filter),       # then the shortened list again, with your choices
    ]
    quick = [Job("subtitles", 30, 5, subtitles), Job("replay position", 10, 12, catchup_tick, lambda: cond("Pvr.HasTVChannels"))]
    stop = threading.Event()

    def beat():
        while not stop.wait(10):
            HOME.setProperty(RUNNING, f"{time.time():.1f}")

    def worker():
        while not stop.is_set() and not monitor.abortRequested():
            for job in slow:
                if stop.is_set():
                    break
                job.maybe(time.time())
            stop.wait(1)

    HOME.setProperty(RUNNING, f"{time.time():.1f}")
    HOME.clearProperty(STOP)
    threading.Thread(target=beat, daemon=True).start()
    threading.Thread(target=worker, daemon=True).start()
    swap = {"t": 0.0}

    def subtitle_window(now):
        """Kodi's own subtitle search opened (for example by another add-on's auto-search): show Lucent's live list instead."""
        if now - swap["t"] < 8 or not cond("Window.IsActive(subtitlesearch)"):
            return
        if cond("Skin.HasSetting(lucent.subs.native.off)") or not cond("Player.HasVideo"):
            return
        swap["t"] = now
        xbmc.executebuiltin("Dialog.Close(subtitlesearch,true)")
        xbmc.executebuiltin("RunScript(special://skin/scripts/subs_live.py)")
        log("Kodi's subtitle search -> Lucent live list")

    lost = {"n": 0}
    pulse = {"sig": None, "until": 0.0, "ok": {}, "memo": {}}
    libdir = xbmcvfs.translatePath("special://profile/addon_data/script.lucent.library/")

    def row_ok(path):
        """True when Lucent Library has a filled copy of this row: then the row is shown before its list is read, so the
        list reads its path at once (Kodi only reads the path of a visible list - a row hidden because it was empty
        would otherwise never fill)."""
        if not path.startswith("plugin://") or cond("Skin.HasSetting(lucent.wcache.off) | !System.HasAddon(script.lucent.library)"):
            return False
        if path.startswith("plugin://script.lucent.library/?action=lib"):
            return True
        if path.startswith("plugin://script.lucent.library/?action=tmdb"):
            q = urllib.parse.parse_qs(path.split("?", 1)[1])
            name = (q.get("list") or [""])[0]
            if name == "tl":
                name = f"tl_{(q.get('user') or [''])[0]}_{(q.get('id') or [''])[0]}"
            file = os.path.join(libdir, "tmdb", f"{name}.json")
        else:
            file = os.path.join(libdir, "widgets", hashlib.md5(path.encode("utf-8")).hexdigest() + ".json")
        try:
            stamp = os.path.getmtime(file)
        except OSError:
            return False
        memo = pulse["memo"].get(file)
        if memo and memo[0] == stamp:
            return memo[1]
        try:
            with open(file, encoding="utf-8") as fh:
                ok = bool(json.load(fh).get("items"))
        except Exception:  # noqa: BLE001 - being written right now: ask again next round
            return False
        pulse["memo"][file] = (stamp, ok)
        return ok

    def rows_pulse(now):
        """Which Home rows to show. A row is shown when it has items, while it loads, when the library has a filled copy
        (lucent.rowok.N), and for a moment after a tab switch or a new copy (lucent.rowsrefresh) for rows from other
        sources, so every list reads its path again."""
        if pulse["until"] and now >= pulse["until"]:
            HOME.clearProperty("lucent.rowsrefresh")
            pulse["until"] = 0.0
        if not cond("Window.IsActive(home)"):
            return
        sig = "|".join([xbmc.getInfoLabel("Container(9000).ListItem.Label")] +
                       [HOME.getProperty(f"lucent.wr.{n}") for n in range(1, 11)])
        if sig != pulse["sig"]:
            pulse["sig"] = sig
            HOME.setProperty("lucent.rowsrefresh", "1")
            pulse["until"] = now + 2.5
        own = xbmc.getInfoLabel("Container(9000).ListItem.Property(w1.path)")
        for n in range(1, 11):
            path = xbmc.getInfoLabel(f"Container(9000).ListItem.Property(w{n}.path)") if own else \
                xbmc.getInfoLabel(f"Skin.String(nuvio.home.w{n}.path)")
            ok = row_ok(path) if path else False
            if pulse["ok"].get(n) != ok:
                pulse["ok"][n] = ok
                if ok:
                    HOME.setProperty(f"lucent.rowok.{n}", "1")
                else:
                    HOME.clearProperty(f"lucent.rowok.{n}")

    def home_focus():
        """Home without any focus (for example OK on the Home tab while it has no rows yet, or after closing the setup
        assistant on a new installation): nothing reacts to the remote any more. Give the focus back to the menu."""
        if not cond("Window.IsActive(home) + !System.HasVisibleModalDialog + !Window.IsVisible(contextmenu)"):
            lost["n"] = 0
            return
        try:
            fid = HOME.getFocusId()
        except RuntimeError:
            fid = 0
        stuck = fid == 0 or (fid == 9100 and not cond("Control.IsVisible(9991)"))
        lost["n"] = lost["n"] + 1 if stuck else 0
        if lost["n"] >= 2:
            lost["n"] = 0
            xbmc.executebuiltin("SetFocus(9000)")
            log("Home had no focus - back to the menu")

    try:
        while not monitor.abortRequested():
            if HOME.getProperty(STOP):
                log("skin updated - making way for the new helper")
                break
            now = time.time()
            for job in quick:
                job.maybe(now)
            try:
                subtitle_window(now)
            except Exception as error:  # noqa: BLE001
                log(f"subtitles: {error}")
            try:
                rows_pulse(now)
            except Exception as error:  # noqa: BLE001
                log(f"rows: {error}")
            try:
                home_focus()
            except Exception as error:  # noqa: BLE001
                log(f"focus: {error}")
            fast = colour.tick()
            if monitor.waitForAbort(0.25 if fast else 1):
                break
    finally:
        stop.set()
        colour.save()
        HOME.clearProperty(RUNNING)
        HOME.clearProperty(STOP)
    log("stopped")


if __name__ == "__main__":
    run()
