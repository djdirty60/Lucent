# -*- coding: utf-8 -*-
"""Lucent: A4KSubtitles as the subtitle service.

RunScript(special://skin/scripts/subtitles.py,default)   make A4KSubtitles the default service for films and series
The "Search subtitles" button in the player menu opens Kodi's own subtitle search, which then uses that service.
"""
import json
import sys

import xbmc
import xbmcgui

ADDON_ID = "service.subtitles.a4ksubtitles"
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
TEXT = {
    "done": ("A4KSubtitles is now the default subtitle service", "A4KSubtitles is nu de standaard ondertitelservice"),
    "missing": ("A4KSubtitles is not installed", "A4KSubtitles is niet geïnstalleerd"),
    "failed": ("Could not change the setting", "Kon de instelling niet wijzigen"),
}


def say(key, icon=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification("Lucent", TEXT[key][1 if NL else 0], icon, 4000)


def set_default():
    if not xbmc.getCondVisibility(f"System.HasAddon({ADDON_ID})"):
        say("missing", xbmcgui.NOTIFICATION_WARNING)
        return
    ok = True
    for setting in ("subtitles.movie", "subtitles.tv"):
        query = {"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue", "params": {"setting": setting, "value": ADDON_ID}}
        try:
            ok = ok and "error" not in json.loads(xbmc.executeJSONRPC(json.dumps(query)))
        except Exception as error:  # noqa: BLE001
            xbmc.log(f"[skin.lucent subtitles] {setting}: {error}", xbmc.LOGINFO)
            ok = False
    say("done" if ok else "failed", xbmcgui.NOTIFICATION_INFO if ok else xbmcgui.NOTIFICATION_WARNING)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "default":
        set_default()
