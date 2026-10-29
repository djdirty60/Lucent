# -*- coding: utf-8 -*-
"""Lucent: OK on a film or episode in a Kodi list (a Seren folder, the video lists).

Started by the OK key from a small keymap (see keymap.py) only when you chose in Skin settings that a film or an
episode first opens its page. Everything else gets the normal OK back.
"""
import xbmc


def main():
    dbtype = xbmc.getInfoLabel("ListItem.DBType")
    page = ((dbtype == "movie" and xbmc.getCondVisibility("Skin.HasSetting(nuvio.ok.movie.page)"))
            or (dbtype == "episode" and xbmc.getCondVisibility("Skin.HasSetting(nuvio.ok.episode.page)")))
    xbmc.executebuiltin("Action(Info)" if page else "Action(Select)")


main()
