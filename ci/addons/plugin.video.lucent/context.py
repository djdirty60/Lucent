# -*- coding: utf-8 -*-
"""Lucent Video's own options in the menu of a title in the Kodi library (the titles Lucent Video put there)."""
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

import xbmc  # noqa: E402
import xbmcvfs  # noqa: E402

import util  # noqa: E402


def _read(path):
    handle = xbmcvfs.File(path)
    try:
        return handle.read()
    finally:
        handle.close()


def _from_strm(path):
    """The .strm holds the play address with the TMDB id, season and episode."""
    text = _read(path).strip() if path.endswith(".strm") else ""
    query = dict(urllib.parse.parse_qsl(text.split("?", 1)[1])) if "?" in text else {}
    return query if query.get("tmdb") else None


def _show_id(folder):
    text = _read(folder.rstrip("/\\") + "/tvshow.nfo")
    found = re.search(r'<uniqueid type="tmdb"[^>]*>(\d+)<', text)
    return found.group(1) if found else ""


def target(item):
    tag = item.getVideoInfoTag()
    kind = tag.getMediaType()
    if kind in ("movie", "episode"):
        query = _from_strm(tag.getFilenameAndPath() or xbmc.getInfoLabel("ListItem.FileNameAndPath") or item.getPath())
        if query:
            return {"type": query["type"], "tmdb": query["tmdb"], "season": query.get("season"), "episode": query.get("episode")}
        return None
    tmdb_id = tag.getUniqueID("tmdb")
    if not tmdb_id:
        folder = xbmc.getInfoLabel("ListItem.Path")
        if kind == "season":
            folder = os.path.dirname(folder.rstrip("/\\"))
        tmdb_id = _show_id(folder)
    if not tmdb_id:
        return None
    meta = {"type": "tvshow", "tmdb": tmdb_id}
    if kind == "season":
        meta["season"] = tag.getSeason()
    return meta


def main(what):
    item = sys.listitem
    meta = target(item)
    if not meta:
        util.notify(util.T("Deze titel komt niet van Lucent Video", "This title does not come from Lucent Video"))
        return
    seen = item.getVideoInfoTag().getPlayCount() > 0
    clean = {k: v for k, v in meta.items() if v not in (None, "")}
    if what == "source":
        xbmc.executebuiltin("PlayMedia(%s)" % util.url_for(action="play", select=1, **clean))
    elif what == "watched":
        xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="watched", value=0 if seen else 1, **clean))
    elif what in ("watchlist_add", "watchlist_remove"):
        xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="watchlist", value=1 if what == "watchlist_add" else 0, **clean))
    elif what == "trailer":
        xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="trailer", type=meta["type"], tmdb=meta["tmdb"]))
    elif what == "cast":
        xbmc.executebuiltin("ActivateWindow(Videos,%s,return)" % util.url_for(action="cast", type=meta["type"], tmdb=meta["tmdb"]))
    elif what == "similar":
        xbmc.executebuiltin("ActivateWindow(Videos,%s,return)" % util.url_for(action="list", name="similar", type=meta["type"], tmdb=meta["tmdb"]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
