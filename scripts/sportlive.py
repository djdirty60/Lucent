# -*- coding: utf-8 -*-
"""Lucent: the sport layer of the TV player (examples P1 - P5).

While a channel plays that shows a live game (live.py finds it), this keeps Window(home).Property(live.*) up to date:
    live.sc.*      the scoreboard (top left, always on screen): sides, score, clock, colours, sport
    live.d.*       statistics (st1..6), goals per side, points per period, top players, timeline
    live.t.*       a piece of the table around both teams
    live.a.N.*     'Also live': the other live games with a channel
    live.f.*       a race: the positions (tower)
The helper calls tick() every 20 seconds while live TV plays.

    RunScript(special://skin/scripts/sportlive.py,panel,stats|timeline|table)   the panel on the right (P2)
    RunScript(special://skin/scripts/sportlive.py,also)                         'Also live' (P3)
    RunScript(special://skin/scripts/sportlive.py,switch,N)                     watch 'Also live' game N
"""
import sys
import time

import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)
NA = 8                      # 'Also live' cards
_STATE = {"cid": None, "score": 0.0, "detail": 0.0, "table": 0.0, "ev": ""}


def log(text):
    xbmc.log(f"[skin.lucent] sportlive: {text}", xbmc.LOGINFO)


def put(name, value):
    value = "" if value is None else str(value)
    if HOME.getProperty(name) != value:
        HOME.setProperty(name, value)


def clear(prefix, keys):
    for k in keys:
        HOME.clearProperty(prefix + k)


# ----------------------------------------------------------------------------- the game on this channel
def game_on(cid):
    """The live game on channel cid (or None)."""
    import sport_core as sc
    live = [ev for ev in sc.all_cached() if ev.get("state") == "in" and ev.get("kind") in ("teams", "event")]
    if not live:
        return None
    import sport_epg as epg
    data = epg.load()
    if not data or not data.get("rows"):
        return None
    for ev in live:
        if any(str(c["cid"]) == str(cid) for c in epg.channels_for(ev, data)):
            return ev
    return None


def side_props(ev):
    import sport_core as sc
    import live
    out = {}
    sport = sc.LEAGUES.get(ev["league"], {}).get("sport", "")
    out["sport"] = sport
    out["league"] = sc.league_name_of(ev["league"])
    out["id"] = ev["id"]
    if ev["kind"] == "event":
        out.update(title=ev.get("title", ""), clock=ev.get("status", ""), race="1" if sport == "racing" else "")
        return out
    h, a = ev["home"], ev["away"]
    out["title"] = f"{h.get('short') or h.get('name', '')} – {a.get('short') or a.get('name', '')}"
    out["clock"] = ev.get("status", "")
    out["hcol"], out["acol"] = live.colour(h, "FFB3262E"), live.colour(a, "FF1F4E9E")
    return out


def detail_props(ev):
    """Statistics, goals, periods, top players and timeline of a team game."""
    import sport_core as sc
    out = {}
    try:
        d = sc.match_detail(ev)
    except Exception as error:  # noqa: BLE001
        log(f"detail: {error}")
        return out
    for k, v in d.items():
        out[k] = v
    # goals per side, oldest first ('12' Brobbey · 58' Taylor')
    habbr = ev["home"].get("abbr") or ev["home"].get("name", "")
    goals = {"h": [], "a": []}
    for i in range(5, 0, -1):
        minute = d.get(f"sc{i}m")
        if not minute:
            continue
        who = d.get(f"sc{i}x", "")
        who = who.replace(" Own Goal", " (og)" if not sc.NL else " (e.d.)").replace(" Penalty - Scored", " (p)")
        for word in (" Goal", "Goal - ", "Goal! "):
            who = who.replace(word, "")
        goals["h" if d.get(f"sc{i}t") == habbr else "a"].append(f"{minute} {who.strip()}".strip())
    out["hgoals"] = "  ·  ".join(goals["h"])
    out["agoals"] = "  ·  ".join(goals["a"])
    return out


