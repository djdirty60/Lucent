# -*- coding: utf-8 -*-
"""Lucent 3.0.5: the Runtime quick filter (GitHub #35).

Choose a length (shorter than 90 minutes, 2 hours, 2.5 hours, 3 hours). In the Kodi library the list itself is filtered;
in the list of a video add-on (3.0.6) the list also shows only the films that fit: Lucent reads the list and shows the
films that fit in its own list (plugin.py). That needs the add-on to give the runtime of its films.

    RunScript(special://skin/scripts/runtime.py)      the Runtime button in the side panel of a film list
"""
import json
import urllib.parse

import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
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


def log(text):
    xbmc.log(f"[skin.lucent] runtime: {text}", xbmc.LOGINFO)


def library(path, limit):
    rules = {"type": "movies", "rules": {"and": [
        {"field": "time", "operator": "lessthan", "value": ["%02d:%02d:01" % divmod(limit, 60)]},
        {"field": "time", "operator": "greaterthan", "value": ["00:00:00"]}]}}
    xbmc.executebuiltin(f"Container.Update(videodb://movies/titles/?xsp={urllib.parse.quote(json.dumps(rules))})")


def addon_list(path, limit):
    """3.0.6 (#35): the list itself shows only the films that fit (Lucent's own list of them, in the same view, with all
    their information); Back gives the whole list again. Kodi cannot filter an add-on's list, so Lucent reads it."""
    if path.startswith("plugin://skin.lucent/?list=runtime"):          # already filtered: filter the original again
        path = dict(urllib.parse.parse_qsl(path.split("?", 1)[1])).get("path", path)
    query = urllib.parse.urlencode({"list": "runtime", "path": path, "max": limit})
    log(f"{path} -> {limit} min")
    xbmc.executebuiltin(f"Container.Update(plugin://skin.lucent/?{query})")


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
