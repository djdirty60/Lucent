"""Lucent: remember the view per kind of content (Settings > Lucent > Remember view per kind).

Kodi remembers a view per folder, so every new series opens in the default view again. With this on, Lucent notes the
view you pick for a kind of content (films, series, seasons, episodes, albums, ...) and uses it in every folder of
that kind. The helper calls tick() several times a second.
Kept in Skin.String(lucent.view.<window>.<content>), for example lucent.view.videos.episodes = 55.
"""
import time

import xbmc

OFF = "Skin.HasSetting(lucent.view.remember.off)"
WINDOWS = {"videos": (56, 51, 52, 57, 55, 53, 50, 70, 71, 72, 73), "music": (50, 54, 52)}
STATE = {"key": "", "path": "", "since": 0.0, "view": 0, "applied": 0, "until": 0.0}


def cond(text):
    return xbmc.getCondVisibility(text)


def label(text):
    return xbmc.getInfoLabel(text)


def visible_view(ids):
    for view in ids:
        if cond(f"Control.IsVisible({view})"):
            return view
    return 0


def tick():
    if cond(OFF):
        return
    window = next((w for w in WINDOWS if cond(f"Window.IsActive({w})")), "")
    if not window or cond("Container.IsUpdating | System.HasActiveModalDialog"):
        STATE["path"] = "" if not window else STATE["path"]
        return
    path = label("Container.FolderPath")
    content = label("Container.Content") or "none"
    key = f"lucent.view.{window}.{content}"
    view = visible_view(WINDOWS[window])
    now = time.time()
    if path != STATE["path"] or key != STATE["key"]:
        # a new folder: bring the view chosen for this kind, once
        STATE.update(path=path, key=key, since=now, view=view, applied=0, until=0.0)
        saved = label(f"Skin.String({key})")
        if saved.isdigit() and int(saved) != view and int(saved) in WINDOWS[window]:
            xbmc.executebuiltin(f"Container.SetViewMode({saved})")
            STATE.update(applied=int(saved), until=now + 2.0)
        return
    if view and view != STATE["view"]:
        if STATE["applied"] and view == STATE["applied"] and now < STATE["until"]:
            STATE["view"] = view                              # our own change
            return
        STATE["view"] = view
        if now - STATE["since"] > 0.8:                        # the user picked another view: remember it for this kind
            xbmc.executebuiltin(f"Skin.SetString({key},{view})")
            xbmc.log(f"[skin.lucent] views: {key} = {view}", xbmc.LOGINFO)
