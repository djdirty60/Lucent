# -*- coding: utf-8 -*-
"""Lucent: the sound of the intro at start (a warm swell, one deep bell when the name appears, a sparkle at the twinkle).

    RunScript(special://skin/scripts/introsound.py)      from Startup.xml, only when the intro is on

It plays as a menu sound (xbmc.playSFX), not through the video/music player, so nothing shows on screen. When Kodi's
menu sounds are set to 'never', you hear nothing. The file starts a quarter of a second in, because starting Python
takes about that long.
"""
import xbmc
import xbmcvfs

if not xbmc.getCondVisibility("Skin.HasSetting(lucent.introsound.off)"):
    xbmc.playSFX(xbmcvfs.translatePath("special://skin/media/sounds/intro.wav"), False)
