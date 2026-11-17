# -*- coding: utf-8 -*-
"""Lucent 2.1.35: watchdog for 'Kodi freezes' reports (#22).

Runs inside the helper (helper.py) as two small threads:
  - the prober asks Kodi a simple question (the time) every 2 seconds; Kodi can only answer when its screen thread is free;
  - the watcher only looks at the clock. When the answer takes longer than 3 seconds, it writes to the log how long Kodi
    has not reacted, which window was open just before, and where every thread of Lucent's helper was at that moment
    (file, line and function). When Kodi reacts again, it writes how long it took.
The watcher never asks Kodi anything itself, so it can still write while Kodi is stuck. It changes nothing.
"""
import os
import sys
import threading
import time

import xbmc

LIMIT = 3.0          # seconds without an answer before it counts as a freeze
REPEAT = (10.0, 30.0, 60.0)


def log(text):
    xbmc.log(f"[skin.lucent] watchdog: {text}", xbmc.LOGINFO)


def stacks():
    """Where each thread of this Python interpreter (the helper) is now: the last lines that are Lucent's own."""
    names = {t.ident: t.name for t in threading.enumerate()}
    out = []
    me = threading.get_ident()
    for ident, frame in sys._current_frames().items():  # noqa: SLF001 - only read for the log
        if ident == me:
            continue
        lines = []
        while frame is not None:
            code = frame.f_code
            lines.append(f"{os.path.basename(code.co_filename)}:{frame.f_lineno} {code.co_name}")
            frame = frame.f_back
        own = [ln for ln in lines if not ln.startswith(("threading.py", "socket.py", "ssl.py"))][:4]
        out.append(f"{names.get(ident, ident)}: {' < '.join(own) or '-'}")
    return " | ".join(out)


class Watchdog:
    def __init__(self, stop):
        self.stop = stop
        self.asked = 0.0          # when the prober asked Kodi (0: not waiting)
        self.window = ""

    def start(self):
        threading.Thread(target=self.prober, name="watchdog-prober", daemon=True).start()
        threading.Thread(target=self.watcher, name="watchdog-watcher", daemon=True).start()

    def prober(self):
        while not self.stop.is_set():
            self.asked = time.time()
            try:
                self.window = xbmc.getInfoLabel("System.CurrentWindow") or self.window
            except Exception:  # noqa: BLE001
                pass
            self.asked = 0.0
            self.stop.wait(2)

    def watcher(self):
        reported, since, window = [], 0.0, ""
        while not self.stop.is_set():
            asked = self.asked
            now = time.time()
            if asked and now - asked > LIMIT:
                if not since:
                    since, window, reported = asked, self.window, []
                    log(f"Kodi has not reacted for {now - asked:.0f} s (window before: {window or '-'}). "
                        f"Lucent's helper is at: {stacks()}")
                for mark in REPEAT:
                    if now - since > mark and mark not in reported:
                        reported.append(mark)
                        log(f"Kodi still not reacting after {mark:.0f} s. Lucent's helper is at: {stacks()}")
            elif since:
                log(f"Kodi reacts again after {time.time() - since:.1f} s (window before: {window or '-'})")
                since = 0.0
            self.stop.wait(1)
