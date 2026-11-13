"""CI stand-in for Seren: lists that are fast, slow, very slow, empty the first two times, or always empty."""
import json
import os
import sys
import time
import urllib.parse

import xbmcgui
import xbmcplugin

handle = int(sys.argv[1])
q = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
kind = q.get("list", "fast")
STATE = "/tmp/ci/fake_calls.json"
try:
    calls = json.load(open(STATE))
except Exception:
    calls = {}
calls[kind] = calls.get(kind, 0) + 1
os.makedirs("/tmp/ci", exist_ok=True)
json.dump(calls, open(STATE, "w"))
n = 60 if kind == "many" else 25
if kind.startswith("slow"):
    time.sleep(12)
elif kind.startswith("slower"):
    time.sleep(30)
elif kind == "flaky" and calls[kind] <= 2:
    n = 0
elif kind == "empty":
    n = 0
icon = "special://home/addons/plugin.video.fakeseren/icon.png"
ART = "special://home/addons/plugin.video.fakeseren/art/"
SHOW = ["Glasswork", "Red Harbour", "Lumen", "Night Ferry", "Northbound", "Copper Sky", "The Quiet Year", "Saltwater",
        "Hollow Pines", "Afterglow", "Paper Tigers", "Low Tide"]
GENRES = ["Drama", "Mystery", "Documentary", "Thriller", "Science fiction", "Comedy"]
PLOT = ("A fictional placeholder synopsis used for this screenshot. The real text comes from Trakt and TMDB through "
        "Seren, and wraps onto up to three lines here.")
if kind == "svc":
    # streaming services like the video add-on sends them: a square coloured logo as art, the skin's own logo as svclogo
    items = []
    for i, (name, key) in enumerate((("Netflix", "netflix"), ("Hulu", "hulu"), ("Starz", "starz"), ("MGM+", "mgm"),
                                     ("Peacock", "peacock"), ("AMC+", "amc"))):
        li = xbmcgui.ListItem(name, offscreen=True)
        sq = f"{ART}svc{i}.png"
        li.setArt({"poster": sq, "thumb": sq, "icon": sq, "landscape": sq, "fanart": ""})
        li.setProperty("svclogo", f"special://skin/media/services/{key}.png")
        li.setProperty("lucent_open", "1")
        li.setProperty("IsPlayable", "false")
        items.append((f"plugin://plugin.video.fakeseren/?list=fast&svc={i}", li, False))
    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
elif kind in ("sm", "ss", "se"):
    items = []
    for i, title in enumerate(SHOW):
        li = xbmcgui.ListItem(title, offscreen=True)
        tag = li.getVideoInfoTag()
        tag.setTitle(title)
        tag.setYear(2016 + i % 9)
        tag.setRating(round(6.4 + (i * 7 % 30) / 10, 1))
        tag.setGenres([GENRES[i % 6], GENRES[(i + 2) % 6]])
        tag.setPlot(PLOT)
        tag.setMpaa("12")
        tag.setDuration((95 + i * 7 % 50) * 60)
        tag.setTrailer(f"plugin://plugin.video.youtube/play/?video_id=ci{kind}{i}")
        if kind == "se":
            tag.setMediaType("episode")
            tag.setTvShowTitle(title)
            tag.setSeason(2)
            tag.setEpisode(7 + i)
            tag.setTitle(f"Chapter {5 + i}")
            li.setLabel(f"Chapter {5 + i}")
            if i % 2 == 0:
                tag.setResumePoint(600 + i * 300, 3000)
            li.setArt({"thumb": f"{ART}f{i}.jpg", "fanart": f"{ART}f{i}.jpg", "poster": f"{ART}p{i}.jpg", "landscape": f"{ART}f{i}.jpg"})
        else:
            tag.setMediaType("movie" if kind == "sm" else "tvshow")
            li.setArt({"poster": f"{ART}p{i}.jpg", "thumb": f"{ART}p{i}.jpg", "fanart": f"{ART}f{(i + 3) % 12}.jpg", "landscape": f"{ART}f{(i + 3) % 12}.jpg"})
        li.setProperty("IsPlayable", "true")
        items.append((f"plugin://plugin.video.fakeseren/?play={kind}{i}", li, False))
    xbmcplugin.setContent(handle, {"sm": "movies", "ss": "tvshows", "se": "episodes"}[kind])
    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
else:
    items = []
    NAMES = ["Mango", "Zebra", "Apple", "Kiwi", "Delta", "Banana", "Yankee", "Echo", "Lima", "Charlie", "Oscar", "Hotel",
             "Golf", "Nectar", "Fig", "Juliet", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "Xray"]
    for i in range(n):
        title = NAMES[i] if kind in ("names", "labels") else f"{kind} {i + 1}"
        if kind == "labels":            # an add-on folder that only gives names (no title, year ...), like many add-ons do
            li = xbmcgui.ListItem(title, offscreen=True)
            li.setArt({"poster": icon, "thumb": icon})
            items.append((f"plugin://plugin.video.fakeseren/?list=fast&from={i}", li, True))
            continue
        li = xbmcgui.ListItem(title, offscreen=True)
        tag = li.getVideoInfoTag()
        tag.setMediaType("movie")
        tag.setTitle(title)
        tag.setYear(2000 + (i * 7) % 25)
        tag.setRating(round(1 + (i * 3) % 9 + 0.5, 1))
        tag.setDateAdded(f"2026-01-{(i * 11) % 28 + 1:02d} 12:00:00")
        li.setArt({"poster": icon, "thumb": icon, "fanart": icon})
        if kind == "fast3" and i < 6:              # 2.1.2 test: streaming service tiles, like the video add-on sends them
            keys = ("netflix", "hulu", "starz", "mgm", "peacock", "amc")
            sq = f"{ART}svc{i}.png"
            li.setArt({"poster": sq, "thumb": sq, "icon": sq, "landscape": sq})
            li.setProperty("svclogo", f"special://skin/media/services/{keys[i]}.png")
        li.setProperty("IsPlayable", "true")
        if kind == "folder":
            items.append((f"plugin://plugin.video.fakeseren/?list=fast&from={i}", li, True))
        else:
            items.append((f"plugin://plugin.video.fakeseren/?play={kind}{i}", li, False))
    xbmcplugin.setContent(handle, "movies")
    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