def table_props(ev):
    import sport_core as sc
    out = {}
    if ev["kind"] != "teams":
        return out
    marks = {s.get("id") for s in (ev["home"], ev["away"]) if s.get("id")}
    try:
        rows = [r for r in sc.table_rows(ev["league"], marks) if r.get("id")]
    except Exception as error:  # noqa: BLE001
        log(f"table: {error}")
        return out
    keep = set(range(min(2, len(rows))))
    for i, r in enumerate(rows):
        if r["id"] in marks:
            keep |= {i - 1, i, i + 1}
    picked = [rows[i] for i in sorted(keep) if 0 <= i < len(rows)][:9]
    for n, r in enumerate(picked, 1):
        out.update({f"{n}rank": str(r.get("rank", "")), f"{n}team": r.get("team", ""), f"{n}gp": str(r.get("gp", "")),
                    f"{n}gd": str(r.get("gd", "")), f"{n}pts": str(r.get("pts", "")), f"{n}mine": "1" if r["id"] in marks else "",
                    f"{n}logo": r.get("logo", "")})
    out["n"] = str(len(picked))
    return out


def race_props(ev):
    """Positions of the race on now (no gaps: ESPN does not give them)."""
    import sport_core as sc
    out = {}
    try:
        comps = ev.get("competitions") or []
        comp = next((c for c in comps if c.get("state") == "in"), comps[-1] if comps else {})
        rows = sc.session_results(ev["league"], ev["id"].split(":", 1)[-1], comp.get("id") if isinstance(comp, dict) else comp, final=False)
    except Exception as error:  # noqa: BLE001
        log(f"race: {error}")
        rows = []
    for n, r in enumerate(rows[:10], 1):
        out[f"{n}pos"], out[f"{n}name"], out[f"{n}team"] = r.get("pos", str(n)), r.get("name", ""), r.get("team", "")
    out["n"] = str(len(rows[:10]))
    return out


def also_props(exclude):
    """The other live games that are on one of your channels."""
    import sport_core as sc
    import sport_epg as epg
    data = epg.load()
    out = []
    if not data or not data.get("rows"):
        return out
    for ev in sc.all_cached():
        if ev.get("state") != "in" or ev["id"] == exclude:
            continue
        chans = epg.channels_for(ev, data)
        if not chans:
            continue
        ch = chans[0]
        row = {"id": ev["id"], "league": sc.league_name_of(ev["league"]), "clock": ev.get("status", "") or "LIVE",
               "cid": str(ch["cid"]), "chan": sc.display_channel(ch.get("name", "")),
               "chicon": sc.channel_logo(ch.get("name", "")) or ""}
        if ev["kind"] == "teams":
            row.update(hname=ev["home"].get("short") or ev["home"].get("name", ""), aname=ev["away"].get("short") or ev["away"].get("name", ""),
                       hs=str(ev["home"].get("score", "")), as_=str(ev["away"].get("score", "")),
                       hcol=sc.club_hex(ev["home"].get("color"), ev["home"].get("alt")) or "2A3441",
                       acol=sc.club_hex(ev["away"].get("color"), ev["away"].get("alt")) or "2A3441")
        else:
            row.update(hname=ev.get("title", ""), aname="", hs="", as_="", hcol="E10600", acol="E10600")
        out.append(row)
        if len(out) >= NA:
            break
    return out


# ----------------------------------------------------------------------------- keeping it up to date
D_KEYS = tuple([f"st{n}{k}" for n in range(1, 7) for k in "lhak"] + [f"q{s}{n}" for s in "ha" for n in range(1, 9)] + ["qn"]
               + [f"tp{n}{k}" for n in range(1, 5) for k in "tnv"] + [f"tl{n}{k}" for n in range(1, 13) for k in "mkx"]
               + ["hgoals", "agoals"] + [f"sc{n}{k}" for n in range(1, 6) for k in "mtx"])
