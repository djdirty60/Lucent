# -*- coding: utf-8 -*-
"""Lucent: the Options button on the info page of a film, series, season, episode or collection in the Kodi library.

    RunScript(special://skin/scripts/options.py)

The same choices as Kodi's own Manage menu (which Kodi only offers from a list's context menu):
  Edit title  ·  Edit sort title  ·  Choose art  ·  Remove from library
A title from Lucent Bibliotheek is removed through it (and from your Trakt collection), otherwise it would simply
come back at the next library run.
"""
import json
import time

import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
LIB_ID = "script.lucent.library"

T = {
    "options": ("Options", "Opties"),
    "saved": ("Saved", "Opgeslagen"),
    "none": ("None (remove this picture)", "Geen (deze afbeelding weghalen)"),
    "nothing": ("No pictures found for this type", "Geen afbeeldingen gevonden voor dit soort"),
    "remove_q": ("Remove [B]{0}[/B] from the library?", "[B]{0}[/B] uit de bibliotheek halen?"),
    "remove_lucent": ("Remove [B]{0}[/B] from the library?\n\nIt is also taken out of your Trakt collection, otherwise it "
                      "would come back at the next update of Lucent Library.",
                      "[B]{0}[/B] uit de bibliotheek halen?\n\nHij gaat ook uit je Trakt-collectie, anders komt hij bij "
                      "de volgende ronde van Lucent Bibliotheek gewoon terug."),
    "removed": ("Removed from the library", "Uit de bibliotheek gehaald"),
    "remove_part": ("Remove [B]{0}[/B] of {1} from the library?\n\nIt stays out, also after the next update of Lucent Library. "
                    "Nothing changes on Trakt. Adding the series again (Library and lists) brings it back.",
                    "[B]{0}[/B] van {1} uit de bibliotheek halen?\n\nHij blijft weg, ook na de volgende ronde van Lucent Bibliotheek. "
                    "Op Trakt verandert niets. Zet je de serie opnieuw in de bibliotheek (Bibliotheek en lijsten), dan komt alles terug."),
    "season_word": ("season {0}", "seizoen {0}"),
}
ART = {"poster": ("Poster", "Poster"), "fanart": ("Background", "Achtergrond"), "clearlogo": ("Logo", "Logo"),
       "landscape": ("Landscape", "Liggend"), "banner": ("Banner", "Banner"), "clearart": ("Clear art", "Clearart"),
       "discart": ("Disc", "Disc"), "keyart": ("Key art", "Keyart"), "thumb": ("Thumbnail", "Miniatuur"),
       "characterart": ("Characters", "Personages")}
# Kodi's own words for the menu (they are translated in every language)
EDIT_TITLE, EDIT_SORT, CHOOSE_ART, REMOVE = 16105, 16107, 13511, 646
KIND = {  # dbtype: (id field, details method, set method, remove method)
    "movie": ("movieid", "VideoLibrary.GetMovieDetails", "VideoLibrary.SetMovieDetails", "VideoLibrary.RemoveMovie"),
    "tvshow": ("tvshowid", "VideoLibrary.GetTVShowDetails", "VideoLibrary.SetTVShowDetails", "VideoLibrary.RemoveTVShow"),
    "episode": ("episodeid", "VideoLibrary.GetEpisodeDetails", "VideoLibrary.SetEpisodeDetails", "VideoLibrary.RemoveEpisode"),
    "season": ("seasonid", "VideoLibrary.GetSeasonDetails", "VideoLibrary.SetSeasonDetails", None),
    "set": ("setid", "VideoLibrary.GetMovieSetDetails", "VideoLibrary.SetMovieSetDetails", None),
}


def tr(key, *args):
    text = T[key][1 if NL else 0]
    return text.format(*args) if args else text


def loc(number):
    return xbmc.getLocalizedString(number)


def log(text):
    xbmc.log(f"[skin.lucent] options: {text}", xbmc.LOGINFO)


