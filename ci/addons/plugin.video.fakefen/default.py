"""CI stand-in for Fen Light / Red Light: logs every call, lists one episode."""
import sys
import urllib.parse

import xbmcgui
import xbmcplugin

with open("/tmp/ci/fakefen.log", "a") as fh:
    fh.write(sys.argv[2] + "\n")
params = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip("?")))
handle = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip("-").isdigit() else -1
if handle >= 0:
    if params.get("mode") == "list":
        li = xbmcgui.ListItem("The Episode")
        tag = li.getVideoInfoTag()
        tag.setMediaType("episode"), tag.setTitle("The Episode"), tag.setTvShowTitle("Fake Show")
        tag.setSeason(2), tag.setEpisode(3), tag.setUniqueIDs({"tmdb": "1399", "tvdb": "121361"})
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.fakefen/?mode=playback&tmdb_id=1399&season=2&episode=3", li, False)
        xbmcplugin.setContent(handle, "episodes")
    else:
        li = xbmcgui.ListItem("Season 2" if params.get("mode") == "build_season_list" else "Episode 1")
        xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.fakefen/?mode=x", li, True)
    xbmcplugin.endOfDirectory(handle)
