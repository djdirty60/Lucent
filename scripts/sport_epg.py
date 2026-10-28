# -*- coding: utf-8 -*-
"""Lucent: Sport tab - reads the IPTV guide (Kodi PVR, e.g. IPTV Simple Client) and finds where a game is on.

scan()              reads the guide of all TV channels (in the background), stores it in sport_epg.json (3 hours)
channels_for(ev)    the channels that show a game: [{cid, name, tag, q, score, title, start, live}]
Matching uses the programme title and description:
  3  both teams are named                 -> "Zeker"
  2  one team + the competition           -> "Zeker"
  1  only the competition, and the programme starts around the kick-off -> "Misschien"
"""
import json
import re
import time

import xbmc

import agenda_core as ac
import sport_core as sc

EPG_PATH = ac.DATA + "sport_epg.json"
EPG_TTL = 3 * 3600
LEAD = 45 * 60          # a programme may start this long before kick-off (pre-show)
LATE = 25 * 60          # ... or this long after it
MAX_CHANNELS = 4
RECAP = ("samenvatting", "highlights", "terugkijken", "herhaling", "repeat", "replay", "review", "studio", "nabeschouwing",
         "magazine", "analyse", "preview", "voorbeschouwing")
_QUALITY = (("4k", "4K"), ("uhd", "4K"), ("fhd", "FHD"), ("1080", "FHD"), ("hd", "HD"), ("sd", ""))


def rpc(method, params=None):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result") or {}
    except Exception as error:  # noqa: BLE001
        sc.log(f"rpc {method}: {error}")
        return {}


def quality_of(name):
    low = " " + re.sub(r"[^a-z0-9]+", " ", name.lower()) + " "
    for word, label in _QUALITY:
        if f" {word} " in low or (word in ("4k", "uhd") and word in low.replace(" ", "")):
            return label
    return ""


def country_of(name):
    """'|NL| Ziggo Sport 1 HD' -> 'NL'."""
    match = re.match(r"\s*[|\[(]?\s*([A-Za-z]{2,3})\s*[|\])\-:]", name or "")
    return match.group(1).upper() if match else ""


def clean_name(name):
    name = re.sub(r"^\s*[|\[(]\s*[A-Za-z]{2,3}\s*[|\])]\s*[-: ]*", "", name or "")
    name = re.sub(r"\s+", " ", name).strip()
    return re.sub(r"(\s+(HD|FHD|UHD|SD|4K|1080p?|H265|HEVC))+$", "", name, flags=re.I).strip()


def channels():
    """All TV channels. 'alltv' first; when Kodi does not know it, the first TV channel group."""
    data = rpc("PVR.GetChannels", {"channelgroupid": "alltv", "properties": ["channel", "thumbnail"]})
    found = data.get("channels") or []
    if found:
        return found
    groups = rpc("PVR.GetChannelGroups", {"channeltype": "tv"}).get("channelgroups") or []
    for group in groups:
        data = rpc("PVR.GetChannels", {"channelgroupid": group.get("channelgroupid"), "properties": ["channel", "thumbnail"]})
        found = data.get("channels") or []
        if found:
            return found
    return []


def diagnose():
    """Why is there no guide? A short Dutch/English reason for the screen."""
    props = rpc("PVR.GetProperties", {"properties": ["available"]})
    if not props.get("available"):
        return sc.t("pvr_off")
    if not channels():
        return sc.t("pvr_nochan")
    return sc.t("pvr_noepg")


def broadcasts(channel_id):
    # PVR.GetBroadcasts has no time filter: it returns what the guide holds, which is what we want
    data = rpc("PVR.GetBroadcasts", {"channelid": channel_id,
                                     "properties": ["title", "plotoutline", "plot", "starttime", "endtime", "episodename"]})
    return data.get("broadcasts") or []


def stamp(value):
    """Kodi gives UTC like '2026-10-30 17:30:00'."""
    import calendar
    import datetime
    try:
        return calendar.timegm(datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timetuple())
    except (TypeError, ValueError):
        return 0


_MEM = {"data": None, "fetched": -1, "starts": []}


def load():
    """The stored guide, rows sorted by start time (kept in memory)."""
    if _MEM["data"] is None:
        data = ac.read_json(EPG_PATH, {})
        data["rows"] = sorted(data.get("rows", []), key=lambda r: r[1])
        _MEM.update(data=data, starts=[r[1] for r in data["rows"]])
    return _MEM["data"]


def forget():
    _MEM["data"] = None


def is_fresh():
    """Read within 3 hours; an empty guide (IPTV Simple was still loading it) is tried again after 5 minutes."""
    data = load()
    age = time.time() - data.get("fetched", 0)
    return age < (EPG_TTL if data.get("rows") else 300)