T_KEYS = tuple([f"{n}{k}" for n in range(1, 10) for k in ("rank", "team", "gp", "gd", "pts", "mine", "logo")] + ["n"])
F_KEYS = tuple([f"{n}{k}" for n in range(1, 11) for k in ("pos", "name", "team")] + ["n"])
SC_KEYS = ("sport", "league", "id", "title", "race")


def clear_all():
    clear("live.d.", D_KEYS)
    clear("live.t.", T_KEYS)
    clear("live.f.", F_KEYS)
    clear("live.sc.", SC_KEYS)


def tick(force=False):
    """Helper, every 20 s while live TV plays: follow the channel, the score, the statistics."""
    if not xbmc.getCondVisibility("Pvr.IsPlayingTV"):
        if _STATE["cid"] is not None:
            _STATE.update(cid=None, ev="")
            clear_all()
        return
    import live
    here = live.current_channel()
    cid = here["id"] if here else None
    now = time.time()
    if cid != _STATE["cid"]:
        _STATE.update(cid=cid, score=0.0, detail=0.0, table=0.0, ev="")
        clear_all()
        live.clear_score()
    if cid is None or (not force and now - _STATE["score"] < 55):
        return
    _STATE["score"] = now
    import sport_core as sc
    ev = game_on(cid)
    if ev and ev["kind"] == "teams":
        try:
            sc.refresh(keys=[ev["league"]])
            ev = next((e for e in sc.all_cached() if e["id"] == ev["id"]), ev)
        except Exception as error:  # noqa: BLE001
            log(f"refresh: {error}")
    if not ev:
        if _STATE["ev"]:
            clear_all()
            live.clear_score()
            _STATE["ev"] = ""
        return
    if ev["kind"] == "teams":
        live.show(ev)
    else:
        HOME.setProperty("live.sc.on", "1")
        HOME.setProperty("live.sc.clock", ev.get("status", ""))
    for k, v in side_props(ev).items():
        put(f"live.sc.{k}", v)
    _STATE["ev"] = ev["id"]
    if ev["kind"] == "teams":
        for k, v in detail_props(ev).items():
            put(f"live.d.{k}", v)
        if now - _STATE["table"] > 600:
            _STATE["table"] = now
            clear("live.t.", T_KEYS)
            for k, v in table_props(ev).items():
                put(f"live.t.{k}", v)
    elif HOME.getProperty("live.sc.race"):
        for k, v in race_props(ev).items():
            put(f"live.f.{k}", v)


def fill_also():
    rows = also_props(HOME.getProperty("live.sc.id"))
    keys = ("id", "league", "clock", "cid", "chan", "chicon", "hname", "aname", "hs", "as_", "hcol", "acol")
    for n in range(1, NA + 1):
        row = rows[n - 1] if n <= len(rows) else {}
        for k in keys:
            put(f"live.a.{n}.{k.rstrip('_')}", row.get(k, ""))
    put("live.a.count", str(len(rows)))


def open_panel(mode, tab="stats"):
    """The panel (P2) or 'Also live' (P3) over the picture."""
    HOME.setProperty("live.p.mode", mode)
    HOME.setProperty("live.p.tab", tab)
    if mode == "also":
        fill_also()
    xbmc.executebuiltin("Dialog.Close(videoosd,true)")
    import xbmcaddon
    win = xbmcgui.WindowXMLDialog("Lucent_SportLive.xml", xbmcaddon.Addon("skin.lucent").getAddonInfo("path"), "Default", "1080i")
    win.doModal()
    del win


def switch(n):
    cid = HOME.getProperty(f"live.a.{n}.cid")
    if cid.isdigit():
        import live
        HOME.setProperty("live.prev.cid", str(_STATE.get("cid") or ""))
        xbmc.executebuiltin("Dialog.Close(all,true)")
        live.play(cid)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["panel"]:
        open_panel("panel", args[1] if len(args) > 1 else "stats")
    elif args[:1] == ["also"]:
        open_panel("also")
    elif args[:1] == ["switch"] and len(args) > 1:
        switch(args[1])
    else:
        tick(force=True)
