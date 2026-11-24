# -*- coding: utf-8 -*-
"""Lucent 2.1.51: the menu key (or holding OK) in the Kodi video lists.

On the episodes row of the series page (list 5601 of view 56) Kodi would open the menu of the selected *season* (its
media list), not of the episode under the cursor. There this script shows the menu of the episode itself: the video
add-on's options for titles it put in the library (with the episode's details as parameters) and Kodi's basic ones.
Everywhere else it opens Kodi's normal menu.

    RunScript(special://skin/scripts/ctx.py)     from the keymap (keymap.py, lucent-ctx.xml)
"""
import json
import urllib.parse

import xbmc
import xbmcgui

EPISODES = "5601"
VIDEO = "plugin.video.lucent"
HOME = xbmcgui.Window(10000)


def log(text):
    xbmc.log(f"[skin.lucent] ctx: {text}", xbmc.LOGINFO)


def rpc(method, params):
    answer = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return answer.get("result")


def video_text(number):
    try:
        import xbmcaddon
        return xbmcaddon.Addon(VIDEO).getLocalizedString(number)
    except Exception:  # noqa: BLE001 - not installed
        return ""


def show_info(episodeid):
    """3.0.0: the information page of this episode (Kodi's own Info would show the selected season)."""
    props = ["title", "plot", "season", "episode", "showtitle", "firstaired", "runtime", "rating", "playcount", "file",
             "art", "uniqueid", "director", "writer", "resume", "tvshowid"]
    details = (rpc("VideoLibrary.GetEpisodeDetails", {"episodeid": episodeid, "properties": props}) or {}).get("episodedetails")
    if not details:
        return
    li = xbmcgui.ListItem(details.get("title", ""), path=details.get("file", ""))
    tag = li.getVideoInfoTag()
    tag.setMediaType("episode")
    tag.setDbId(episodeid)
    tag.setTitle(details.get("title", ""))
    tag.setTvShowTitle(details.get("showtitle", ""))
    tag.setSeason(int(details.get("season") or 0))
    tag.setEpisode(int(details.get("episode") or 0))
    tag.setPlot(details.get("plot", ""))
    tag.setFirstAired(details.get("firstaired", ""))
    tag.setDuration(int(details.get("runtime") or 0))
    tag.setRating(float(details.get("rating") or 0))
    tag.setPlaycount(int(details.get("playcount") or 0))
    tag.setDirectors(details.get("director") or [])
    tag.setWriters(details.get("writer") or [])
    tag.setUniqueIDs(details.get("uniqueid") or {})
    resume = details.get("resume") or {}
    if resume.get("position"):
        tag.setResumePoint(float(resume["position"]), float(resume.get("total") or 0))
    li.setArt({k: urllib.parse.unquote(v[8:-1]) if v.startswith("image://") else v for k, v in (details.get("art") or {}).items()})
    xbmcgui.Dialog().info(li)


def episode_menu():
    pre = f"Container({EPISODES}).ListItem."
    label = xbmc.getInfoLabel
    item = {k: label(pre + v) for k, v in (
        ("dbtype", "DBTYPE"), ("dbid", "DBID"), ("file", "FileNameAndPath"), ("path", "Path"), ("folder", "FolderPath"),
        ("tmdb", "UniqueID(tmdb)"), ("season", "Season"), ("episode", "Episode"), ("playcount", "PlayCount"),
        ("tvshowid", "TvShowDBID"), ("title", "Title"))}
    # 3.0.0: only for an episode in the Kodi library; an episode from an add-on folder (a Lucent Video widget) keeps Kodi's
    # own menu, with the buttons the add-on put on it (a script cannot read those)
    if not (item["dbid"].isdigit() or any(f"{VIDEO}/library" in item[k] for k in ("file", "path", "folder"))):
        xbmc.executebuiltin("Action(ContextMenu)")
        return
    watched = (item["playcount"] or "0").isdigit() and int(item["playcount"] or 0) > 0
    resumable = xbmc.getCondVisibility(f"Container({EPISODES}).ListItem.IsResumable")
    entries = []                                     # (label, what) - what: a video add-on action or one of ours
    if xbmc.getCondVisibility(f"System.HasAddon({VIDEO})") and any(
            f"{VIDEO}/library" in item[k] for k in ("file", "path", "folder")):
        for number, what in ((32560, "tonight"), (32130, "source"), (32132 if watched else 32131, "watched")) + \
                ((32299, "resume"),) * bool(resumable) + ((32186, "skiplib"),):
            text = video_text(number)
            if text:
                entries.append((text, "lucent:" + what))
    entries.append((xbmc.getLocalizedString(208), "play"))
    if item["dbid"].isdigit() and item["dbtype"] == "episode":
        entries.append((xbmc.getLocalizedString(19033), "info"))      # Kodi's "Information"
    if item["dbid"].isdigit() and item["dbtype"] == "episode":
        entries.append((xbmc.getLocalizedString(16104 if watched else 16103), "kodiwatched"))
    HOME.setProperty("lucent.ctx.own", "1")          # DialogContextMenu.xml: hide its fixed buttons (they show the season)
    try:
        choice = xbmcgui.Dialog().contextmenu([e[0] for e in entries])
    finally:
        HOME.clearProperty("lucent.ctx.own")
    if choice < 0:
        return
    what = entries[choice][1]
    log(f"{what} on {item['dbtype']} {item['dbid'] or item['file']}")
    if what.startswith("lucent:"):
        query = {"action": "library_ctx", "what": what[7:]}
        query.update({k: v for k, v in item.items() if v and k != "title"})
        xbmc.executebuiltin(f"RunPlugin(plugin://{VIDEO}/?{urllib.parse.urlencode(query)})")
    elif what == "play":
        if item["dbid"].isdigit() and item["dbtype"] == "episode":
            rpc("Player.Open", {"item": {"episodeid": int(item["dbid"])}, "options": {"resume": True}})
        else:
            xbmc.executebuiltin(f"SetFocus({EPISODES})")
            xbmc.executebuiltin("Action(Select)")
    elif what == "info":
        show_info(int(item["dbid"]))
    elif what == "kodiwatched":
        rpc("VideoLibrary.SetEpisodeDetails", {"episodeid": int(item["dbid"]), "playcount": 0 if watched else 1})
        xbmc.executebuiltin("Container.Refresh")


def main():
    if xbmc.getSkinDir() != "skin.lucent":         # 3.0.4 (#37): an old Lucent keymap under another skin
        xbmc.executebuiltin("Action(ContextMenu)")
        return
    # 3.0.17: a Python dialog on top (the video add-on's source list, ...) gets the menu key itself; the <videos>
    # keymap section brought it here and Kodi's menu then opened for the film in the list under it
    dialog = xbmcgui.getCurrentWindowDialogId()
    if dialog >= 13000:
        xbmc.log(f"[skin.lucent] ctx: menu key to dialog {dialog}", xbmc.LOGINFO)
        xbmc.executebuiltin(f"Action(ContextMenu,{dialog})")
        return
    if xbmc.getCondVisibility("Window.IsActive(videos)") and xbmc.getInfoLabel("System.CurrentControlID") == EPISODES:
        episode_menu()
    else:
        xbmc.executebuiltin("Action(ContextMenu)")


if __name__ == "__main__":
    main()
