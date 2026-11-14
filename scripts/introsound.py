# -*- coding: utf-8 -*-
"""Lucent: starts the intro at start - the picture and the sound together - and goes on to the start window after it.

    RunScript(special://skin/scripts/introsound.py)      from Startup.xml, only when the intro is on

2.1.5: on a real box Kodi opens Startup.xml while it is still busy starting (issue #14, CoreELEC): animations that start
when the window opens run unseen. Python only runs once Kodi is free, so this script gives the go signal
(Window(home).Property(lucent.intro.go)); the animations in Startup.xml start on it. The sound plays as a menu sound
(xbmc.playSFX): with Kodi's menu sounds set to 'never', you hear nothing. Skin settings can switch the sound off.
"""
import xbmc
import xbmcvfs

LENGTH = 6.0            # seconds: the animations end with a fade to black at 5.2 - 6.0 s

monitor = xbmc.Monitor()
xbmc.executebuiltin("SetProperty(lucent.intro.go,1,home)")
if not xbmc.getCondVisibility("Skin.HasSetting(lucent.introsound.off)"):
    xbmc.playSFX(xbmcvfs.translatePath("special://skin/media/sounds/intro.wav"), False)
if not monitor.waitForAbort(LENGTH) and xbmc.getCondVisibility("Window.IsActive(startup)"):
    xbmc.executebuiltin("CancelAlarm(lucentintrosafe,true)")
    xbmc.executebuiltin("ReplaceWindow(%s)" % (xbmc.getInfoLabel("System.StartupWindow") or "home"))
xbmc.executebuiltin("ClearProperty(lucent.intro.go,home)")
