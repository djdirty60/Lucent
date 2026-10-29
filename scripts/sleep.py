# -*- coding: utf-8 -*-
"""Lucent: sleep timer from the player menu (the moon button).

    RunScript(special://skin/scripts/sleep.py)

Choices: after this episode / film, after 15, 30, 45, 60 or 90 minutes, or switch the timer off.
When the time is there, playback stops (and what was queued next - Seren's next episode - is cleared, so nothing
starts by itself). The timer runs in this script; Window(home).Property(lucent.sleep.label) shows what is set
(the player menu shows it under the moon button). Choosing again replaces the running timer.
"""
import time

import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
HOME = xbmcgui.Window(10000)
GEN, UNTIL, MODE, LABEL = "lucent.sleep.gen", "lucent.sleep.until", "lucent.sleep.mode", "lucent.sleep.label"
MINUTES = (15, 30, 45, 60, 90)


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] sleep: {text}", xbmc.LOGINFO)


def remaining_label():
    mode = HOME.getProperty(MODE)
    if mode == "end":
        return t("after this one", "na deze")
    if mode == "time":
        left = max(0, int((float(HOME.getProperty(UNTIL) or 0) - time.time() + 59) // 60))
        return t(f"{left} min left", f"nog {left} min")
    return ""


def stop_all():
    """Stop, and clear what is queued so the next episode does not start by itself."""
    xbmc.executebuiltin("Playlist.Clear(video)")
    xbmc.executebuiltin("PlayerControl(Stop)")


def clear(gen=None):
    if gen is None or HOME.getProperty(GEN) == gen:
        for key in (UNTIL, MODE, LABEL):
            HOME.clearProperty(key)


def watch(gen):
    """The timer itself: checks every few seconds until it is time, or until another choice replaced it."""
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    try:
        first = player.getPlayingFile() if player.isPlayingVideo() else ""
    except RuntimeError:
        first = ""
    try:
        while not monitor.abortRequested() and HOME.getProperty(GEN) == gen:
            mode = HOME.getProperty(MODE)
            HOME.setProperty(LABEL, remaining_label())
            if mode == "time" and time.time() >= float(HOME.getProperty(UNTIL) or 0):
                log("time is up")
                stop_all()
                xbmcgui.Dialog().notification(t("Sleep timer", "Slaaptimer"), t("Goodnight", "Welterusten"),
                                              "special://skin/media/buttons/sleep_nf.png", 4000, False)
                return
            if mode == "end":
                try:
                    now = player.getPlayingFile() if player.isPlayingVideo() else ""
                except RuntimeError:
                    now = ""
                if not now or (first and now != first):           # ended, or the next one already began
                    log("played to the end")
                    stop_all()
                    return
                try:
                    left = player.getTotalTime() - player.getTime()
                except RuntimeError:
                    left = 999
                if 0 < left <= 2.5:                           # the very end: stop before the next one starts
                    log("end of this one")
                    stop_all()
                    xbmcgui.Dialog().notification(t("Sleep timer", "Slaaptimer"), t("Goodnight", "Welterusten"),
                                                  "special://skin/media/buttons/sleep_nf.png", 4000, False)
                    return
            if monitor.waitForAbort(1 if mode == "end" else 5):
                return
    finally:
        clear(gen)


def run():
    active = HOME.getProperty(MODE)
    episode = bool(xbmc.getInfoLabel("VideoPlayer.TVShowTitle"))
    labels = [t("After this episode", "Na deze aflevering") if episode else t("After this film", "Na deze film")]
    labels += [t(f"In {m} minutes", f"Over {m} minuten") for m in MINUTES]
    if active:
        labels.append(t("Switch the sleep timer off", "Slaaptimer uitzetten"))
    heading = t("Sleep timer", "Slaaptimer") + (f"  ·  {remaining_label()}" if active else "")
    pick = xbmcgui.Dialog().select(heading, labels)
    if pick < 0:
        return
    gen = f"{time.time():.3f}"
    HOME.setProperty(GEN, gen)                                # a running timer sees this and ends
    if active and pick == len(labels) - 1:
        clear()
        xbmcgui.Dialog().notification(t("Sleep timer", "Slaaptimer"), t("Off", "Uit"),
                                      "special://skin/media/buttons/sleep_nf.png", 2500, False)
        return
    if pick == 0:
        HOME.setProperty(MODE, "end")
        HOME.clearProperty(UNTIL)
    else:
        HOME.setProperty(MODE, "time")
        HOME.setProperty(UNTIL, str(time.time() + MINUTES[pick - 1] * 60))
    HOME.setProperty(LABEL, remaining_label())
    xbmcgui.Dialog().notification(t("Sleep timer", "Slaaptimer"), labels[pick], "special://skin/media/buttons/sleep_nf.png", 3000, False)
    watch(gen)


if __name__ == "__main__":
    run()
