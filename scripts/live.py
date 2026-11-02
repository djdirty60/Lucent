"""Live TV helpers for the player screens.

live.py,track      remember the channel you watch (recent list) and look up the live score of the game on it
live.py,play,<id>  switch to a channel
live.py,record,<broadcast id>   record a programme of the mini guide (the one on now: Kodi's own Record)
live.py,remind,<broadcast id>   a reminder: when it starts, Lucent asks whether to switch to it
"""
import datetime
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


def colour(side, default):
    import sport_core as sc
    value = sc.club_hex(side.get("color"), side.get("alt"))
    return "FF" + value.upper() if value else default


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
    HOME.setProperty("live.sc.hcol", colour(home, "FFB3262E"))
    HOME.setProperty("live.sc.acol", colour(away, "FF1F4E9E"))


def score(cid):
    import sport_core as sc
    live = [ev for ev in sc.all_cached() if ev.get("kind") == "teams" and ev.get("state") == "in"]
    if not live:
        return False                           # no game is live: do not load the whole TV guide while a video plays
    import sport_epg as epg
    data = epg.load()
    if not data or not data.get("rows"):
        return False
    for ev in live:
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
    try:
        guide(here)
    except Exception as error:  # noqa: BLE001
        xbmc.log(f"[lucent.live] guide: {error}", xbmc.LOGWARNING)
    clear_score()
    if here:
        try:
            score(here["id"])
        except Exception as error:  # noqa: BLE001
            xbmc.log(f"[lucent.live] score: {error}", xbmc.LOGWARNING)


def play(cid):
    rpc("Player.Open", {"item": {"channelid": int(cid)}})


# ----------------------------------------------------------------------------- the mini guide in the TV player
GN = 6
REMIND_FILE = "special://profile/addon_data/skin.lucent/live_reminders.json"
_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"


def tr(en, nl):
    return nl if _NL else en


def utc_stamp(text):
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0


def hhmm(stamp):
    return datetime.datetime.fromtimestamp(stamp).strftime("%H:%M")


def guide(here):
    """live.g.N.*: the programmes of this channel from now on; live.g.up / .down: the channels above and below."""
    rows = []
    if here:
        data = rpc("PVR.GetBroadcasts", {"channelid": here["id"], "properties": ["title", "starttime", "endtime", "plot", "genre"]})
        now = time.time()
        for b in data.get("broadcasts") or []:
            start, end = utc_stamp(b.get("starttime")), utc_stamp(b.get("endtime"))
            if end <= now:
                continue
            on = start <= now < end
            rows.append({"bid": str(b.get("broadcastid", "")), "title": b.get("title") or b.get("label") or "",
                         "start": hhmm(start), "end": hhmm(end), "now": "1" if on else "",
                         "prog": str(int((now - start) * 100 / max(1, end - start))) if on else "0",
                         "cid": str(here["id"]), "stamp": str(int(start))})
            if len(rows) >= GN:
                break
    for n in range(1, GN + 1):
        row = rows[n - 1] if n <= len(rows) else {}
        for key in ("bid", "title", "start", "end", "now", "prog", "cid", "stamp"):
            HOME.setProperty(f"live.g.{n}.{key}", row.get(key, ""))
    up = down = ""
    if here:
        chans = (rpc("PVR.GetChannels", {"channelgroupid": "alltv", "properties": ["channelnumber"]}) or {}).get("channels") or []
        ids = [c.get("channelid") for c in chans]
        if here["id"] in ids and len(chans) > 1:
            i = ids.index(here["id"])
            up = chans[(i - 1) % len(chans)].get("label", "")
            down = chans[(i + 1) % len(chans)].get("label", "")
    HOME.setProperty("live.g.up", up)
    HOME.setProperty("live.g.down", down)
    # the player menu opened before the guide was filled: the programme on now gets the focus
    if rows and xbmc.getCondVisibility("Window.IsActive(videoosd) + !Control.HasFocus(460) + !ControlGroup(470).HasFocus + !ControlGroup(400).HasFocus"):
        xbmc.executebuiltin("SetFocus(460,0)")


def record(bid):
    if not str(bid).isdigit():
        xbmc.executebuiltin("Action(Record)")
        return
    reply = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "PVR.AddTimer", "params": {"broadcastid": int(bid)}})))
    ok = "error" not in reply
    xbmcgui.Dialog().notification("Lucent", tr("Will be recorded", "Wordt opgenomen") if ok else tr("Recording not possible", "Opnemen lukt niet"),
                                  xbmcgui.NOTIFICATION_INFO if ok else xbmcgui.NOTIFICATION_WARNING, 3000)


def load_reminders():
    try:
        with xbmcvfs.File(REMIND_FILE) as fh:
            data = json.loads(fh.read() or "[]")
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def save_reminders(rows):
    try:
        with xbmcvfs.File(REMIND_FILE, "w") as fh:
            fh.write(json.dumps(rows))
    except Exception:  # noqa: BLE001
        pass


def remind(n):
    """Remember programme N of the mini guide; Lucent asks to switch when it starts."""
    p = f"live.g.{n}."
    title, cid, stamp = HOME.getProperty(p + "title"), HOME.getProperty(p + "cid"), HOME.getProperty(p + "stamp")
    if not title or not stamp.isdigit():
        return
    if HOME.getProperty(p + "now"):
        xbmcgui.Dialog().notification("Lucent", tr("This is on now", "Dit is nu al bezig"), xbmcgui.NOTIFICATION_INFO, 2500)
        return
    rows = [r for r in load_reminders() if r.get("stamp", 0) > time.time() - 600 and not (r.get("cid") == cid and r.get("stamp") == int(stamp))]
    rows.append({"cid": cid, "stamp": int(stamp), "title": title, "channel": xbmc.getInfoLabel("VideoPlayer.ChannelName")})
    save_reminders(rows)
    xbmcgui.Dialog().notification("Lucent", tr("Reminder at {0}: {1}", "Herinnering om {0}: {1}").format(hhmm(int(stamp)), title),
                                  xbmcgui.NOTIFICATION_INFO, 3000)


def check_reminders():
    """Helper, every few seconds: a reminded programme starts - ask to switch (once)."""
    rows = load_reminders()
    if not rows:
        return
    now, keep, due = time.time(), [], []
    for r in rows:
        if r.get("stamp", 0) - 30 <= now:
            if now - r.get("stamp", 0) < 15 * 60:
                due.append(r)
        else:
            keep.append(r)
    if not due:
        return
    save_reminders(keep)
    import threading
    threading.Thread(target=_ask, args=(due,), daemon=True).start()     # the helper must not wait for the answer


def _ask(due):
    for r in due:
        if xbmcgui.Dialog().yesno("Lucent", tr("{0} starts now on {1}. Switch to it?", "{0} begint nu op {1}. Overschakelen?").format(r["title"], r.get("channel") or ""),
                                  nolabel=tr("No", "Nee"), yeslabel=tr("Switch", "Overschakelen"), autoclose=60000):
            play(r["cid"])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "play" and len(sys.argv) > 2 and sys.argv[2].isdigit():
        play(sys.argv[2])
    elif len(sys.argv) > 2 and sys.argv[1] == "record":
        record(sys.argv[2])
    elif len(sys.argv) > 2 and sys.argv[1] == "remind":
        remind(sys.argv[2])
    else:
        track()
