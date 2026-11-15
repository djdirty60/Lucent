# -*- coding: utf-8 -*-
"""Lucent 2.1.21: the resume question for a half-watched film or episode of the Kodi library (Lucent_Resume.xml),
in the look of the video add-on's own resume screen, instead of Kodi's small menu.

    RunScript(special://skin/scripts/resume.py)        from OK on a Home row (the item under the cursor)

Continue watching / Start over plays the library item itself (Player.Open with its id), so Kodi resumes, marks it as
watched and keeps the library up to date as always. Back closes without playing. Titles of the video add-on's own
library keep that add-on's screen (Includes_Player.xml: LucentLibOwnResume)."""
import json

import xbmc
import xbmcaddon
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
CLOSE = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] resume: {text}", xbmc.LOGINFO)


def rpc(method, params):
    res = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return res.get("result") or {}


def clock(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}" if seconds >= 3600 else f"{seconds // 60}:{seconds % 60:02d}"


def details(kind, dbid):
    fields = ["title", "plot", "resume", "art", "runtime", "file"]
    if kind == "episode":
        return rpc("VideoLibrary.GetEpisodeDetails", {"episodeid": dbid, "properties": fields + ["showtitle", "season", "episode"]}).get("episodedetails") or {}
    return rpc("VideoLibrary.GetMovieDetails", {"movieid": dbid, "properties": fields + ["year"]}).get("moviedetails") or {}


def art(item, *keys):
    for key in keys:
        value = (item.get("art") or {}).get(key) or ""
        if value:
            return value
    return ""


class Resume(xbmcgui.WindowXMLDialog):
    def setup(self, info):
        self.info, self.choice = info, None

    def onInit(self):
        for key, value in self.info.items():
            self.setProperty(key, value)
        try:
            self.getControl(50).setPercent(float(self.info.get("percent") or 0))
        except (RuntimeError, TypeError, ValueError):
            pass
        self.setFocusId(10)

    def onClick(self, cid):
        if cid in (10, 11):
            self.choice = cid == 10
            self.close()

    def onAction(self, action):
        if action.getId() in CLOSE:
            self.choice = None
            self.close()


def addon_item(path):
    """An add-on's own title (not in the library): the add-on keeps where you stopped and gives it with the tile. Kodi
    has no info label with the exact second, so ask the add-on's folder again for the item (its 'resume'); when that
    fails, go by the percentage on the tile (rounded down: a little earlier, never later)."""
    cid = xbmc.getInfoLabel("System.CurrentControlID")
    folder = xbmc.getInfoLabel(f"Container({cid}).FolderPath") if cid.isdigit() else ""
    item = {"file": path, "title": xbmc.getInfoLabel("ListItem.Title") or xbmc.getInfoLabel("ListItem.Label"),
            "showtitle": xbmc.getInfoLabel("ListItem.TVShowTitle"), "season": xbmc.getInfoLabel("ListItem.Season"),
            "episode": xbmc.getInfoLabel("ListItem.Episode"), "year": xbmc.getInfoLabel("ListItem.Year"),
            "plot": xbmc.getInfoLabel("ListItem.Plot"),
            "art": {k: xbmc.getInfoLabel(f"ListItem.Art({k})") for k in ("thumb", "fanart", "landscape", "poster", "tvshow.fanart")}}
    try:
        duration = float(xbmc.getInfoLabel("ListItem.Duration(secs)") or 0)
    except ValueError:
        duration = 0.0
    try:
        percent = float(xbmc.getInfoLabel("ListItem.PercentPlayed") or 0)
    except ValueError:
        percent = 0.0
    item["resume"] = {"position": int(duration * percent / 100), "total": duration}
    if folder.startswith("plugin://"):
        files = rpc("Files.GetDirectory", {"directory": folder, "media": "video", "properties": ["resume"]}).get("files") or []
        found = next((f for f in files if f.get("file") == path), None)
        if found and (found.get("resume") or {}).get("position"):
            item["resume"] = found["resume"]
    return item


def main():
    kind = xbmc.getInfoLabel("ListItem.DBType")
    dbid = xbmc.getInfoLabel("ListItem.DBID")
    path = xbmc.getInfoLabel("ListItem.FilenameAndPath")
    library = kind in ("movie", "episode") and dbid.isdigit() and int(dbid) > 0
    if library:
        item = details(kind, int(dbid))
        source = t("From your library", "Uit je bibliotheek")
    elif path.startswith("plugin://"):
        item = addon_item(path)
        addon_id = path.split("/")[2]
        try:
            source = xbmcaddon.Addon(addon_id).getAddonInfo("name")
        except RuntimeError:
            source = ""
    else:
        log(f"not a library or add-on title ({kind or '-'} {dbid or '-'}): Kodi plays it")
        if path:
            xbmc.executebuiltin(f'PlayMedia("{path}")')
        return
    res = item.get("resume") or {}
    position, total = float(res.get("position") or 0), float(res.get("total") or 0) or float(item.get("runtime") or 0)
    key = "episodeid" if kind == "episode" else "movieid"

    def play(resume):
        if library:
            rpc("Player.Open", {"item": {key: int(dbid)}, "options": {"resume": bool(resume)}})
            return
        li = xbmcgui.ListItem(item.get("title") or "", offscreen=True)
        li.setProperty("StartOffset", f"{position:.1f}" if resume else "0")
        xbmc.Player().play(path, li)

    if position <= 0:                                   # nothing to resume after all: just play
        play(False)
        return
    if kind == "episode" or item.get("showtitle"):
        title = item.get("showtitle") or item.get("title") or ""
        where = t(f"S{item.get('season')} · E{item.get('episode')} · ", f"S{item.get('season')} · A{item.get('episode')} · ") \
            if str(item.get("season") or "").isdigit() and str(item.get("episode") or "").isdigit() else ""
        thumb = art(item, "thumb", "tvshow.fanart", "tvshow.landscape", "fanart")
        fanart = art(item, "tvshow.fanart", "fanart", "thumb")
    else:
        title = item.get("title") or ""
        where = f"{item.get('year')} · " if item.get("year") else ""
        thumb = art(item, "landscape", "fanart", "thumb", "poster")
        fanart = art(item, "fanart", "landscape")
    left = max(0, total - position)
    stopped = where + t(f"Stopped at {clock(position)}", f"Gestopt bij {clock(position)}")
    if left >= 60:
        stopped += t(f" · {int(left // 60)} min left", f" · nog {int(left // 60)} min")
    info = {
        "caps": t("CONTINUE WATCHING", "VERDER KIJKEN"), "title": title, "stopped": stopped,
        "thumb": thumb, "fanart": fanart, "percent": f"{position * 100 / total:.1f}" if total else "0",
        "plot_head": t("What it's about", "Waar gaat het over"), "plot": item.get("plot") or "",
        "source": source,
        "resume_label": t("Continue watching", "Verder kijken"), "start_label": t("Start over", "Opnieuw beginnen"),
    }
    win = Resume("Lucent_Resume.xml", xbmcaddon.Addon("skin.lucent").getAddonInfo("path"), "Default", "1080i")
    win.setup(info)
    win.doModal()
    choice = win.choice
    del win
    if choice is None:
        return
    log(f"{'library ' + kind + ' ' + dbid if library else path[:60]}: {'resume at ' + clock(position) if choice else 'from the start'}")
    play(choice)


if __name__ == "__main__":
    main()
