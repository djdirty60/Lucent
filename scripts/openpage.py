# -*- coding: utf-8 -*-
"""Lucent: open the film / series PAGE of a title that is clicked on the info page or on a person page.

Clicking a similar title, a film of the collection or a film of an actor / director used to start the film or
open Seren's search list. This opens the page instead: it opens the Seren list that holds the title, picks the
right item (by its place for similar titles, by its year for the others) and presses Info on it.

  RunScript(openpage.py,related)   the similar title that was clicked (nuvio.open.pos = its place, 1 = first)
  RunScript(openpage.py,path)      Seren path in nuvio.open.path, the year in nuvio.open.year (may be empty)
"""
import sys
import time

import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)
WAIT_LIST = 25       # seconds for Seren to build the list
SERENPATH = "plugin://plugin.video.seren/"


def log(text):
    xbmc.log(f"[skin.lucent] openpage: {text}", xbmc.LOGINFO)


def cond(text):
    return xbmc.getCondVisibility(text)


def info(label):
    return xbmc.getInfoLabel(label)


def related_path():
    """The Seren 'related titles' list of the title whose page is open now (the same path the page itself uses)."""
    kind = info("ListItem.DBType")
    if kind == "movie" and info("ListItem.Property(trakt_id)"):
        return f"{SERENPATH}?action=moviesRelated&action_args={info('ListItem.Property(trakt_id)')}"
    if kind == "tvshow" and info("ListItem.Property(trakt_id)"):
        return f"{SERENPATH}?action=showsRelated&action_args={info('ListItem.Property(trakt_id)')}"
    if kind in ("episode", "season") and info("ListItem.Property(trakt_show_id)"):
        return f"{SERENPATH}?action=showsRelated&action_args={info('ListItem.Property(trakt_show_id)')}"
    return ""


def wait_for_list(monitor):
    """Wait until the video window shows a finished list; True when there are items."""
    start = time.time()
    while time.time() - start < WAIT_LIST:
        if monitor.waitForAbort(0.3):
            return False
        if cond("Window.IsActive(videos)") and not cond("Container.IsUpdating") and \
                not cond("System.HasActiveModalDialog") and int(info("Container.NumItems") or 0) > 0:
            monitor.waitForAbort(0.5)  # let the list settle
            return True
    return False


def pick(position, year):
    """0-based place of the item to open."""
    total = int(info("Container.NumItems") or 0)
    if position is not None:
        return max(0, min(position, total - 1))
    if year:
        for place in range(min(total, 60)):
            if info(f"Container.ListItemAbsolute({place}).Year") == year:
                return place
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "path"
    monitor = xbmc.Monitor()
    position = None
    if mode == "related":
        path = related_path()
        try:
            position = max(int(HOME.getProperty("nuvio.open.pos") or "1") - 1, 0)
        except ValueError:
            position = 0
        year = ""
    else:
        path = HOME.getProperty("nuvio.open.path")
        year = HOME.getProperty("nuvio.open.year")
    if not path:
        log("no path to open")
        return
    xbmc.executebuiltin("Dialog.Close(1180,true)")
    xbmc.executebuiltin("Dialog.Close(movieinformation,true)")
    if monitor.waitForAbort(0.4):
        return
    xbmc.executebuiltin(f'ActivateWindow(Videos,"{path}",return)')
    if not wait_for_list(monitor):
        log("the list did not open")
        return
    place = pick(position, year)
    control = info("System.CurrentControlID")
    log(f"opening item {place} of the list (year {year or '-'})")
    if control:
        xbmc.executebuiltin(f"SetFocus({control},{place},absolute)")
        monitor.waitForAbort(0.4)
    xbmc.executebuiltin("Action(Info)")


main()
