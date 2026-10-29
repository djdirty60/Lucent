# -*- coding: utf-8 -*-
"""Lucent: star button in the live TV menu - add the channel you watch to Kodi's favourites, or take it out again.

    RunScript(special://skin/scripts/livefav.py)

The favourite starts the channel through Lucent (live.py,play,<channel id>), so it also works from Kodi's Favourites
list and from the Favourites tab in the Lucent menu. Kodi has no switch for the channel groups, so the favourites
list is used. Choosing the star again removes it.
"""
import xbmc
import xbmcgui

import live

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"


def t(en, nl):
    return nl if NL else en


def target(cid):
    return f"special://skin/scripts/live.py,play,{cid}"


def is_favourite(cid):
    result = live.rpc("Favourites.GetFavourites", {"type": "script", "properties": ["path"]})
    return any(f"live.py,play,{cid}" in (f.get("path") or "") for f in (result.get("favourites") or []))


def toggle():
    here = live.current_channel()
    if not here:
        xbmcgui.Dialog().notification("Lucent", t("Watch a TV channel first", "Kijk eerst een tv-zender"), xbmcgui.NOTIFICATION_INFO, 3000, False)
        return
    was = is_favourite(here["id"])
    live.rpc("Favourites.AddFavourite", {"title": here["name"] or t("TV channel", "Tv-zender"), "type": "script", "path": target(here["id"]),
                                         "thumbnail": here.get("icon") or ""})
    now = is_favourite(here["id"])
    if now == was:
        text = t("Could not change the favourite", "Favoriet wijzigen is niet gelukt")
    else:
        text = (t("Added to favourites: ", "Toegevoegd aan favorieten: ") if now else t("Removed from favourites: ", "Uit favorieten gehaald: ")) + here["name"]
    xbmcgui.Dialog().notification("Lucent", text, "special://skin/media/icons/star.png", 3000, False)


if __name__ == "__main__":
    toggle()
