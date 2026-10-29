# -*- coding: utf-8 -*-
"""Lucent: hide (or show) all channel groups at once in Kodi's group manager.

    RunScript(special://skin/scripts/pvrgroups.py,hide|show)

Kodi has no command for this, only the "Hide group" switch (id 25) for the group that is selected in the list (id 13).
So this walks the list: select a group, flip the switch when needed, next group - the same as doing it by hand.
Which groups are hidden now: Kodi's JSON-RPC lists only the visible ones.
'All channels' stays visible when hiding: without it the TV guide would have nothing to show.
"""
import json
import sys

import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
LIST, SWITCH = 13, 25


def log(text):
    xbmc.log(f"[skin.lucent] pvrgroups: {text}", xbmc.LOGINFO)


def visible_groups(radio):
    request = {"jsonrpc": "2.0", "id": 1, "method": "PVR.GetChannelGroups", "params": {"channeltype": "radio" if radio else "tv"}}
    try:
        result = json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result") or {}
    except Exception as error:  # noqa: BLE001
        log(f"groups: {error}")
        return None
    return {g.get("label", "") for g in result.get("channelgroups") or []}


def wait(condition, monitor, seconds=1.5):
    for _ in range(int(seconds / 0.05)):
        if xbmc.getCondVisibility(condition):
            return True
        if monitor.waitForAbort(0.05):
            return False
    return False


def run(mode):
    monitor = xbmc.Monitor()
    if not xbmc.getCondVisibility("Window.IsActive(pvrgroupmanager)"):
        return
    radio = bool(xbmc.getInfoLabel("Window(pvrgroupmanager).Property(IsRadio)"))
    visible = visible_groups(radio)
    if visible is None:
        return
    total = int(xbmc.getInfoLabel(f"Container({LIST}).NumItems") or 0)
    all_channels = xbmc.getLocalizedString(19287)
    changed = 0
    xbmc.executebuiltin(f"SetFocus({LIST})")
    if not wait(f"Control.HasFocus({LIST})", monitor):
        return
    xbmc.executebuiltin("Action(FirstPage)")                 # a move action: the dialog follows the selection
    wait(f"Integer.IsEqual(Container({LIST}).CurrentItem,1)", monitor)
    for index in range(total):
        label = xbmc.getInfoLabel(f"Container({LIST}).ListItem.Label")
        shown = label in visible
        flip = (mode == "hide" and shown and label != all_channels) or (mode == "show" and not shown)
        if flip:
            xbmc.executebuiltin(f"SetFocus({SWITCH})")
            if wait(f"Control.HasFocus({SWITCH})", monitor):
                xbmc.executebuiltin("Action(Select)")         # a real press, so the switch changes and Kodi saves it
                monitor.waitForAbort(0.3)
                changed += 1
            xbmc.executebuiltin(f"SetFocus({LIST})")
            wait(f"Control.HasFocus({LIST})", monitor)
        if index < total - 1:
            xbmc.executebuiltin("Action(Down)")
            wait(f"Integer.IsEqual(Container({LIST}).CurrentItem,{index + 2})", monitor)
        if monitor.abortRequested():
            return
    xbmc.executebuiltin("Action(FirstPage)")
    text = (f"{changed} groepen verborgen" if mode == "hide" else f"{changed} groepen weer zichtbaar") if NL else \
        (f"{changed} groups hidden" if mode == "hide" else f"{changed} groups shown again")
    xbmcgui.Dialog().notification("Lucent", text, xbmcgui.NOTIFICATION_INFO, 3000)
    log(f"{mode}: {changed} of {total}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "hide")
