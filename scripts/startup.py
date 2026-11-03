# -*- coding: utf-8 -*-
"""Lucent: everything that has to happen once when Kodi starts, in ONE Python start.

    RunScript(special://skin/scripts/startup.py)      from Home.xml, only the first time Home opens

Before this, Home started five or six separate scripts at the same time (key maps, rating logos, the Calendar and
Sport tabs, the helper). Every one of them is its own Python interpreter, and on a small box they all compete with
Seren and the widgets that load at that moment. Now the quick jobs run here after each other, and the long-running
helper is started last, in this same interpreter.
"""
import xbmc


def log(text):
    xbmc.log(f"[skin.lucent] startup: {text}", xbmc.LOGINFO)


def step(name, func):
    try:
        func()
    except Exception as error:  # noqa: BLE001 - one job must never stop the others
        log(f"{name}: {error}")


def season_page():
    """Kodi skips the seasons of a series with only one season ('Flatten TV show seasons: if only one season'), so
    such a series opened as a bare episode list instead of Lucent's series page with the season tabs. Set it once
    to 'Never' (you can change it back in Kodi's settings; Lucent does not ask again)."""
    if xbmc.getCondVisibility("Skin.HasSetting(lucent.seasontabs.off) | !String.IsEmpty(Skin.String(lucent.flattenset))"):
        return
    import json
    req = {"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "videolibrary.flattentvshows"}}
    value = (json.loads(xbmc.executeJSONRPC(json.dumps(req))).get("result") or {}).get("value")
    if value not in (None, 0):
        req = {"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue",
               "params": {"setting": "videolibrary.flattentvshows", "value": 0}}
        log(f"flatten seasons {value} -> 0: {xbmc.executeJSONRPC(json.dumps(req))}")
    xbmc.executebuiltin("Skin.SetString(lucent.flattenset,1)")


def run():
    xbmc.executebuiltin("Skin.Reset(nuvio.osdstats)")      # the old player-info overlay: now its own window (playerinfo.py)
    step("season page", season_page)
    import keymap
    step("keymap", keymap.main)
    import settings
    step("logos", settings.scan_logos)
    import agenda
    step("calendar tab", agenda.ensure_tab)
    if xbmc.getCondVisibility("Pvr.HasTVChannels"):
        import sport
        step("sport tab", sport.ensure_tab)
    import helper
    helper.run()                                     # keeps running until Kodi stops or the skin is updated


if __name__ == "__main__":
    run()
