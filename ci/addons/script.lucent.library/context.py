# -*- coding: utf-8 -*-
"""Lucent Library: Seren's options on a film or episode in the Kodi library (long press OK / menu button).

The library items are small .strm files with Seren's address in them; this reads that address and asks Seren for
the chosen action: choose a source, search again (rescrape), Trakt manager, or open the series in Seren.
"""
import json
import sys
import urllib.parse

import xbmc
import xbmcgui
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


def _plugin_id(path):
    return path.split("/")[2] if path.startswith("plugin://") and len(path.split("/")) > 2 else ""


def _is_fen_light(addon_id):
    """Fen Light and its clones (Red Light, ...) build seasons and episodes with mode=build_season_list / _episode_list."""
    router = f"special://home/addons/{addon_id}/resources/lib/modules/router.py"
    try:
        with xbmcvfs.File(router) as fh:
            text = fh.read()
        return "build_season_list" in text and "build_episode_list" in text
    except Exception:  # noqa: BLE001
        return False


def _is_umbrella(addon_id):
    """Umbrella and add-ons built on it (luc_kodi, ...): seasons and episodes with action=seasons / action=episodes."""
    router = f"special://home/addons/{addon_id}/resources/lib/modules/router.py"
    try:
        with xbmcvfs.File(router) as fh:
            text = fh.read()
        return "action == 'seasons'" in text and "action == 'episodes'" in text and "playcount_Episode" in text
    except Exception:  # noqa: BLE001
        return False


def browse(episodes):
    """'Browse series' / 'Browse episodes' on an episode (also on Home rows): the library, a Fen Light clone, an Umbrella clone
    (luc_kodi), Seren or TMDb Helper - whichever knows this series."""
    label = xbmc.getInfoLabel
    season = label("ListItem.Season")
    season = season if season.isdigit() else ""
    nl = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
    show_db = label("ListItem.TvShowDBID")
    if show_db.isdigit():
        target = f"videodb://tvshows/titles/{show_db}/" + (f"{season}/" if episodes and season else "")
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{target}",return)')
        return
    path = label("ListItem.FileNameAndPath") or label("ListItem.Path") or label("ListItem.FolderPath")
    addon_id = _plugin_id(path) or _plugin_id(label("Container.FolderPath"))
    tmdb = label("ListItem.UniqueID(tmdb)") or label("ListItem.Property(tmdb_id)")
    tmdb = tmdb if tmdb.isdigit() else ""
    target = ""
    if addon_id and tmdb and _is_fen_light(addon_id):
        params = {"mode": "build_episode_list" if episodes and season else "build_season_list", "tmdb_id": tmdb}
        if episodes and season:
            params["season"] = season
        target = f"plugin://{addon_id}/?" + urllib.parse.urlencode(params)
    elif addon_id and tmdb and _is_umbrella(addon_id):
        params = {"action": "episodes" if episodes and season else "seasons",
                  "tvshowtitle": label("ListItem.TVShowTitle") or label("ListItem.Title"), "year": label("ListItem.Year"),
                  "imdb": label("ListItem.UniqueID(imdb)"), "tmdb": tmdb, "tvdb": label("ListItem.UniqueID(tvdb)")}
        if episodes and season:
            params["season"] = season
        target = f"plugin://{addon_id}/?" + urllib.parse.urlencode(params)
    elif tmdb and xbmc.getCondVisibility("System.HasAddon(plugin.video.themoviedb.helper)"):
        params = {"info": "episodes" if episodes and season else "seasons", "tmdb_id": tmdb, "tmdb_type": "tv"}
        if episodes and season:
            params["season"] = season
        target = "plugin://plugin.video.themoviedb.helper/?" + urllib.parse.urlencode(params)
    if target:
        xbmc.executebuiltin(f'ActivateWindow(Videos,"{target}",return)')
        return
    xbmcgui.Dialog().notification("Lucent", "Deze serie kan Lucent hier niet openen" if nl else "Lucent cannot open this series from here",
                                  xbmcgui.NOTIFICATION_INFO, 3500)


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "select"
    if what in ("browseshow", "browseeps"):
        browse(what == "browseeps")
        return
    if what == "addwidget":                          # a folder of any add-on or of the library: a row on a Lucent tab
        item = sys.listitem                          # noqa: F821 - given by Kodi to context scripts
        home = xbmcgui.Window(10000)
        home.setProperty("lucent.addw.path", item.getPath() or xbmc.getInfoLabel("ListItem.FolderPath") or xbmc.getInfoLabel("ListItem.Path"))
        home.setProperty("lucent.addw.label", item.getLabel() or xbmc.getInfoLabel("ListItem.Label"))
        xbmc.executebuiltin("RunScript(special://skin/scripts/menu.py,addwidget)")
        return
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
