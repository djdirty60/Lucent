# -*- coding: utf-8 -*-
"""Lucent 3.0.10: the best episode of the season you are looking at (the highest score in the list).

The background helper calls tick() a few times a second. When an episode list opens (the season page or an episode
list), it reads the scores the list gives (ListItem.Rating: TMDB in a library scraped from TMDB) and marks the
highest one. The lists show it with a 'Best' label next to the score (expression LucentBestEp).

Window(home).Property:
  lucent.best.path   the folder the mark belongs to (Container.FolderPath)
  lucent.best.s / .e season and episode number of the best episode
"""
import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)
STATE = {"path": "", "count": -1}


def log(text):
    xbmc.log(f"[skin.lucent] bestep: {text}", xbmc.LOGINFO)


def clear():
    if HOME.getProperty("lucent.best.path"):
        for p in ("path", "s", "e"):
            HOME.clearProperty("lucent.best." + p)


def tick():
    if not xbmc.getCondVisibility("Window.IsActive(videos) + Container.Content(episodes)"):
        STATE.update(path="", count=-1)
        clear()
        return
    path = xbmc.getInfoLabel("Container.FolderPath")
    box = "Container"                       # the list of the view; on the season page its episode cards (5601)
    if int(xbmc.getInfoLabel("Container(5601).NumItems") or 0) > 0 and xbmc.getCondVisibility("Control.IsVisible(5601)"):
        box = "Container(5601)"
    count = int(xbmc.getInfoLabel(f"{box}.NumItems") or 0)
    if path == STATE["path"] and count == STATE["count"]:
        return
    STATE.update(path=path, count=count)
    scores = []
    for i in range(min(count, 60)):
        raw = xbmc.getInfoLabel(f"{box}.ListItemAbsolute({i}).Rating")
        try:
            score = float(raw.replace(",", "."))
        except ValueError:
            continue
        if score > 0:
            scores.append((score, xbmc.getInfoLabel(f"{box}.ListItemAbsolute({i}).Season"),
                           xbmc.getInfoLabel(f"{box}.ListItemAbsolute({i}).Episode")))
    if len(scores) < 3:                     # too few scores to call one the best
        log(f"{len(scores)} scores in {count} items: no best")
        clear()
        return
    scores.sort(reverse=True)
    if scores[0][0] == scores[1][0]:        # a tie: no single best
        clear()
        return
    best = scores[0]
    HOME.setProperty("lucent.best.s", best[1])
    HOME.setProperty("lucent.best.e", best[2])
    HOME.setProperty("lucent.best.path", path)
    log(f"best of {len(scores)}: S{best[1]}E{best[2]} {best[0]}")
