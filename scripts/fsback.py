# -*- coding: utf-8 -*-
"""Lucent: Back in the full screen player.

Normally Back stops the video (see keymap.py). While you skip (seek bar, fast forward, a seek just done) it only ends
the skipping. A live channel that was started from the Sport pages is
different: Back makes it small again in the TV window and brings the Sport page back. Leaving Sport stops it.
"""
import time

import xbmc
import xbmcgui


def main():
    home = xbmcgui.Window(10000)
    if home.getProperty("lucent.sport.cid") and xbmc.getCondVisibility("PVR.IsPlayingTV"):
        xbmc.executebuiltin("Action(FullScreen)")
        wid = home.getProperty("lucent.sport.wid")
        time.sleep(1.5)
        if wid and not xbmc.getCondVisibility(f"Window.IsActive({wid})") and not xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)"):
            xbmc.executebuiltin("RunScript(special://skin/scripts/sport.py)")
        return
    # while you skip through the film (seek bar on screen, fast forward / rewind, a seek just done) Back only ends the
    # skipping: it must not stop the film (a remote that skips with left / right showed the seek bar, Back stopped)
    if xbmc.getCondVisibility("Player.Forwarding | Player.Rewinding"):
        xbmc.executebuiltin("PlayerControl(Play)")         # back to normal speed
        return
    if xbmc.getCondVisibility("Player.Seeking | Player.HasPerformedSeek(3)"):
        xbmc.executebuiltin("Dialog.Close(seekbar)")
        return
    xbmc.executebuiltin("PlayerControl(Stop)")


main()
