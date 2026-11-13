"""CI stand-in for YouTube: like the real add-on it needs a few seconds before the trailer starts."""
import sys
import time

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

time.sleep(3)
path = xbmcvfs.translatePath("special://home/addons/plugin.video.lucent/resources/formattest/hevc4k.mp4")
xbmc.log(f"[ci-youtube] resolve {sys.argv[2]}", xbmc.LOGINFO)
xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, xbmcgui.ListItem(path=path))
