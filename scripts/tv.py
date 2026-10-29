# -*- coding: utf-8 -*-
"""Lucent: the TV tab opens Kodi's own TV guide (the old channel-list screen was removed in 1.30.115)."""
import xbmc

xbmc.executebuiltin("ActivateWindow(TVGuide)")
