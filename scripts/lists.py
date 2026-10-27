# -*- coding: utf-8 -*-
"""Nuvio Arc skin helper: pick Trakt lists (via Seren) to show as rows on the home screen.

Run from the skin with  RunScript(special://skin/scripts/lists.py)        -> choose lists
                    or  RunScript(special://skin/scripts/lists.py,clear)  -> remove all list rows
"""
import json
import re
import sys

import xbmc
import xbmcgui

MAX_ROWS = 6
SEREN = "plugin://plugin.video.seren/"
SOURCES = [
    ("myLikedLists", "movies", 31082, 31003),
    ("myLikedLists", "shows", 31082, 31004),
    ("myTraktLists", "movies", 31081, 31003),
    ("myTraktLists", "shows", 31081, 31004),
]


def loc(string_id):
    return xbmc.getLocalizedString(string_id)


def clean(label):
    label = re.sub(r"\[/?(COLOR|B|I|UPPERCASE|LOWERCASE|CAPITALIZE)[^\]]*\]", "", label or "")
    return label.strip()


def quote(value):
    """Wrap a builtin argument in quotes so commas and brackets survive."""
    return '"' + value.replace('"', "'") + '"'


def get_directory(path):
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Files.GetDirectory",
        "params": {"directory": path, "media": "files", "properties": ["title", "file"]},
    }
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
        return response.get("result", {}).get("files", []) or []
    except Exception as error:  # noqa: BLE001 - never crash the skin
        xbmc.log(f"[skin.nuvioarc] lists.py could not read {path}: {error}", xbmc.LOGWARNING)
        return []


def current_rows():
    rows = []
    for n in range(1, MAX_ROWS + 1):
        path = xbmc.getInfoLabel(f"Skin.String(nuvio.list{n}.path)")
        if path:
            rows.append(path)
    return rows


def clear_rows():
    for n in range(1, MAX_ROWS + 1):
        xbmc.executebuiltin(f"Skin.Reset(nuvio.list{n}.path)")
        xbmc.executebuiltin(f"Skin.Reset(nuvio.list{n}.label)")


def choose():
    if not xbmc.getCondVisibility("System.HasAddon(plugin.video.seren)"):
        xbmcgui.Dialog().ok("Nuvio Arc", loc(31030))
        return

    progress = xbmcgui.DialogProgress()
    progress.create("Nuvio Arc", loc(31090))
    options = []
    for step, (action, mediatype, kind_id, type_id) in enumerate(SOURCES):
        progress.update(int(step * 100 / len(SOURCES)))
        if progress.iscanceled():
            break
        for entry in get_directory(f"{SEREN}?action={action}&mediatype={mediatype}"):
            path = entry.get("file", "")
            name = clean(entry.get("label") or entry.get("title"))
            if not path or not name or "action=traktList" not in path:
                continue
            options.append((f"{name}  ·  {loc(type_id)}", name, path, f"{loc(kind_id)} · {loc(type_id)}"))
    progress.close()

    # de-duplicate on path, keep order
    seen, unique = set(), []
    for option in options:
        if option[2] not in seen:
            seen.add(option[2])
            unique.append(option)
    options = unique

    if not options:
        xbmcgui.Dialog().ok("Nuvio Arc", loc(31091))
        return

    items = []
    for display, _name, _path, sub in options:
        item = xbmcgui.ListItem(display, sub)
        item.setArt({"icon": "icons/trakt.png"})
        items.append(item)
    selected_paths = current_rows()
    preselect = [i for i, option in enumerate(options) if option[2] in selected_paths]

    chosen = xbmcgui.Dialog().multiselect(loc(31027), items, preselect=preselect, useDetails=True)
    if chosen is None:
        return
    if len(chosen) > MAX_ROWS:
        xbmcgui.Dialog().notification("Nuvio Arc", loc(31092), xbmcgui.NOTIFICATION_INFO, 4000)
        chosen = chosen[:MAX_ROWS]

    clear_rows()
    for n, index in enumerate(chosen, start=1):
        _display, name, path, _sub = options[index]
        xbmc.executebuiltin(f"Skin.SetString(nuvio.list{n}.path,{quote(path)})")
        xbmc.executebuiltin(f"Skin.SetString(nuvio.list{n}.label,{quote(name)})")
    xbmcgui.Dialog().notification("Nuvio Arc", loc(31093).format(len(chosen)), xbmcgui.NOTIFICATION_INFO, 3000)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_rows()
    else:
        choose()
