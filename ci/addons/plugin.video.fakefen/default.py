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
    elif params.get("mode") == "showcase":               # films with posters, backgrounds and plots, for the view screenshots
        films = [("Northern Lights", 2024, 7.8, "Drama / Mystery"), ("Iron Harbor", 2023, 6.9, "Action / Thriller"),
                 ("The Quiet Field", 2022, 8.1, "Drama"), ("Neon Avenue", 2025, 7.2, "Crime / Thriller"),
                 ("Paper Moons", 2021, 6.5, "Comedy / Romance"), ("Deep Blue Line", 2024, 7.4, "Adventure"),
                 ("Glass Garden", 2023, 7.9, "Fantasy / Drama"), ("Red Canyon", 2020, 6.8, "Western"),
                 ("Silent Orbit", 2025, 8.3, "Science fiction"), ("Last Train Home", 2022, 7.1, "Family / Drama"),
                 ("Copper Sky", 2021, 6.6, "Action"), ("Winter Tale", 2024, 7.6, "Animation / Family")]
        for n, (name, year, rating, genre) in enumerate(films):
            li = xbmcgui.ListItem(name)
            tag = li.getVideoInfoTag()
            tag.setMediaType("movie"), tag.setTitle(name), tag.setYear(year), tag.setRating(rating), tag.setGenres(genre.split(" / "))
            tag.setPlot("A CI test film. %s is about people who find out more than they wanted to know, told across one long night "
                        "in a city that never sleeps. Made up for the screenshots." % name)
            tag.setDuration(6000 + n * 300), tag.setUniqueIDs({"tmdb": str(1000 + n)})
            li.setArt({"poster": "/tmp/ci/art/poster%d.jpg" % n, "fanart": "/tmp/ci/art/fanart%d.jpg" % n,
                       "landscape": "/tmp/ci/art/fanart%d.jpg" % n, "thumb": "/tmp/ci/art/poster%d.jpg" % n})
            li.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.fakefen/?mode=playback&t=" + urllib.parse.quote(name), li, False)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
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