def rpc(method, params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        answer = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    except Exception as error:  # noqa: BLE001
        log(f"{method}: {error}")
        return None
    if "error" in answer:
        log(f"{method}: {answer['error']}")
        return None
    return answer.get("result")


def info(label):
    return xbmc.getInfoLabel(f"ListItem.{label}")


class Item:
    def __init__(self):
        self.kind = info("DBType")
        self.dbid = int(info("DBID") or 0)
        self.title = info("Title") or info("Label")
        self.season = int(info("Season") or -1) if self.kind in ("season", "episode") else 0
        self.episode = int(info("Episode") or 0) if self.kind == "episode" else 0
        self.show_dbid = int(info("TvShowDBID") or 0)
        self.show_title = info("TVShowTitle")
        self.trakt = info("UniqueID(trakt)")
        self.file = (info("FileNameAndPath") or info("Path")).replace("\\", "/")

    @property
    def ok(self):
        return self.kind in KIND and self.dbid > 0

    def ref(self):
        return {KIND[self.kind][0]: self.dbid}

    def lucent(self):
        """Written by Lucent Bibliotheek (then removing must go through it)."""
        if LIB_ID in self.file and self.trakt.isdigit():
            return True
        if self.kind == "tvshow" and self.trakt.isdigit():
            details = rpc(KIND["tvshow"][1], {"tvshowid": self.dbid, "properties": ["file"]}) or {}
            return LIB_ID in (details.get("tvshowdetails") or {}).get("file", "")
        return False

    def choices(self):
        out = []
        if self.kind != "season" or self.season > 0:
            out.append(("title", loc(EDIT_TITLE)))
        if self.kind in ("movie", "tvshow"):
            out.append(("sorttitle", loc(EDIT_SORT)))
        out.append(("art", loc(CHOOSE_ART)))
        if self.kind in ("movie", "tvshow", "episode") or (self.kind == "season" and self.season >= 0):
            out.append(("remove", loc(REMOVE)))
        return out

    def show_trakt(self):
        """For an episode or season of a Lucent series: the Trakt id of the series ('' for anything else)."""
        if not self.show_dbid:
            return ""
        details = (rpc("VideoLibrary.GetTVShowDetails", {"tvshowid": self.show_dbid, "properties": ["file", "uniqueid"]}) or {}).get("tvshowdetails") or {}
        trakt = str((details.get("uniqueid") or {}).get("trakt") or "")
        return trakt if LIB_ID in details.get("file", "") and trakt.isdigit() else ""

    def code(self):
        return f"S{self.season:02d}E{self.episode:02d}" if self.kind == "episode" else f"S{self.season:02d}"


def save(item, fields):
    result = rpc(KIND[item.kind][2], dict(item.ref(), **fields))
    if result is not None:
        xbmcgui.Dialog().notification(tr("options"), tr("saved"), xbmcgui.NOTIFICATION_INFO, 2000)
        return True
    return False


def edit_text(item, field, heading):
    details = rpc(KIND[item.kind][1], dict(item.ref(), properties=[field])) or {}
    current = next(iter(details.values()), {}).get(field, "") if details else ""
    new = xbmcgui.Dialog().input(heading, defaultt=current or (item.title if field == "title" else ""))
    if new is None or new == current or (field == "title" and not new.strip()):
        return False
    return save(item, {field: new.strip()})


def choose_art(item):
    """Type list -> pictures of that type. Back from the pictures returns to the type list, back from there to Options."""
    kinds = (rpc("VideoLibrary.GetAvailableArtTypes", {"item": item.ref()}) or {}).get("availablearttypes") or []
    order = list(ART)
    kinds = sorted(set(kinds) | {"poster", "fanart"}, key=lambda k: order.index(k) if k in order else 99)
    labels = [ART.get(k, (k, k))[1 if NL else 0] for k in kinds]
    pick = 0
    while True:
        pick = xbmcgui.Dialog().select(loc(CHOOSE_ART), labels, preselect=pick)
        if pick < 0:
            return False                                         # back: to the Options menu
        kind = kinds[pick]
        found = (rpc("VideoLibrary.GetAvailableArt", {"item": item.ref(), "arttype": kind}) or {}).get("availableart") or []
        if not found:
            xbmcgui.Dialog().notification(tr("options"), tr("nothing"), xbmcgui.NOTIFICATION_INFO, 3000)
            continue
        entries = [xbmcgui.ListItem(tr("none"))]
        for n, art in enumerate(found, start=1):
            li = xbmcgui.ListItem(f"{labels[pick]} {n}")
            thumb = art.get("previewurl") or art.get("url") or ""
            li.setArt({"thumb": thumb, "icon": thumb})
            li.setProperty("full", art.get("url") or thumb)      # the big preview next to the list
            entries.append(li)
        home = xbmcgui.Window(10000)
        home.setProperty("lucent.artpick", kind)                 # DialogSelect: list to the left, big preview beside it
        try:
            choice = xbmcgui.Dialog().select(labels[pick], entries, useDetails=True, preselect=1)
        finally:
            home.clearProperty("lucent.artpick")
        if choice < 0:
            continue                                             # back: to the list of picture types
        value = None if choice == 0 else found[choice - 1].get("url")
        return save(item, {"art": {kind: value}})


def remove(item):
    if item.kind in ("episode", "season"):
        return remove_part(item)
    lucent = item.lucent()
    question = tr("remove_lucent" if lucent else "remove_q", item.title)
    if not xbmcgui.Dialog().yesno(loc(REMOVE), question):
        return False
    xbmc.executebuiltin("Dialog.Close(movieinformation)")
    if lucent:
        kind = "movie" if item.kind == "movie" else "show"
        xbmc.executebuiltin(f"RunScript({LIB_ID},remove,{kind},{item.trakt},trakt)")
    else:
        rpc(KIND[item.kind][3], item.ref())
        xbmcgui.Dialog().notification(tr("options"), tr("removed"), xbmcgui.NOTIFICATION_INFO, 2500)
    xbmc.sleep(500)
    xbmc.executebuiltin("Container.Refresh")
    return True


def remove_part(item):
    """One episode or a whole season. Of a Lucent series it goes through Lucent Bibliotheek, which keeps it out for good
    (otherwise the next run would simply bring it back); of any other series Kodi forgets the episode(s)."""
    what = item.code() if item.kind == "episode" else tr("season_word", item.season)
    show = item.show_title or item.title
    if not xbmcgui.Dialog().yesno(loc(REMOVE), tr("remove_part", what, show)):
        return False
    xbmc.executebuiltin("Dialog.Close(movieinformation)")
    trakt = item.show_trakt()
    if trakt:
        xbmc.executebuiltin(f"RunScript({LIB_ID},skip,{trakt},{item.code()})")
    elif item.kind == "episode":
        rpc("VideoLibrary.RemoveEpisode", {"episodeid": item.dbid})
        xbmcgui.Dialog().notification(tr("options"), tr("removed"), xbmcgui.NOTIFICATION_INFO, 2500)
    else:
        episodes = (rpc("VideoLibrary.GetEpisodes", {"tvshowid": item.show_dbid, "season": item.season}) or {}).get("episodes") or []
        for ep in episodes:
            rpc("VideoLibrary.RemoveEpisode", {"episodeid": ep["episodeid"]})
        xbmcgui.Dialog().notification(tr("options"), tr("removed"), xbmcgui.NOTIFICATION_INFO, 2500)
    xbmc.sleep(500)
    xbmc.executebuiltin("Container.Refresh")
    return True                                                  # removed: the menu does not come back


def reopen(item):
    """Kodi's info page does not refresh by itself: show it again with the new title or picture."""
    xbmc.executebuiltin("Container.Refresh")
    if not xbmc.getCondVisibility("Window.IsActive(videos)"):
        return
    xbmc.executebuiltin("Dialog.Close(movieinformation)")
    monitor = xbmc.Monitor()
    for _ in range(20):
        if not xbmc.getCondVisibility("Window.IsActive(movieinformation)") or monitor.waitForAbort(0.1):
            break
    for _ in range(20):                                   # wait for the refreshed list, then open the same item again
        if xbmc.getInfoLabel("Container.ListItem.DBID") == str(item.dbid) and not xbmc.getCondVisibility("Container.IsUpdating"):
            xbmc.executebuiltin("Action(Info)")
            return
        if monitor.waitForAbort(0.15):
            return


def run():
    item = Item()
    if not item.ok:
        log(f"not a library item ({item.kind} {item.dbid})")
        return
    choices = item.choices()
    pick = 0
    while True:                                                  # back from a choice returns here, back here closes
        home = xbmcgui.Window(10000)
        home.setProperty("lucent.smallselect", "1")             # DialogSelect: compact, in the middle of the screen
        try:
            pick = xbmcgui.Dialog().select(tr("options"), [label for _key, label in choices], preselect=pick)
        finally:
            home.clearProperty("lucent.smallselect")
        if pick < 0:
            return
        key = choices[pick][0]
        changed = False
        if key == "title":
            changed = edit_text(item, "title", loc(EDIT_TITLE))
        elif key == "sorttitle":
            changed = edit_text(item, "sorttitle", loc(EDIT_SORT))
        elif key == "art":
            changed = choose_art(item)
        elif key == "remove":
            if remove(item):
                return
            continue
        if changed:
            time.sleep(0.2)
            reopen(item)
            return


if __name__ == "__main__":
    run()
