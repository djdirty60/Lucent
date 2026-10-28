# -*- coding: utf-8 -*-
"""Lucent: open the settings of an add-on straight on the right category (not on the first one).

RunScript(special://skin/scripts/opensettings.py,plugin.video.seren,accounts)   Seren > Accounts (Trakt, Real-Debrid, ...)
The category id is the id="..." of <category> in the add-on's resources/settings.xml.
"""
import re
import sys
import xbmc
import xbmcaddon
import xbmcvfs

START_BUTTONS = -200            # Kodi numbers the category buttons of a settings dialog -200, -199, ...


def log(text):
    xbmc.log(f"[skin.lucent settings] {text}", xbmc.LOGINFO)


def category_index(addon_id, category):
    path = xbmcaddon.Addon(addon_id).getAddonInfo("path")
    with xbmcvfs.File(f"{path.rstrip('/')}/resources/settings.xml") as fh:
        xml = fh.read()
    ids = [i.replace("&amp;", "&") for i in re.findall(r'<category\s[^>]*?id="([^"]+)"', xml)]
    return ids.index(category) if category in ids else -1


def open_settings(addon_id, category):
    try:
        index = category_index(addon_id, category)
    except Exception as error:  # noqa: BLE001 - open the settings anyway
        log(f"{addon_id}: {error}")
        index = -1
    xbmc.executebuiltin(f"Addon.OpenSettings({addon_id})")
    if index < 0:
        return
    monitor = xbmc.Monitor()
    for _ in range(40):                                    # wait up to 4 seconds for the dialog
        if xbmc.getCondVisibility("Window.IsActive(addonsettings)"):
            break
        if monitor.waitForAbort(0.1):
            return
    monitor.waitForAbort(0.3)
    xbmc.executebuiltin(f"SetFocus({START_BUTTONS + index})")


if __name__ == "__main__" and len(sys.argv) > 2:
    open_settings(sys.argv[1], sys.argv[2])
