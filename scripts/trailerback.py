# -*- coding: utf-8 -*-
"""Lucent: after a trailer that was started from the film / series page, come back to that page.

Kodi closes the page when the Trailer button starts the video, so afterwards you land on Home (or the list)
and not on the page. This helper is started by the Trailer button, waits until the trailer has started and
ended (or you pressed Back), and then opens the page again for the item that is still selected underneath.
"""

import xbmc

START_WAIT = 40       # seconds to wait for the trailer to start (YouTube needs a moment)
SETTLE = 1.2          # seconds for Kodi to close the full screen player and show the window underneath


def log(text):
    xbmc.log(f"[skin.lucent] trailerback: {text}", xbmc.LOGINFO)


def main():
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    waited = 0.0
    while not player.isPlayingVideo():
        if monitor.waitForAbort(0.25):
            return
        waited += 0.25
        if waited > START_WAIT:
            log("the trailer did not start, nothing to come back to")
            return
    while player.isPlayingVideo():
        if monitor.waitForAbort(0.5):
            return
    if monitor.waitForAbort(SETTLE):
        return
    # something else already took over (another video, a dialog of ours): leave it
    if player.isPlayingVideo() or xbmc.getCondVisibility("Window.IsActive(fullscreenvideo) | Window.IsActive(movieinformation)"):
        return
    log("trailer is over: opening the page again")
    xbmc.executebuiltin("Action(Info)")


main()
