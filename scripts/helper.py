# -*- coding: utf-8 -*-
"""Lucent: one background helper for everything.

Before, every part had its own Python process (calendar, sport, updates, Tonight for you, poster colour,
subtitles). Each one costs memory, so now this single helper does all the jobs in turn:

  every ~0.25 s   poster colour (not in light mode)
  every 30 s      sport: refresh, reminders / switching / recording, the card on Home (only with TV channels)
  every 60 s      Tonight for you (works from its saved list; asks TMDB a few times a day)
  every 120 s     calendar pop-ups
  every 6 h       check for a new version of Lucent
  (subtitles and skip intro moved to the video add-on in 1.37.0)

Started from Home.xml; a second start does nothing while the first one is running.

The slow jobs (they ask the internet) run one after another in a worker thread, so the poster colour
never waits for them. A small heartbeat thread tells a new start that this helper is still alive,
also while a job takes long. After a skin update (lucent.helper.stop) this helper stops so the new one can start.
"""
import threading
import time

import xbmc
import xbmcaddon
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
    import continuerow
    import tint
    import omdb
    import seasoninfo
    import views
    import mediaflags
    import updater

    sport_state = {}
    colour = tint.TintJob()
    subs = {"watcher": None}

    def sport():
        import sport_plan                           # only loaded on boxes with TV channels
        sport_plan.tick(sport_state, monitor)

    def calendar():
        agenda_core.check_notifications()

    def live_sport():
        import sportlive
        sportlive.tick()

    def tab_panels():
        import tabpanels
        tabpanels.update()

    def solis_tab():
        import solis                                # the Solis Dashboard tab on Home: the numbers of now
        solis.tick()

    def xtream_list():
        import xbmcvfs
        if xbmcvfs.exists("special://profile/addon_data/skin.lucent/xtream.json"):
            import xtream
            xtream.refresh_file()

    def maintenance():
        import maintenance as m
        m.auto()

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

    def youtube_fix():
        import ytfix
        ytfix.check()
        xbmc.executebuiltin(f'Skin.SetString(lucent.ytfix.state,"{ytfix.label()}")')

    slow = [                                        # network work: in the worker thread
        Job("sport", 30, 15, sport, lambda: cond("Pvr.HasTVChannels")),
        Job("for you", 60, 20, foryou.update, lambda: not cond("Skin.HasSetting(lucent.fy.off)")),
        Job("continue row", 60, 8, continuerow.update),   # one row: films/episodes in progress + next episodes (library)
        Job("calendar", 120, 60, calendar),
        Job("tab panels", 60, 6, tab_panels),
        Job("solis", 3, 4, solis_tab, lambda: cond("System.AddonIsEnabled(script.solis.dashboard) + Window.IsVisible(home)")),
        Job("live sport", 20, 8, live_sport, lambda: cond("Pvr.IsPlayingTV") or bool(HOME.getProperty("live.sc.on"))),   # the score in the TV player               # Calendar / Sport / TV tabs on Home without rows of their own
        Job("youtube fix", 3 * 3600, 25, youtube_fix, lambda: cond("System.HasAddon(plugin.video.youtube)")),   # trailers stopped at ~1:05 (ytfix.py)
        Job("update", 6 * 3600, 90, updater.check, lambda: not cond("Skin.HasSetting(nuvio.update.off)")),
        Job("auto backup", 3600, 600, auto_backup),         # a weekly backup into the folder you chose (checked every hour)
        Job("maintenance", 6 * 3600, 1500, maintenance, lambda: cond("Skin.HasSetting(lucent.maint.auto)")),   # once a month
        Job("xtream list", 24 * 3600, 300, xtream_list),             # the channel list Lucent builds itself: once a day
        Job("channel filter", 24 * 3600, 420, channel_filter),       # then the shortened list again, with your choices
    ]
    def tv_reminders():
        import live
        live.check_reminders()

    def lv_features():
        """What the installed the video add-on can do (it can go back to an older version too): its code is checked, the
        player menu shows a button only when the add-on knows it."""
        try:
            with open(xbmcvfs.translatePath("special://home/addons/plugin.video.lucent/resources/lib/router.py"), encoding="utf-8") as fh:
                code = fh.read()
        except OSError:
            code = ""
        for action, prop in (("replay", "lucent.lv.replay"), ("intro_mark", "lucent.lv.intromark")):
            if f'"{action}"' in code:
                HOME.setProperty(prop, "1")
            else:
                HOME.clearProperty(prop)

    quick = [Job("video add-on", 300, 6, lv_features), Job("tv reminders", 20, 15, tv_reminders), Job("replay position", 10, 12, catchup_tick, lambda: cond("Pvr.HasTVChannels"))]
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


    lost = {"n": 0}
    rowstate = {"ok": {}, "memo": {}, "path": {}, "fresh": {}}
    ROW_ORDER = [(8090, 9988), (8092, 9987), (8091, 9989)] + [(base + n, marker + n) for n in range(1, 11) for base, marker in ((8100, 9900), (8200, 9910))]

    def top_row():
        """lucent.toprow: the highest Home row on screen - Back from a row goes there (then to the menu)."""
        top = ""
        for cid, marker in ROW_ORDER:
            if cond(f"Control.IsVisible({marker}) + Integer.IsGreater(Container({cid}).NumItems,0)"):
                top = str(cid)
                break
        if HOME.getProperty("lucent.toprow") != top:
            HOME.setProperty("lucent.toprow", top)

    def rows_state(now):
        """lucent.rowok.N: show Home row N even while its list is empty. Kodi only reads the list of a VISIBLE row, so a
        row hidden for being empty would never fill. A row is shown for a few seconds after its path changed (a tab
        switch), long enough for Kodi to read it. Nothing here pulses on a timer, so the rows do not jump."""
        if not cond("Window.IsActive(home)"):
            return
        top_row()
        own = xbmc.getInfoLabel("Container(9000).ListItem.Property(w1.path)")
        for n in range(1, 11):
            path = xbmc.getInfoLabel(f"Container(9000).ListItem.Property(w{n}.path)") if own else \
                xbmc.getInfoLabel(f"Skin.String(nuvio.home.w{n}.path)")
            if rowstate["path"].get(n) != path:
                rowstate["path"][n] = path
                rowstate["fresh"][n] = now + 4.0
            ok = bool(path) and now < rowstate["fresh"].get(n, 0)
            if rowstate["ok"].get(n) != ok:
                rowstate["ok"][n] = ok
                if ok:
                    HOME.setProperty(f"lucent.rowok.{n}", "1")
                else:
                    HOME.clearProperty(f"lucent.rowok.{n}")

    def pause_clean():
        """Paused with the player menu open (OK on a Shield): close the menu once no button was pressed for as long as the
        pause screen setting says, so the pause info (or the clean picture) can come. Not while a sub-menu is open."""
        if not cond("Window.IsActive(videoosd) + !Window.IsActive(subtitlesearch) + !Window.IsActive(contextmenu) + !Window.IsActive(selectdialog) + !Window.IsActive(Lucent_PlayerInfo.xml) + !Window.IsActive(Lucent_Subtitles.xml) + !Window.IsActive(osdvideosettings) + !Window.IsActive(osdaudiosettings) + !Window.IsActive(osdsubtitlesettings) + !Window.IsActive(sliderdialog) + !Window.IsActive(videobookmarks) + !Window.IsActive(numericinput)"):
            return
        # the menu goes when the pause screen would come: after the time of the setting (default 5 s); 'Off' keeps it
        if not cond("Player.Paused"):                       # playing: the setting 'Close the player menu by itself'
            secs = xbmc.getInfoLabel("Skin.String(lucent.osdclose)")
            if secs.isdigit() and cond(f"System.IdleTime({secs}) + !Player.Seeking + !Player.Forwarding + !Player.Rewinding"):
                xbmc.executebuiltin("Dialog.Close(videoosd)")
            return
        choice = xbmc.getInfoLabel("Skin.String(nuvio.pauseinfo)")
        wait = {"clean3": 3, "clean5": 5, "clean10": 10, "": 5, "3": 3, "5": 5, "10": 10, "15": 15, "30": 30, "60": 60}.get(choice)
        if wait and cond(f"System.IdleTime({wait})"):
            xbmc.executebuiltin("Dialog.Close(videoosd)")

    settings_state = {"open": False}

    def addon_settings():
        """Add-on settings in three columns: remember which group is chosen and how many groups there are, for the
        tiles and the picture (Kodi switches the group when its button gets the focus; the group buttons have the
        ids -100, -99, ... and the settings -80, -79, ...; the skin cannot ask for negative ids itself)."""
        if xbmcgui.getCurrentWindowDialogId() != 10140:
            if settings_state["open"]:
                settings_state["open"] = False
                HOME.clearProperty("lucent.as.cat")
                HOME.clearProperty("lucent.as.count")
                HOME.clearProperty("lucent.as.lv")
            return
        win = xbmcgui.Window(10140)
        if not settings_state["open"]:
            settings_state["open"] = True
            HOME.setProperty("lucent.as.cat", "0")
            count = 0
            for n in range(20):
                try:
                    win.getControl(-100 + n)
                except (RuntimeError, TypeError):
                    break
                count += 1
            HOME.setProperty("lucent.as.count", str(count))
            name = ""                                  # the settings of the video add-on of the Lucent repository?
            if xbmc.getCondVisibility("System.HasAddon(plugin.video.lucent)"):
                try:
                    name = xbmcaddon.Addon("plugin.video.lucent").getAddonInfo("name")
                except Exception:  # noqa: BLE001
                    name = ""
            if name and name in xbmc.getInfoLabel("Control.GetLabel(2)"):
                HOME.setProperty("lucent.as.lv", "1")
            else:
                HOME.clearProperty("lucent.as.lv")
        try:
            fid = win.getFocusId()
        except RuntimeError:
            return
        if -100 <= fid < -80 and HOME.getProperty("lucent.as.cat") != str(fid + 100):
            HOME.setProperty("lucent.as.cat", str(fid + 100))

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
            row = HOME.getProperty("nuvio.row")
            # a mouse or a tap on an empty spot also leaves Home without focus (issue #13): then go back to the row you
            # were on, so the side menu does not open by itself; only without such a row back to the menu
            if row.isdigit() and cond(f"Control.IsVisible({row}) + Integer.IsGreater(Container({row}).NumItems,0)"):
                xbmc.executebuiltin(f"SetFocus({row})")
                log(f"Home had no focus - back to row {row}")
            elif cond("Control.IsVisible(9991)"):              # Home has rows: the rows, not the side menu
                xbmc.executebuiltin("SetFocus(9100)")
                log(f"Home had no focus - back to the rows (last row {row or '-'})")
            else:
                xbmc.executebuiltin("SetFocus(9000)")
                log("Home had no focus - back to the menu")

    import xbmcaddon
    started_as = {"v": xbmcaddon.Addon("skin.lucent").getAddonInfo("version"), "t": time.time()}

    def updated():
        """Kodi updated the skin by itself (not through Lucent's own update button): start the new helper code."""
        if time.time() - started_as["t"] < 30:
            return False
        started_as["t"] = time.time()
        try:
            now_v = xbmcaddon.Addon("skin.lucent").getAddonInfo("version")
        except Exception:  # noqa: BLE001
            return False
        if now_v and now_v != started_as["v"]:
            log(f"skin updated by Kodi ({started_as['v']} -> {now_v}) - starting the new helper")
            HOME.setProperty(STOP, "1")
            xbmc.executebuiltin("RunScript(special://skin/scripts/startup.py)")
            return True
        return False

    try:
        while not monitor.abortRequested():
            if HOME.getProperty(STOP) or updated():
                log("skin updated - making way for the new helper")
                break
            now = time.time()
            if cond("Player.HasVideo"):
                # a video plays: keep the box as quiet as possible (Dolby Vision FEL on small boxes needs all of it).
                # Only the score in the TV player and closing the player menu; everything else waits until it stops.
                for job in quick:
                    if job.name == "live sport":
                        job.maybe(now)
                try:
                    pause_clean()
                except Exception as error:  # noqa: BLE001
                    log(f"pause clean: {error}")
                if monitor.waitForAbort(1):
                    break
                continue
            for job in quick:
                job.maybe(now)
            try:
                rows_state(now)
            except Exception as error:  # noqa: BLE001
                log(f"rows: {error}")
            try:
                home_focus()
            except Exception as error:  # noqa: BLE001
                log(f"focus: {error}")
            try:
                continuerow.tab_tick()               # the Films tab: films you stopped in; other tabs: series
            except Exception as error:  # noqa: BLE001
                log(f"continue row: {error}")
            try:
                omdb.list_tick()                     # Rotten Tomatoes / Metacritic of the title under the cursor
            except Exception as error:  # noqa: BLE001
                log(f"omdb: {error}")
            try:
                omdb.home_tick()                     # 2.1.3: the same scores for the title under the cursor on Home
                seasoninfo.tick()                    # 2.1.3: episodes left in the season, premiere / finale
            except Exception as error:  # noqa: BLE001
                log(f"home extra: {error}")
            try:
                views.tick()                         # the view you chose, for every folder of that kind (issue #5)
            except Exception as error:  # noqa: BLE001
                log(f"views: {error}")
            try:
                mediaflags.tick()                    # flags of the title under the cursor in the lists (issue #9)
            except Exception as error:  # noqa: BLE001
                log(f"media flags: {error}")
            try:
                addon_settings()                     # the chosen group in the add-on settings (three columns)
            except Exception as error:  # noqa: BLE001
                log(f"add-on settings: {error}")
            try:
                pause_clean()                        # "Clean picture" when paused: the player menu goes too (issue #4)
            except Exception as error:  # noqa: BLE001
                log(f"pause clean: {error}")
            fast = colour.tick() or settings_state["open"]      # quick while the add-on settings are open
            # nobody pressed a button for half a minute: look around less often (small boxes)
            pause = 0.25 if fast else (2.5 if cond("System.IdleTime(30)") else 1)
            if monitor.waitForAbort(pause):
                break
    finally:
        stop.set()
        colour.save()
        HOME.clearProperty(RUNNING)
        HOME.clearProperty(STOP)
    log("stopped")


if __name__ == "__main__":
    run()
