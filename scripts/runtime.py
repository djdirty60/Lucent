# -*- coding: utf-8 -*-
"""Lucent 3.0.5: the Runtime quick filter (GitHub #35).

Choose a length (shorter than 90 minutes, 2 hours, 2.5 hours, 3 hours). In the Kodi library the list itself is filtered;
in the list of a video add-on Lucent reads the list, keeps the films that fit and shows them in a list to pick from.
That needs the add-on to give the runtime of its films.

    RunScript(special://skin/scripts/runtime.py)      the Runtime button in the side panel of a film list
"""
import json
import urllib.parse

import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
HOME = xbmcgui.Window(10000)
LIMITS = (90, 120, 150, 180)
T = {
    "heading": ("Runtime", "Speelduur"),
    "shorter": ("Shorter than {0}", "Korter dan {0}"),
    "none": ("No films shorter than {0} in this list", "Geen films korter dan {0} in deze lijst"),
    "unknown": ("This list does not give the runtime of its films", "Deze lijst geeft de speelduur van de films niet door"),
    "found": ("{0} films shorter than {1}", "{0} films korter dan {1}"),
}


def tr(key, *args):
    text = T[key][1 if NL else 0]
    return text.format(*args) if args else text


def length(minutes):
    if minutes % 60 == 0:
        hours = minutes // 60
        return (f"{hours} uur" if NL else f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes < 60 or minutes == 90:
        return f"{minutes} min"
    return (f"{minutes / 60:.1f} uur".replace(".", ",") if NL else f"{minutes / 60:.1f} hours")


def duration(seconds):
    minutes = int(seconds or 0) // 60
    return f"{minutes // 60} u {minutes % 60:02d}" if NL else f"{minutes // 60} h {minutes % 60:02d}"


def log(text):
    xbmc.log(f"[skin.lucent] runtime: {text}", xbmc.LOGINFO)


def library(path, limit):
    rules = {"type": "movies", "rules": {"and": [
        {"field": "time", "operator": "lessthan", "value": ["%02d:%02d:01" % divmod(limit, 60)]},
        {"field": "time", "operator": "greaterthan", "value": ["00:00:00"]}]}}
    xbmc.executebuiltin(f"Container.Update(videodb://movies/titles/?xsp={urllib.parse.quote(json.dumps(rules))})")


def addon_list(path, limit):
    xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
    try:
        query = {"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                 "params": {"directory": path, "media": "video",
                            "properties": ["title", "runtime", "art", "year", "rating", "file", "uniqueid", "plot"]}}
        files = (json.loads(xbmc.executeJSONRPC(json.dumps(query))).get("result") or {}).get("files") or []
    finally:
        xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
    films = [f for f in files if f.get("filetype") != "directory" or f.get("type") == "movie"]
    with_time = [f for f in films if int(f.get("runtime") or 0) > 0]
    log(f"{len(files)} items, {len(with_time)} with a runtime, limit {limit} min")
    if not with_time:
        xbmcgui.Dialog().notification(tr("heading"), tr("unknown"), xbmcgui.NOTIFICATION_INFO, 5000)
        return
    fit = sorted((f for f in with_time if int(f["runtime"]) <= limit * 60), key=lambda f: int(f["runtime"]))
    if not fit:
        xbmcgui.Dialog().notification(tr("heading"), tr("none", length(limit)), xbmcgui.NOTIFICATION_INFO, 5000)
        return
    items = []
    for f in fit:
        li = xbmcgui.ListItem(f.get("title") or f.get("label") or "")
        li.setLabel2("  ·  ".join(x for x in (duration(f["runtime"]), str(f.get("year") or "")) if x and x != "0"))
        art = f.get("art") or {}
        poster = art.get("poster") or art.get("thumb") or art.get("icon") or ""
        li.setArt({"thumb": poster, "icon": poster, "poster": poster})
        items.append(li)
    pick = xbmcgui.Dialog().select(tr("found", len(fit), length(limit)), items, useDetails=True)
    if pick < 0:
        return
    chosen = fit[pick]
    target = chosen.get("file") or ""
    tmdb = str((chosen.get("uniqueid") or {}).get("tmdb") or "")
    if chosen.get("filetype") == "directory":
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{target}",return)')
    elif tmdb.isdigit() and xbmc.getCondVisibility("Skin.HasSetting(nuvio.ok.movie.page)"):
        HOME.setProperty("nuvio.open.tmdb", tmdb)
        HOME.setProperty("nuvio.open.type", "movie")
        HOME.clearProperty("nuvio.open.trakt")
        xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,open,path)")
    else:
        xbmc.executebuiltin(f'PlayMedia("{target}")')


def main():
    path = xbmc.getInfoLabel("Container.FolderPath")
    pick = xbmcgui.Dialog().select(tr("heading"), [tr("shorter", length(m)) for m in LIMITS])
    if pick < 0:
        return
    limit = LIMITS[pick]
    if path.startswith(("videodb://", "library://")):
        library(path, limit)
    else:
        addon_list(path, limit)


if __name__ == "__main__":
    main()
