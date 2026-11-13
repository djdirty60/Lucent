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


def _skin(key):
    return xbmc.getInfoLabel(f"Skin.String({key})")


def first_start():
    """A new installation: the one-time jobs one after the other (they used to start as six scripts at the same time
    from Home, which made small boxes hang). Returns True when the skin reloads for the light mode."""
    import settings
    if not _skin("lucent.lite.checked"):
        step("light mode check", settings.lite_check)
    if not _skin("nuvio.migrated"):
        import migrate
        step("settings of Nuvio Arc", migrate.migrate)
        xbmc.executebuiltin('Skin.SetString(nuvio.migrated,"1")', True)
        if _skin("nuvio.menu.version"):
            step("settings", settings.sync)
    if not _skin("nuvio.menu.version"):
        import menu
        step("menu", menu.init)
    elif not _skin("lucent.addonw4"):
        import menu
        step("add-ons row", menu.addons_once)
    if xbmc.getCondVisibility("System.HasAddon(plugin.video.lucent)") and _skin("lucent.lvrows") != "done4" \
            and _skin("nuvio.menu.version"):
        import menu
        step("rows of the video add-on", menu.lv_convert)
    lite = xbmc.getCondVisibility("Skin.HasSetting(lucent.lite)")
    if lite != bool(_skin("lucent.lite.built")):
        step("light mode", settings.lite_build)      # reloads the skin: Home starts this script again
        return True
    return False


def cw_notice():
    """2.1.4: the Continue watching row from the library is no longer put on the Films and Series tabs by itself. Tell
    people who used Lucent before, once, how to add it themselves as a widget. A new installation gets no message."""
    import threading

    def show():
        import xbmcgui
        mon = xbmc.Monitor()
        mon.waitForAbort(6)                                 # let Home appear first
        for _ in range(600):                                # then wait until Home is on top, without a dialog
            if xbmc.getCondVisibility("Window.IsActive(home) + !System.HasModalDialog + !System.HasVisibleModalDialog") \
                    or mon.waitForAbort(1):
                break
        if mon.abortRequested():
            return
        nl = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
        if nl:
            head, text = "Lucent: Verder kijken", (
                "De rij [B]Verder kijken[/B] uit je bibliotheek staat niet meer vanzelf op de tabbladen Films en Series.[CR][CR]"
                "Wil je hem terug? Zet hem als widget: Menu en widgets > kies het tabblad > Widgets op deze tab > "
                "Kodi-bibliotheek > [B]Films die je kijkt[/B], [B]Series die je kijkt[/B] of [B]Afleveringen die je kijkt[/B].")
        else:
            head, text = "Lucent: Continue watching", (
                "The [B]Continue watching[/B] row from your library is no longer put on the Films and Series tabs by itself.[CR][CR]"
                "Want it back? Add it as a widget: Menu and widgets > choose the tab > Widgets on this tab > "
                "Kodi library > [B]Movies in progress[/B], [B]Shows in progress[/B] or [B]Episodes in progress[/B].")
        xbmcgui.Dialog().ok(head, text)

    if _skin("lucent.notice.cw214"):
        return
    xbmc.executebuiltin('Skin.SetString(lucent.notice.cw214,"1")')
    if _skin("lucent.setup.done"):                          # used Lucent before this version
        threading.Thread(target=show, daemon=True).start()


def run():
    if first_start():
        return
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
    if not _skin("lucent.setup.done") and not xbmc.getInfoLabel("Window(home).Property(lucent.setup.shown)"):
        xbmc.executebuiltin("RunScript(special://skin/scripts/setup.py,first)")   # the very first time, after the jobs above
    step("continue watching notice", cw_notice)
    import helper
    helper.run()                                     # keeps running until Kodi stops or the skin is updated


if __name__ == "__main__":
    run()
