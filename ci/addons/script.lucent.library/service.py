"""Lucent Bibliotheek in the background.

  - Four minutes after Kodi starts (Seren has synced with Trakt by then) the library files are refreshed - only after
    the first manual run - and again every few hours when chosen in the skin (Skin.String(lucent.lib.every)).
    The run happens in its own thread, so this loop stays awake.
  - Fetches the Lucent Home rows one at a time (widget.Worker) and refreshes 'Continue watching' after a video.
  - Watched / unwatched marks set by hand in Kodi on our films or episodes go to Trakt too, collected for a few
    seconds and sent in one request (marking a whole season = one request, not one per episode). Not while or just
    after playing (Seren tells Trakt itself then) and not the marks our own sync from Trakt sets.
"""
import json
import os
import threading
import time

import xbmc
import xbmcgui

import lib
import widget

HOME = xbmcgui.Window(10000)
START_DELAY = 240
PUSH_WAIT = 5


class Player(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.pending = 0
        self.stopped = 0.0

    def onPlayBackStarted(self):  # noqa: N802 - Kodi callback name
        self.stopped = time.time()

    def onPlayBackStopped(self):  # noqa: N802
        self.pending = 8
        self.stopped = time.time()

    def onPlayBackEnded(self):  # noqa: N802
        self.pending = 8
        self.stopped = time.time()


class Monitor(xbmc.Monitor):
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.queue = []
        self.last = 0.0
        self.lock = threading.Lock()

    def onNotification(self, sender, method, data):  # noqa: N802
        if method != "VideoLibrary.OnUpdate" or xbmc.getCondVisibility("Skin.HasSetting(lucent.lib.push.off)"):
            return
        try:
            data = json.loads(data or "{}")
        except ValueError:
            return
        item = data.get("item") or {}
        if "playcount" not in data or item.get("type") not in ("movie", "episode") or data.get("added"):
            return
        now = time.time()
        syncing = HOME.getProperty("lucent.lib.syncing")
        if self.player.isPlaying() or now - self.player.stopped < 600:
            return                                  # played: Seren scrobbles to Trakt itself
        if syncing and now - float(syncing) < 120:
            return                                  # our own sync from Trakt
        with self.lock:
            self.queue.append((item["type"], item.get("id"), int(data["playcount"] > 0)))
            self.last = now

    def take(self):
        """The collected marks, once nothing new came in for a few seconds."""
        with self.lock:
            if not self.queue or time.time() - self.last < PUSH_WAIT:
                return []
            marks, self.queue = self.queue, []
            return marks


def every_hours():
    value = xbmc.getInfoLabel("Skin.String(lucent.lib.every)")
    return int(value) if value.isdigit() else 0


def background(target, *args):
    def safe():
        try:
            target(*args)
        except Exception as error:  # noqa: BLE001 - never stop the service
            lib.log(f"service: {error}")
    worker = threading.Thread(target=safe, daemon=True)
    worker.start()
    return worker


def main():
    player = Player()
    monitor = Monitor(player)
    background(widget.Worker(monitor, player).run)   # fetches the Home rows, one at a time
    started = time.time()
    first_done = False
    next_run = 0.0
    next_check = time.time() + 15 * 60               # new episodes on your calendar: looked at every hour
    runner = None
    import tools
    while not monitor.abortRequested():
        now = time.time()
        if player.pending:
            player.pending -= 1
            if player.pending == 0:
                widget.mark_all_stale()             # Seren has had a few seconds to save the progress
        marks = monitor.take()
        if marks:
            background(tools.push_watched, marks)
        busy = runner is not None and runner.is_alive()
        if os.path.exists(lib.ENABLED) and not busy and not player.isPlaying():
            hours = every_hours()
            if not first_done and now - started >= START_DELAY:
                first_done = True
                runner = background(lib.run, False)
                next_run = now + hours * 3600 if hours else 0
            elif first_done and now >= next_check:
                next_check = now + 3600
                if lib.new_episodes_missing():         # a new episode was on TV: add it now, not at the next run
                    runner = background(lib.run, False)
            elif first_done and hours:
                if not next_run:
                    next_run = now + hours * 3600
                elif now >= next_run:
                    runner = background(lib.run, False)
                    next_run = now + hours * 3600
        if monitor.waitForAbort(1):
            break


main()
