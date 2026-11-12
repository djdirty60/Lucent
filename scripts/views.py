"""Lucent: remember the view per kind of content (Settings > Lucent > Remember view per kind).

Kodi remembers a view per folder, so every new series opens in the default view again. With this on, Lucent notes the
view you pick for a kind of content (films, series, seasons, episodes, albums, ...) and uses it in every folder of
that kind. The helper calls tick() several times a second.
Kept in Skin.String(lucent.view.<window>.<content>), for example lucent.view.videos.episodes = 55.
"""
import time

import xbmc

OFF = "Skin.HasSetting(lucent.view.remember.off)"
WINDOWS = {"videos": (56, 51, 52, 57, 55, 53, 50, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 86, 87), "music": (50, 54, 52, 81, 82, 83, 84, 85)}
STATE = {"key": "", "path": "", "since": 0.0, "view": 0, "applied": 0, "until": 0.0, "restore": None}
# issue #9: the title you were on in a folder (Films, Series ...), so going back into it starts there again
POSITIONS = {}


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
    opened = not STATE["path"]                                # the window was just opened (not a step inside it)
    key = f"lucent.view.{window}.{content}"
    view = visible_view(WINDOWS[window])
    now = time.time()
    if path != STATE["path"] or key != STATE["key"]:
        # a new folder: bring the view chosen for this kind, once
        STATE.update(path=path, key=key, since=now, view=view, applied=0, until=0.0,
                     restore=POSITIONS.get(path) if opened else None)
        saved = label(f"Skin.String({key})")
        if saved.isdigit() and int(saved) != view and int(saved) in WINDOWS[window]:
            xbmc.executebuiltin(f"Container.SetViewMode({saved})")
            STATE.update(applied=int(saved), until=now + 2.0)
        return
    if STATE["restore"] and now - STATE["since"] > 0.4:
        restore(view)
    elif view and now - STATE["since"] > 1.0:
        remember(path)
    if view and view != STATE["view"]:
        if STATE["applied"] and view == STATE["applied"] and now < STATE["until"]:
            STATE["view"] = view                              # our own change
            return
        STATE["view"] = view
        if now - STATE["since"] > 0.8:                        # the user picked another view: remember it for this kind
            xbmc.executebuiltin(f"Skin.SetString({key},{view})")
            xbmc.log(f"[skin.lucent] views: {key} = {view}", xbmc.LOGINFO)


def remember(path):
    item = label("ListItem.Label")
    if item and item != "..":
        POSITIONS[path] = (item, label("ListItem.FileNameAndPath"))
        if len(POSITIONS) > 60:
            POSITIONS.pop(next(iter(POSITIONS)))


def restore(view):
    """Back on the title you were on when you left this folder (found by its name and file, not by number)."""
    item, file = STATE["restore"]
    STATE["restore"] = None
    if not view or label("ListItem.Label") == item:
        return
    total = int(label("Container.NumItems") or 0)
    for i in range(min(total + 1, 3000)):
        if label(f"Container({view}).ListItemAbsolute({i}).Label") == item and \
                (not file or label(f"Container({view}).ListItemAbsolute({i}).FileNameAndPath") == file):
            xbmc.executebuiltin(f"SetFocus({view},{i},absolute)")
            return


def choose_s56_episodes():
    """Season page: how the episodes are shown - a row (as before), a timeline, cards or a list with flags."""
    import xbmcgui
    names = [xbmc.getLocalizedString(n) for n in (31868, 31850, 31851, 31854)]
    keys = ["", "timeline", "cards", "flags"]
    now = label("Skin.String(lucent.s56.eps)")
    pick = xbmcgui.Dialog().select(xbmc.getLocalizedString(31867), names, preselect=keys.index(now) if now in keys else 0)
    if pick < 0:
        return
    if keys[pick]:
        xbmc.executebuiltin(f"Skin.SetString(lucent.s56.eps,{keys[pick]})")
    else:
        xbmc.executebuiltin("Skin.Reset(lucent.s56.eps)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "s56eps":
        choose_s56_episodes()
