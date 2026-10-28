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


def run():
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
                if epg.play_windowed(cid):
                    started = True
            done = name
        if monitor.waitForAbort(0.4):
            return
    if started:
        monitor.waitForAbort(1.2)
        if not (xbmc.getCondVisibility("Window.IsActive(fullscreenvideo)") or xbmc.getCondVisibility("Window.IsActive(videoosd)")
                or xbmc.getCondVisibility(GUIDE)):
            xbmc.executebuiltin("PlayerControl(Stop)")


if __name__ == "__main__":
    run()
