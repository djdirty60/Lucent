# -*- coding: utf-8 -*-
"""Lucent: Back in the full screen player.

Normally Back stops the video (see keymap.py). A live channel that was started from the Sport pages is
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
    xbmc.executebuiltin("PlayerControl(Stop)")


main()
