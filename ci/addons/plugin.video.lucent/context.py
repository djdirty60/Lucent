# -*- coding: utf-8 -*-
"""Lucent Video's options in the context menu: on the titles in the Kodi library that Lucent Video put there, and the
items the Lucent skin needs (Add to Home, Browse series / episodes, Add to / remove from your library)."""
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib"))

import xbmc  # noqa: E402
import xbmcgui  # noqa: E402
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


def _plugin_id(path):
    return path.split("/")[2] if path.startswith("plugin://") and len(path.split("/")) > 2 else ""


def _is_fen_light(addon_id):
    """Fen Light and its clones build seasons and episodes with mode=build_season_list / build_episode_list."""
    try:
        text = _read("special://home/addons/%s/resources/lib/modules/router.py" % addon_id)
    except Exception:          # noqa: BLE001
        return False
    return "build_season_list" in text and "build_episode_list" in text


def browse(episodes):
    """'Browse series' / 'Browse episodes' on an episode: the library, Lucent Video, a Fen Light clone or TMDb Helper."""
    label = xbmc.getInfoLabel
    season = label("ListItem.Season")
    season = season if season.isdigit() else ""
    show_db = label("ListItem.TvShowDBID")
    target = ""
    if show_db.isdigit():
        target = "videodb://tvshows/titles/%s/" % show_db + ("%s/" % season if episodes and season else "")
    else:
        path = label("ListItem.FileNameAndPath") or label("ListItem.Path") or label("ListItem.FolderPath")
        addon_id = _plugin_id(path) or _plugin_id(label("Container.FolderPath"))
        tmdb = label("ListItem.Property(tmdb_id)") or label("ListItem.UniqueID(tmdb)")
        tmdb = tmdb if tmdb.isdigit() else ""
        if tmdb and addon_id == util.ADDON_ID:
            target = util.url_for(action="episodes", tmdb=tmdb, season=season) if episodes and season else util.url_for(action="seasons", tmdb=tmdb)
        elif tmdb and addon_id and _is_fen_light(addon_id):
            params = {"mode": "build_episode_list" if episodes and season else "build_season_list", "tmdb_id": tmdb}
            if episodes and season:
                params["season"] = season
            target = "plugin://%s/?%s" % (addon_id, urllib.parse.urlencode(params))
        elif tmdb and xbmc.getCondVisibility("System.HasAddon(plugin.video.themoviedb.helper)"):
            params = {"info": "episodes" if episodes and season else "seasons", "tmdb_id": tmdb, "tmdb_type": "tv"}
            if episodes and season:
                params["season"] = season
            target = "plugin://plugin.video.themoviedb.helper/?" + urllib.parse.urlencode(params)
        elif tmdb:
            target = util.url_for(action="episodes", tmdb=tmdb, season=season) if episodes and season else util.url_for(action="seasons", tmdb=tmdb)
    if target:
        xbmc.executebuiltin('ActivateWindow(Videos,"%s",return)' % target)
    else:
        util.notify(util.T("Deze serie kan Lucent hier niet openen", "Lucent cannot open this series from here"))


def add_widget(item):
    """A folder of any add-on or of the library as a row on a Lucent tab: the skin does the rest."""
    home = xbmcgui.Window(10000)
    home.setProperty("lucent.addw.path", item.getPath() or xbmc.getInfoLabel("ListItem.FolderPath") or xbmc.getInfoLabel("ListItem.Path"))
    home.setProperty("lucent.addw.label", item.getLabel() or xbmc.getInfoLabel("ListItem.Label"))
    xbmc.executebuiltin("RunScript(special://skin/scripts/menu.py,addwidget)")


def _loose_target(item):
    """A film or series in a row (not in the library): its kind and TMDB number."""
    tag = item.getVideoInfoTag()
    kind = tag.getMediaType()
    tmdb_id = item.getProperty("tmdb_id") or tag.getUniqueID("tmdb") or xbmc.getInfoLabel("ListItem.UniqueID(tmdb)")
    if kind in ("movie", "tvshow") and str(tmdb_id).isdigit():
        return {"type": kind, "tmdb": str(tmdb_id)}
    return None


def main(what):
    item = sys.listitem
    if what == "addwidget":
        return add_widget(item)
    if what in ("browseshow", "browseeps"):
        return browse(what == "browseeps")
    if what == "addlib":
        meta = _loose_target(item)
        if meta:
            xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="library_add", **meta))
        return None
    if what in ("removelib", "rate"):
        meta = _loose_target(item) or target(item)
        if meta and what == "removelib":
            xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="library_remove", type=meta["type"], tmdb=meta["tmdb"]))
        elif meta:
            xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="kompas_rate", type=meta["type"], tmdb=meta["tmdb"]))
        return None
    if what == "skiplib":
        meta = target(item)
        if meta and meta.get("season"):
            xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="library_skip", tmdb=meta["tmdb"], season=meta["season"],
                                                             episode=meta.get("episode")))
        return None
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
        xbmc.executebuiltin("RunPlugin(%s)" % util.url_for(action="cast_popup", type=meta["type"], tmdb=meta["tmdb"]))
    elif what == "similar":
        xbmc.executebuiltin("ActivateWindow(Videos,%s,return)" % util.url_for(action="list", name="similar", type=meta["type"], tmdb=meta["tmdb"]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
