"""CI stand-in for luc_kodi (built on Umbrella): logs every call, lists one episode or one film."""
import sys
import urllib.parse

import xbmcgui
import xbmcplugin

with open("/tmp/ci/luckodi.log", "a") as fh:
    fh.write(sys.argv[2] + "\n")
params = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip("?")))
handle = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip("-").isdigit() else -1
if handle >= 0:
    action = params.get("action")
    if action == "list":
        li = xbmcgui.ListItem("Luc Episode")
        tag = li.getVideoInfoTag()
        tag.setMediaType("episode"), tag.setTitle("Luc Episode"), tag.setTvShowTitle("Luc Show"), tag.setYear(2011)
        tag.setSeason(2), tag.setEpisode(3), tag.setUniqueIDs({"imdb": "tt0944947", "tmdb": "1399", "tvdb": "121361"})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.luc_kodi/?action=play_Item&tmdb=1399&season=2&episode=3", li, False)
        xbmcplugin.setContent(handle, "episodes")
    elif action == "homewidget":
        li = xbmcgui.ListItem("Luc Film")
        tag = li.getVideoInfoTag()
        tag.setMediaType("movie"), tag.setTitle("Luc Film"), tag.setUniqueIDs({"imdb": "tt1375666", "tmdb": "27205"})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.luc_kodi/?action=play_Item&tmdb=27205", li, False)
        xbmcplugin.setContent(handle, "movies")
    else:
        li = xbmcgui.ListItem("Season 2" if action == "seasons" else "Episode 1")
        xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.luc_kodi/?action=x", li, True)
    xbmcplugin.endOfDirectory(handle)
