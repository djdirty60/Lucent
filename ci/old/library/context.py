# -*- coding: utf-8 -*-
"""Lucent Library: Seren's options on a film or episode in the Kodi library (long press OK / menu button).

The library items are small .strm files with Seren's address in them; this reads that address and asks Seren for
the chosen action: choose a source, search again (rescrape), Trakt manager, or open the series in Seren.
"""
import json
import sys
import urllib.parse

import xbmc
import xbmcvfs

SEREN = "plugin://plugin.video.seren/"


def strm_address(path):
    try:
        with xbmcvfs.File(path) as fh:
            return (fh.read() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "select"
    item = sys.listitem                              # noqa: F821 - given by Kodi to context scripts
    path = item.getPath() or xbmc.getInfoLabel("ListItem.FileNameAndPath")
    address = strm_address(path)
    if not address.startswith(SEREN) or "action_args=" not in address:
        xbmc.log(f"[script.lucent.library] context: no Seren address in {path}", xbmc.LOGWARNING)
        return
    query = dict(urllib.parse.parse_qsl(address.split("?", 1)[1]))
    args = query.get("action_args", "")
    if what == "select":
        xbmc.executebuiltin(f"PlayMedia({address}&source_select=true)")
    elif what == "rescrape":
        xbmc.executebuiltin(f"PlayMedia({address}&seren_reload=true)")
    elif what == "trakt":
        url = SEREN + "?" + urllib.parse.urlencode({"action": "traktManager", "action_args": args})
        xbmc.executebuiltin(f"RunPlugin({url})")
    elif what == "show":
        try:
            ids = json.loads(urllib.parse.unquote(args))
        except ValueError:
            ids = {}
        show = ids.get("trakt_show_id")
        if show:
            show_args = urllib.parse.quote(json.dumps({"mediatype": "tvshow", "trakt_id": int(show)}, sort_keys=True))
            xbmc.executebuiltin(f'ActivateWindow(Videos,"{SEREN}?action=showSeasons&action_args={show_args}",return)')


main()
