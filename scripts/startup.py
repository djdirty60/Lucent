# -*- coding: utf-8 -*-
"""Lucent: everything that has to happen once when Kodi starts, in ONE Python start.

    RunScript(special://skin/scripts/startup.py)      from Home.xml, only the first time Home opens

Before this, Home started five or six separate scripts at the same time (key maps, rating logos, the Calendar and
Sport tabs, the helper). Every one of them is its own Python interpreter, and on a small box they all compete with
the video add-on and the widgets that load at that moment. Now the quick jobs run here after each other, and the long-running
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


LUCENT_ADDONS = ("skin.lucent", "plugin.video.lucent", "service.subtitles.lucent", "repository.lucent", "screensaver.lucent")


def fresh_icons():
    """Kodi keeps a copy of every add-on icon and only looks at the file again after a day, so a new icon showed in
    the info window but not in the lists. After an update of a Lucent add-on, its old copies are thrown away."""
    import json

    def rpc(method, params):
        return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    for addon in LUCENT_ADDONS:
        version = xbmc.getInfoLabel(f"System.AddonVersion({addon})")
        key = f"lucent.iconver.{addon}"
        if not version or xbmc.getInfoLabel(f"Skin.String({key})") == version:
            continue
        found = (rpc("Textures.GetTextures", {"properties": ["url"], "filter": {"field": "url", "operator": "contains",
                                                                                "value": f"/addons/{addon}/"}})
                 .get("result") or {}).get("textures") or []
        gone = 0
        for tex in found:
            if any(tex.get("url", "").lower().endswith(name) for name in ("icon.png", "fanart.jpg", "fanart.png")):
                rpc("Textures.RemoveTexture", {"textureid": tex["textureid"]})
                gone += 1
        log(f"{addon} {version}: {gone} old icon copies removed")
        xbmc.executebuiltin(f"Skin.SetString({key},{version})")


def run():
    xbmc.executebuiltin("Skin.Reset(nuvio.osdstats)")      # the old player-info overlay: now its own window (playerinfo.py)
    step("season page", season_page)
    step("fresh icons", fresh_icons)
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
