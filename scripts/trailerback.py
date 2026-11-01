# -*- coding: utf-8 -*-
"""Lucent: after a trailer that was started from the film / series page, come back to that page.

Kodi closes the page when the Trailer button starts the video, so afterwards you land on Home (or the list)
and not on the page. This helper is started by the Trailer button, waits until the trailer has started and
ended (or you pressed Back), and then opens the page again for the item that is still selected underneath.
"""

import json
import threading

import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)

START_WAIT = 40       # seconds to wait for the trailer to start (YouTube needs a moment)
SETTLE = 1.2          # seconds for Kodi to close the full screen player and show the window underneath


def log(text):
    xbmc.log(f"[skin.lucent] trailerback: {text}", xbmc.LOGINFO)


def which_page():
    """What the open page is about, read before it closes: a library title (its id) or a Lucent page (TMDb id)."""
    page = {"dbid": HOME.getProperty("lucent.page.dbid"), "dbtype": HOME.getProperty("lucent.page.dbtype")}   # set when the page loaded
    try:
        page["ident"] = json.loads(HOME.getProperty("nuvio.info.identity") or "null")
    except ValueError:
        page["ident"] = None
    return page


def _info(li):
    try:
        xbmcgui.Dialog().info(li)
    except Exception as error:  # noqa: BLE001
        log(f"page: {error}")


def reopen(page):
    """Open the page again: a library title by its id, a Lucent page from TMDb, otherwise Info on the selected item."""
    if page["dbid"].isdigit() and int(page["dbid"]) > 0 and page["dbtype"] in ("movie", "tvshow", "episode", "season"):
        li = xbmcgui.ListItem(offscreen=True)
        tag = li.getVideoInfoTag()
        tag.setMediaType(page["dbtype"])
        tag.setDbId(int(page["dbid"]))
        threading.Thread(target=_info, args=(li,)).start()      # Kodi holds this call while the page is open
        return
    ident = page["ident"]
    if ident and str(ident[1]).isdigit():
        HOME.setProperty("nuvio.open.type", ident[0] or "movie")
        HOME.setProperty("nuvio.open.tmdb", str(ident[1]))
        HOME.setProperty("nuvio.open.trakt", str(ident[2] or ""))
        xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,open,path)")
        return
    xbmc.executebuiltin("Action(Info)")


def main():
    page = which_page()
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    waited = 0.0
    while not player.isPlayingVideo():
        if monitor.waitForAbort(0.1):
            return
        waited += 0.1
        if waited > START_WAIT:
            log("the trailer did not start, nothing to come back to")
            return
    # the trailer started: it must be full screen at once. Kodi does not switch to full screen while the page (a
    # dialog) is open, so the video would play behind it: close the page and show the video (the page comes back after)
    for attempt in range(6):
        if xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)"):
            break
        log("trailer is playing behind the page: closing the page, full screen")
        xbmc.executebuiltin("Dialog.Close(movieinformation,true)")
        xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
        if monitor.waitForAbort(0.5):
            return
    while player.isPlayingVideo():
        if monitor.waitForAbort(0.5):
            return
    if monitor.waitForAbort(SETTLE):
        return
    # something else already took over (another video, a dialog of ours): leave it
    if player.isPlayingVideo() or xbmc.getCondVisibility("Window.IsActive(fullscreenvideo) | Window.IsActive(movieinformation)"):
        return
    log(f"trailer is over: opening the page again ({page['dbtype']} {page['dbid']} / {page['ident']})")
    reopen(page)


main()
