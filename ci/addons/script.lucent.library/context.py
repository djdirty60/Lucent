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


def from_tmdb(path):
    """Seren's address of a film in a Lucent row: its TMDb number, looked up on Trakt."""
    query = dict(urllib.parse.parse_qsl(path.split("?", 1)[1]))
    tmdb = query.get("tmdb") or ""
    if query.get("type") != "movie" or not tmdb.isdigit():
        return ""
    try:
        import quick
        for entry in quick.Trakt().call(f"search/tmdb/{tmdb}?type=movie") or []:
            trakt_id = ((entry.get("movie") or {}).get("ids") or {}).get("trakt")
            if trakt_id:
                args = quick.seren_args({"mediatype": "movie", "trakt_id": int(trakt_id)})
                return f"{SEREN}?action=getSources&action_args={args}"
    except Exception as error:  # noqa: BLE001
        xbmc.log(f"[script.lucent.library] context: Trakt lookup for TMDb {tmdb}: {error}", xbmc.LOGWARNING)
    return ""


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "select"
    if what == "addlib":                             # a film or series in a row: into your library in one go (the skin does it)
        xbmc.executebuiltin("RunScript(special://skin/scripts/info.py,quickadd)")
        return
    item = sys.listitem                              # noqa: F821 - given by Kodi to context scripts
    path = item.getPath() or xbmc.getInfoLabel("ListItem.FileNameAndPath")
    # a library file (.strm with Seren's address in it), or a Seren item itself (Seren's own menu switched off)
    address = path if path.startswith(SEREN) else strm_address(path)
    if path.startswith("plugin://script.lucent.library/") and "action=tmdbopen" in path:
        address = from_tmdb(path)                    # a film in a Lucent row (TMDb / Trakt lists)
    if not address.startswith(SEREN) or "action_args=" not in address:
        xbmc.log(f"[script.lucent.library] context: no Seren address in {path}", xbmc.LOGWARNING)
        return
    query = dict(urllib.parse.parse_qsl(address.split("?", 1)[1]))
    args = query.get("action_args", "")
    try:
        ids = json.loads(urllib.parse.unquote(args))
    except ValueError:
        ids = {}
    if what == "select":
        xbmc.executebuiltin(f"PlayMedia({address}&source_select=true)")
    elif what == "rescrape":
        xbmc.executebuiltin(f"PlayMedia({address}&seren_reload=true)")
    elif what == "rescrape_select":
        xbmc.executebuiltin(f"PlayMedia({address}&seren_reload=true&source_select=true)")
    elif what == "similar":
        movie = ids.get("mediatype") == "movie"
        tid = ids.get("trakt_id") if movie else ids.get("trakt_show_id")
        if tid:
            action = "moviesRelated" if movie else "showsRelated"
            xbmc.executebuiltin(f'ActivateWindow(Videos,"{SEREN}?action={action}&action_args={tid}",return)')
    elif what == "trakt":
        url = SEREN + "?" + urllib.parse.urlencode({"action": "traktManager", "action_args": args})
        xbmc.executebuiltin(f"RunPlugin({url})")
    elif what == "show":
        show = ids.get("trakt_show_id")
        if show:
            show_args = urllib.parse.quote(json.dumps({"mediatype": "tvshow", "trakt_id": int(show)}, sort_keys=True))
            xbmc.executebuiltin(f'ActivateWindow(Videos,"{SEREN}?action=showSeasons&action_args={show_args}",return)')


main()
