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
    elif params.get("mode") == "showcase_tv":            # series with status and how much was watched (views 74, 75, 78)
        shows = [("Harbor Lights", "Returning Series", 10, 4), ("The Long Road", "Ended", 24, 24), ("Signal Lost", "Canceled", 8, 2),
                 ("Copper Town", "In Production", 0, 0), ("Night Shift", "Returning Series", 16, 15), ("Echo Valley", "Ended", 30, 9),
                 ("Blue Hour", "Returning Series", 12, 0), ("Paper Crowns", "Ended", 20, 20)]
        for n, (name, status, total, seen) in enumerate(shows):
            li = xbmcgui.ListItem(name)
            tag = li.getVideoInfoTag()
            tag.setMediaType("tvshow"), tag.setTitle(name), tag.setTvShowTitle(name), tag.setYear(2018 + n), tag.setRating(6.5 + n / 5)
            tag.setTvShowStatus(status), tag.setGenres(["Drama", "Mystery"]), tag.setUniqueIDs({"tmdb": str(2000 + n)})
            tag.setPlot("A CI test series. %s follows a small town where every season opens a new door. Made up for the screenshots." % name)
            li.setProperty("TotalEpisodes", str(total)), li.setProperty("WatchedEpisodes", str(seen))
            li.setProperty("UnWatchedEpisodes", str(total - seen))
            if total:
                li.setProperty("WatchedProgress", str(int(round(100 * seen / total))))
            li.setArt({"poster": "/tmp/ci/art/poster%d.jpg" % n, "fanart": "/tmp/ci/art/fanart%d.jpg" % n,
                       "landscape": "/tmp/ci/art/fanart%d.jpg" % n, "thumb": "/tmp/ci/art/poster%d.jpg" % n})
            xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.fakefen/?mode=x", li, True)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
        xbmcplugin.setContent(handle, "tvshows")
    elif params.get("mode") == "showcase_ep":            # episodes with stills, stream flags, watched and resume (views 76, 77, 79, 80)
        import xbmc
        for n in range(1, 9):
            name = ["The Arrival", "Low Tide", "Old Friends", "The Map", "Static", "Crossing", "Small Hours", "Homecoming"][n - 1]
            li = xbmcgui.ListItem(name)
            tag = li.getVideoInfoTag()
            tag.setMediaType("episode"), tag.setTitle(name), tag.setTvShowTitle("Harbor Lights"), tag.setSeason(2), tag.setEpisode(n)
            tag.setPlot("Episode %d of a CI test series. Someone comes back to town and nothing stays the way it was. Made up for the screenshots." % n)
            tag.setDuration(2700 + n * 60), tag.setPremiered("2026-10-%02d" % (n + 1)), tag.setDateAdded("2026-11-%02d 21:00:00" % (n + 1))
            if n <= 3:
                tag.setPlaycount(1)
            if n == 4:
                tag.setResumePoint(1200.0, 2940.0)
            tag.addVideoStream(xbmc.VideoStreamDetail(width=3840 if n % 2 else 1920, height=2160 if n % 2 else 1080, codec="hevc",
                                                      hdrType="dolbyvision" if n % 3 == 0 else "hdr10"))
            tag.addAudioStream(xbmc.AudioStreamDetail(channels=6 if n % 2 else 2, codec="eac3", language="en"))
            tag.addSubtitleStream(xbmc.SubtitleStreamDetail(language="nl"))
            k = n % 8
            li.setArt({"thumb": "/tmp/ci/art/fanart%d.jpg" % k, "fanart": "/tmp/ci/art/fanart0.jpg", "tvshow.poster": "/tmp/ci/art/poster0.jpg"})
            li.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(handle, "plugin://plugin.video.fakefen/?mode=playback&t=" + urllib.parse.quote(name), li, False)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
        xbmcplugin.setContent(handle, "episodes")
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
