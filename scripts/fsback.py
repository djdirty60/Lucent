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
    if xbmc.getSkinDir() != "skin.lucent":         # 3.0.4 (#37): an old Lucent keymap under another skin
        xbmc.executebuiltin("Action(Back)")
        return
    # 3.0.5 (#36): the film has just ended and Kodi is closing the player: nothing left to stop, so Back does nothing
    # here (a stop sent to a player that is closing could leave Kodi in a bad state)
    if not xbmc.getCondVisibility("Player.HasMedia") or xbmc.getCondVisibility("Window.IsActive(busydialog)"):
        xbmc.log("[skin.lucent] fsback: no media playing, Back ignored", xbmc.LOGINFO)
        return
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
