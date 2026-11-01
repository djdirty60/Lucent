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
items = []
NAMES = ["Mango", "Zebra", "Apple", "Kiwi", "Delta", "Banana", "Yankee", "Echo", "Lima", "Charlie", "Oscar", "Hotel",
         "Golf", "Nectar", "Fig", "Juliet", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "Xray"]
for i in range(n):
    title = NAMES[i] if kind == "names" else f"{kind} {i + 1}"
    li = xbmcgui.ListItem(title, offscreen=True)
    tag = li.getVideoInfoTag()
    tag.setMediaType("movie")
    tag.setTitle(title)
    tag.setYear(2000 + (i * 7) % 25)
    tag.setRating(round(1 + (i * 3) % 9 + 0.5, 1))
    tag.setDateAdded(f"2026-01-{(i * 11) % 28 + 1:02d} 12:00:00")
    li.setArt({"poster": icon, "thumb": icon, "fanart": icon})
    li.setProperty("IsPlayable", "true")
    if kind == "folder":
        items.append((f"plugin://plugin.video.fakeseren/?list=fast&from={i}", li, True))
    else:
        items.append((f"plugin://plugin.video.fakeseren/?play={kind}{i}", li, False))
xbmcplugin.setContent(handle, "movies")
xbmcplugin.addDirectoryItems(handle, items, len(items))
xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
