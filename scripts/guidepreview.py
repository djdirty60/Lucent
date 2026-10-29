# -*- coding: utf-8 -*-
"""Lucent: live preview in the TV guide.

Runs while the TV guide is open: the channel you are on in the guide plays in the small window at the top right
(started after you stayed on it for a moment). Leaving the guide stops that preview, unless you went to full screen.
"""
import time

import xbmc

import sport_epg as epg
import sport_core as sc

GUIDE = "Window.IsActive(tvguide)"
STAY = 1.2          # seconds on a channel before it starts


def focused():
    name = xbmc.getInfoLabel("Container(50).ListItem.ChannelName") or xbmc.getInfoLabel("ListItem.ChannelName")
    return name.strip()


def select_action_once():
    """OK on a programme switches to the channel (full screen); set once, so a later choice of the user stays."""
    if xbmc.getInfoLabel("Skin.String(lucent.guideselect)"):
        return
    xbmc.executebuiltin('Skin.SetString(lucent.guideselect,"1")', True)
    epg.rpc("Settings.SetSettingValue", {"setting": "epg.selectaction", "value": 1})


def open_favourite_group():
    """Open the favourite channel group once per visit of the guide (not again when coming back from full screen)."""
    home = xbmcgui_window()
    if home.getProperty("lucent.guide.applied"):
        return
    home.setProperty("lucent.guide.applied", "1")
    want = xbmc.getInfoLabel("Skin.String(lucent.guide.group)")
    if not want:
        return
    for _ in range(30):                       # wait until the groups are listed
        if xbmc.getCondVisibility("Integer.IsGreater(Container(11).NumItems,0)"):
            break
        xbmc.sleep(200)
    count = int(xbmc.getInfoLabel("Container(11).NumItems") or 0)
    for index in range(count):
        if xbmc.getInfoLabel(f"Container(11).ListItemAbsolute({index}).Label").strip() == want:
            if index != int(xbmc.getInfoLabel("Container(11).CurrentItem") or 1) - 1:
                xbmc.executebuiltin(f"SetFocus(11,{index},absolute)")
                xbmc.sleep(400)
                xbmc.executebuiltin("Action(Select)")
                xbmc.sleep(900)
            xbmc.executebuiltin("SetFocus(50)")
            return


def xbmcgui_window():
    import xbmcgui
    return xbmcgui.Window(10000)


def run():
    select_action_once()
    try:
        open_favourite_group()
    except Exception as error:  # noqa: BLE001
        sc.log(f"guide favourite: {error}")
    monitor = xbmc.Monitor()
    ids = {}
    try:
        for ch in epg.channels():
            ids.setdefault((ch.get("label") or "").strip(), ch.get("channelid"))
    except Exception as error:  # noqa: BLE001
        sc.log(f"guide preview: no channels ({error})")
        return
    started = False
    seen, since, done = "", time.time(), ""
    for _ in range(40):                       # the guide needs a moment to open
        if xbmc.getCondVisibility(GUIDE) or monitor.waitForAbort(0.25):
            break
    while xbmc.getCondVisibility(GUIDE) and not monitor.abortRequested():
        name = focused()
        if name != seen:
            seen, since = name, time.time()
        elif name and name != done and time.time() - since >= STAY and name in ids:
            cid, playing = ids[name], epg.playing_channel()
            if str(cid) != playing[0]:
                if epg.play_windowed(cid, 3):
                    started = True
            done = name
        if monitor.waitForAbort(0.4):
            return
    monitor.waitForAbort(1.2)
    if not (xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)") or xbmc.getCondVisibility("Window.IsActive(videoosd)")
            or xbmc.getCondVisibility(GUIDE)):
        xbmcgui_window().clearProperty("lucent.guide.applied")      # the guide was really left
    if started or xbmc.getCondVisibility("Pvr.IsPlayingTV"):
        if not (xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)") or xbmc.getCondVisibility("Window.IsActive(videoosd)")
                or xbmc.getCondVisibility(GUIDE)):
            xbmc.executebuiltin("PlayerControl(Stop)")


if __name__ == "__main__":
    try:
        run()
    finally:
        epg.restore_fullscreen()            # your own "switch to full screen" setting back, however the guide was left
