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
    if params.get("mode") == "letters":                  # many films, for the alphabet bar (letters.py)
        names = ["%s%s film %d" % (ch, "ab"[n % 2], n) for ch in "ABCDEFGHKLMNPRSTVW" for n in range(3)] + ["The Batman", "1917"]
        for name in names:
            li = xbmcgui.ListItem(name)
            tag = li.getVideoInfoTag()
            tag.setMediaType("movie"), tag.setTitle(name)
            li.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.fakefen/?mode=playback&t=" + urllib.parse.quote(name), li, False)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.setContent(handle, "movies")
    elif params.get("mode") == "progress":               # like Fen Light: a resume point without total time + WatchedProgress
        li = xbmcgui.ListItem("Half Film")
        tag = li.getVideoInfoTag()
        tag.setMediaType("movie"), tag.setTitle("Half Film"), tag.setUniqueIDs({"tmdb": "2667"}), tag.setResumePoint(45.0)
        li.setProperty("WatchedProgress", "45")
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.fakefen/?mode=playback&tmdb_id=2667", li, False)
        xbmcplugin.setContent(handle, "movies")
    elif params.get("mode") == "list":
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
