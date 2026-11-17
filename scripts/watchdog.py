# -*- coding: utf-8 -*-
"""Lucent 2.1.35: watchdog for 'Kodi freezes' reports (#22).

Runs inside the helper (helper.py) as two small threads:
  - the prober asks Kodi a simple question (the time) every 2 seconds; Kodi can only answer when its screen thread is free;
  - the watcher only looks at the clock. When the answer takes longer than 3 seconds, it writes to the log how long Kodi
    has not reacted, which window was open just before, and where every thread of Lucent's helper was at that moment
    (file, line and function). When Kodi reacts again, it writes how long it took.
The watcher never asks Kodi anything itself, so it can still write while Kodi is stuck. It changes nothing.

2.1.36: Kodi can also hang while it still draws the screen (the watchdog above stays quiet then), for example when it
goes back to Home and is busy with something else: your remote does nothing. The prober also notes the screen, the
selection and whether you pressed a key. When you keep pressing keys for 8 seconds and nothing on screen changes, it
writes that to the log with the same information (no debug log needed, nothing on screen).
"""
import os
import sys
import threading
import time

import xbmc

LIMIT = 3.0          # seconds without an answer before it counts as a freeze
DEAD_KEYS = 8.0      # seconds of pressing keys without anything changing on screen
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
        self.dead = {"state": "", "first": 0.0, "last": 0.0, "presses": 0, "told": False}

    def start(self):
        threading.Thread(target=self.prober, name="watchdog-prober", daemon=True).start()
        threading.Thread(target=self.watcher, name="watchdog-watcher", daemon=True).start()

    def prober(self):
        log("started")
        while not self.stop.is_set():
            self.asked = time.time()
            try:
                self.window = xbmc.getInfoLabel("System.CurrentWindow") or self.window
                state = "|".join(xbmc.getInfoLabel(x) for x in ("System.CurrentWindow", "System.CurrentControlID",
                                                                 "ListItem.Label", "Container.CurrentItem"))
                pressed = not xbmc.getCondVisibility("System.IdleTime(2)") and not xbmc.getCondVisibility("Player.HasVideo")
                self.keys(state, pressed)
            except Exception:  # noqa: BLE001
                pass
            self.asked = 0.0
            self.stop.wait(2)

    def keys(self, state, pressed):
        """You press keys, but nothing on screen changes (window, selection, item): Kodi does not take your remote."""
        d = self.dead
        now = time.time()
        if state != d["state"]:
            if d["told"]:
                log(f"the remote works again after {now - d['first']:.0f} s (now: {state.split('|')[0] or '-'})")
            d.update(state=state, first=0.0, last=0.0, presses=0, told=False)
            return
        if not pressed:
            if d["first"] and now - d["last"] > 10:     # you stopped pressing: start over
                d.update(first=0.0, presses=0)
            return
        d["first"] = d["first"] or now
        d["last"] = now
        d["presses"] += 1
        if not d["told"] and d["presses"] >= 3 and now - d["first"] >= DEAD_KEYS:
            d["told"] = True
            window, control = (state.split("|") + ["", ""])[:2]
            log(f"keys pressed for {now - d['first']:.0f} s but nothing changes (window {window or '-'}, "
                f"focus {control or 'none'}). Python threads: {stacks()}")

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
