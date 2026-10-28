"""Live TV helpers for the player screens.

live.py,track      remember the channel you watch (recent list) and look up the live score of the game on it
live.py,play,<id>  switch to a channel
"""
import json
import os
import sys
import time

import xbmc
import xbmcgui
import xbmcvfs

HOME = xbmcgui.Window(10000)
MAX = 8
FILE = "special://profile/addon_data/skin.lucent/live_recent.json"
PROPS = ("on", "h", "a", "hs", "as", "clock", "hname", "aname", "hrec", "arec", "hlogo", "alogo", "hcol", "acol")


def rpc(method, params=None):
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))).get("result") or {}
    except Exception:  # noqa: BLE001
        return {}


def load():
    try:
        with xbmcvfs.File(FILE) as fh:
            data = json.loads(fh.read() or "[]")
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def save(rows):
    try:
        folder = os.path.dirname(xbmcvfs.translatePath(FILE))
        if not xbmcvfs.exists(folder + "/"):
            xbmcvfs.mkdirs(folder)
        with xbmcvfs.File(FILE, "w") as fh:
            fh.write(json.dumps(rows))
    except Exception:  # noqa: BLE001
        pass


def current_channel():
    result = rpc("Player.GetActivePlayers")
    for player in (result if isinstance(result, list) else []):
        if player.get("type") != "video":
            continue
        item = rpc("Player.GetItem", {"playerid": player["playerid"], "properties": ["channel"]}).get("item") or {}
        if item.get("type") == "channel" and item.get("id"):
            return {"id": int(item["id"]), "name": xbmc.getInfoLabel("VideoPlayer.ChannelName") or item.get("channel") or item.get("label") or "",
                    "icon": xbmc.getInfoLabel("Player.Icon")}
    return None


def set_recent(rows, now_id):
    shown = [r for r in rows if r["id"] != now_id][:MAX]
    for n in range(1, MAX + 1):
        row = shown[n - 1] if n <= len(shown) else {}
        HOME.setProperty(f"live.r.{n}.id", str(row.get("id", "")))
        HOME.setProperty(f"live.r.{n}.name", row.get("name", ""))
        HOME.setProperty(f"live.r.{n}.icon", row.get("icon", ""))


def clear_score():
    for key in PROPS:
        HOME.clearProperty(f"live.sc.{key}")


def colour(value, default):
    value = (value or "").strip("#")
    return "FF" + value.upper() if len(value) == 6 else default


def show(ev):
    home, away = ev["home"], ev["away"]
    HOME.setProperty("live.sc.on", "1")
    HOME.setProperty("live.sc.h", (home.get("abbr") or home.get("short") or home["name"])[:3].upper())
    HOME.setProperty("live.sc.a", (away.get("abbr") or away.get("short") or away["name"])[:3].upper())
    HOME.setProperty("live.sc.hs", home.get("score", ""))
    HOME.setProperty("live.sc.as", away.get("score", ""))
    HOME.setProperty("live.sc.clock", ev.get("status", ""))
    HOME.setProperty("live.sc.hname", home.get("short") or home["name"])
    HOME.setProperty("live.sc.aname", away.get("short") or away["name"])
    HOME.setProperty("live.sc.hrec", home.get("rec", ""))
    HOME.setProperty("live.sc.arec", away.get("rec", ""))
    HOME.setProperty("live.sc.hlogo", home.get("logo", ""))
    HOME.setProperty("live.sc.alogo", away.get("logo", ""))
    HOME.setProperty("live.sc.hcol", colour(home.get("color"), "FFB3262E"))
    HOME.setProperty("live.sc.acol", colour(away.get("color"), "FF1F4E9E"))


def score(cid):
    import sport_core as sc
    import sport_epg as epg
    data = epg.load()
    if not data or not data.get("rows"):
        return False
    for ev in sc.all_cached():
        if ev.get("kind") != "teams" or ev.get("state") != "in":
            continue
        if not any(str(c["cid"]) == str(cid) for c in epg.channels_for(ev, data)):
            continue
        show(ev)                               # at once, from what we already hold
        try:                                   # then fresh numbers for this league, shown when they arrive
            sc.refresh(keys=[ev["league"]])
            fresh = next((e for e in sc.all_cached() if e["id"] == ev["id"]), None)
            if fresh and HOME.getProperty("live.sc.on"):
                show(fresh)
        except Exception:  # noqa: BLE001
            pass
        return True
    return False


def track():
    here = current_channel()
    rows = load()
    if here:
        rows = [{"id": here["id"], "name": here["name"], "icon": here["icon"]}] + [r for r in rows if r["id"] != here["id"]]
        save(rows[:MAX + 2])
        set_recent(rows, here["id"])
    else:
        set_recent(rows, None)
    clear_score()
    if here:
        try:
            score(here["id"])
        except Exception as error:  # noqa: BLE001
            xbmc.log(f"[lucent.live] score: {error}", xbmc.LOGWARNING)


def play(cid):
    rpc("Player.Open", {"item": {"channelid": int(cid)}})


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "play" and len(sys.argv) > 2 and sys.argv[2].isdigit():
        play(sys.argv[2])
    else:
        track()