def scan(progress=None, abort=None):
    """Read the guide of every TV channel. progress(done, total); abort() -> True stops. Returns the number of programmes."""
    now = int(time.time())
    horizon = now + (sc.DAYS_AHEAD + 1) * 86400
    chans = channels()
    rows, total = [], len(chans)
    for index, chan in enumerate(chans, 1):
        if abort and abort():
            return -1
        for item in broadcasts(chan["channelid"]):
            start, end = stamp(item.get("starttime")), stamp(item.get("endtime"))
            if end < now - 4 * 3600 or start > horizon:
                continue
            rows.append([chan["channelid"], start, end, item.get("title") or "",
                         " ".join(x for x in (item.get("plotoutline"), item.get("episodename"), (item.get("plot") or "")[:300]) if x)])
        if progress and (index % 5 == 0 or index == total):
            progress(index, total)
    names = {c["channelid"]: c.get("label") or c.get("channel") or "" for c in chans}
    icons = {c["channelid"]: c.get("thumbnail") or "" for c in chans}
    forget()
    ac.write_json(EPG_PATH, {"fetched": now, "rows": rows, "names": {str(k): v for k, v in names.items()},
                             "icons": {str(k): v for k, v in icons.items()}})
    sc.log(f"guide read: {total} channels, {len(rows)} programmes")
    return len(rows)


# ----------------------------------------------------------------------------- matching
def score_event(ev, text, title_norm):
    """How sure are we that the programme (title + description, normalised) is this game? 0..3"""
    words = sc.league_terms(ev["league"])
    league_hit = any(sc.has_phrase(text, w) for w in words)
    if ev["kind"] == "teams":
        home = any(sc.has_phrase(text, t) for t in sc.team_terms(ev["home"]))
        away = any(sc.has_phrase(text, t) for t in sc.team_terms(ev["away"]))
        if home and away:
            return 3
        if (home or away) and league_hit:
            return 2
        if league_hit and title_norm:
            return 1
        return 0
    # races / tournaments / fight cards: a competition word, and for Formula 1 the session
    if not league_hit:
        return 0
    sub = sc.norm(ev.get("sub"))
    if sub and any(sc.has_phrase(text, w) for w in session_words(ev.get("sub"))):
        return 3
    name_tokens = [t for t in sc.norm(ev.get("title")).split() if len(t) > 3]
    if name_tokens and sum(1 for t in name_tokens if t in text.split()) * 2 >= len(name_tokens):
        return 2
    return 1


_SESSION = {"Vrije training 1": ["vrije training 1", "free practice 1", "fp1", "training 1"],
            "Vrije training 2": ["vrije training 2", "free practice 2", "fp2", "training 2"],
            "Vrije training 3": ["vrije training 3", "free practice 3", "fp3", "training 3"],
            "Kwalificatie": ["kwalificatie", "qualifying", "kwalificatie"],
            "Sprintkwalificatie": ["sprintkwalificatie", "sprint qualifying", "sprint shootout"],
            "Sprint": ["sprint"], "Race": ["race", "grand prix", "gp"]}
_SESSION.update({"Free practice 1": _SESSION["Vrije training 1"], "Free practice 2": _SESSION["Vrije training 2"],
                 "Free practice 3": _SESSION["Vrije training 3"], "Qualifying": _SESSION["Kwalificatie"],
                 "Sprint qualifying": _SESSION["Sprintkwalificatie"]})


def session_words(sub):
    return _SESSION.get(sub, [sc.norm(sub)] if sub else [])


def near_kickoff(ev, start, end):
    kick = ev["start"]
    if start - LEAD <= kick <= start + LATE:
        return True
    return start <= kick <= end                      # the programme covers kick-off (long studio shows, race weekends)


def channels_for(ev, data=None):
    """Channels that show this game, best first."""
    data = data or load()
    names, icons = data.get("names", {}), data.get("icons", {})
    found = {}
    import bisect
    rows = data.get("rows", [])
    starts = _MEM["starts"] if data is _MEM["data"] else [r[1] for r in rows]
    lo = bisect.bisect_left(starts, ev["start"] - 24 * 3600)
    hi = bisect.bisect_right(starts, ev["start"] + 4 * 3600)
    for cid, start, end, title, plot in rows[lo:hi]:
        if end < ev["start"] - 3600 or start > ev["start"] + 4 * 3600:
            continue
        if ev["kind"] == "event" and ev["league"] != "f1":
            ok = start - 86400 <= ev["start"] <= end + 86400 or near_kickoff(ev, start, end)
        else:
            ok = near_kickoff(ev, start, end)
        if not ok:
            continue
        title_norm = sc.norm(title)
        if ev["state"] != "post" and any(sc.has_phrase(title_norm, w) for w in RECAP) and start >= ev["start"] - 3 * 3600:
            continue                         # a recap / pre-show is not the game itself
        text = sc.norm(f"{title} {plot}")
        score = score_event(ev, text, title_norm)
        if score <= 0:
            continue
        if score == 1 and not (start - 20 * 60 <= ev["start"] <= start + 20 * 60):
            continue
        raw = names.get(str(cid), "")
        best = found.get(cid)
        if not best or score > best["score"]:
            found[cid] = {"cid": cid, "name": clean_name(raw) or raw, "country": country_of(raw), "q": quality_of(raw),
                          "score": score, "title": title, "start": start, "icon": icons.get(str(cid), ""),
                          "live": start <= time.time() <= end}
    home_pref = ("NL", "BE")
    out = sorted(found.values(), key=lambda c: (-c["score"], 0 if c["country"] in home_pref else 1,
                                                {"4K": 0, "FHD": 1, "HD": 2, "": 3}.get(c["q"], 3), c["name"]))
    for chan in out:
        chan["tag"] = sc.t("sure") if chan["score"] >= 2 else sc.t("maybe")
    return out[:MAX_CHANNELS]


def play(cid):
    rpc("Player.Open", {"item": {"channelid": int(cid)}})
