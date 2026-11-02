# -*- coding: utf-8 -*-
"""Lucent: what the Calendar and Sport tabs show on Home when they have no rows of their own.

The helper calls update() every minute. It writes Window(home).Property(lucent.pc.N.*) (Calendar: coming up) and
lucent.ps.N.* (Sport: today), N = 1..8; Home.xml shows them as cards with the first (or focused) one big above them.
    RunScript(special://skin/scripts/tabpanels.py,open,cal,N)     OK on a calendar card: open it in Seren
"""
import datetime
import sys
import time

import xbmc
import xbmcgui

HOME = xbmcgui.Window(10000)
N = 8
_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"


def tr(en, nl):
    return nl if _NL else en


def log(text):
    xbmc.log(f"[skin.lucent] tabpanels: {text}", xbmc.LOGINFO)


def put(name, value):
    value = "" if value is None else str(value)
    if HOME.getProperty(name) != value:
        HOME.setProperty(name, value)


def fill(prefix, rows):
    for n in range(1, N + 1):
        row = rows[n - 1] if n <= len(rows) else {}
        for key in KEYS[prefix]:
            put(f"{prefix}.{n}.{key}", row.get(key, ""))
    put(f"{prefix}.count", len(rows))


KEYS = {
    "lucent.pc": ("title", "sub", "day", "kick", "art", "logo", "plot", "net", "kind", "tmdb", "today", "eptitle"),
    "lucent.ps": ("id", "hname", "aname", "hlogo", "alogo", "hcol", "acol", "hs", "as", "when", "live", "league", "kick", "mine", "big"),
}


# ----------------------------------------------------------------------------- Calendar: this week
def calendar_rows():
    import agenda_core as ac
    today = ac.today()
    last = today + datetime.timedelta(days=90)            # the next ones, also when nothing airs this week
    now = datetime.datetime.now().strftime("%H:%M")
    rows = []
    for ev in ac.all_events():
        try:
            d = datetime.date.fromisoformat(ev["date"])
        except (KeyError, ValueError):
            continue
        if not today <= d <= last:
            continue
        at = ev.get("time") or ""
        if d == today:
            day = (tr("Tonight", "Vanavond") if at >= "18:00" else tr("Today", "Vandaag")) + (f" {at}" if at else "")
            if at and at < now:
                day = tr("Today", "Vandaag") + f" {at}"
        elif d == today + datetime.timedelta(days=1):
            day = tr("Tomorrow", "Morgen") + (f" {at}" if at else "")
        else:
            day = ac.day_short(d).capitalize()
        if ev.get("kind") == "tv":
            sub = ac.ep_code(ev)
            what = tr("New episode", "Nieuwe aflevering")
        else:
            sub = tr("Out digitally", "Digitaal te koop") if ev.get("digital") else tr("In cinemas", "In de bioscoop")
            what = tr("Film", "Film")
        kick = " · ".join(p for p in (day, what, ev.get("network") or "") if p)
        rows.append({"title": ev.get("name", ""), "sub": sub, "day": day, "kick": kick.upper(),
                     "art": ev.get("still") or ev.get("backdrop") or ev.get("poster") or "",
                     "logo": ev.get("logo") or "", "plot": ev.get("plot") or "", "net": ev.get("network") or "",
                     "kind": ev.get("kind", "tv"), "tmdb": ev.get("tmdb", ""), "today": "1" if d == today else "",
                     "eptitle": ev.get("title") or ""})
        if len(rows) >= N:
            break
    return rows


# ----------------------------------------------------------------------------- Sport: today
def sport_rows():
    import sport_core as sc
    if not sc.has_follow():
        return []
    follow = sc.load_follow()
    now = time.time()
    today = sc.local_day(now)
    games = []
    for ev in sc.all_cached():
        if ev.get("kind") != "teams":
            continue
        live = ev.get("state") == "in"
        if not live and sc.local_day(ev["start"]) != today:
            continue
        mine = bool(sc.is_following_team(follow, ev["home"]) or sc.is_following_team(follow, ev["away"]))
        games.append((0 if mine else 1, 0 if live else (1 if ev["state"] == "pre" else 2), ev["start"], ev, mine))
    games.sort(key=lambda g: g[:3])
    rows = []
    for _m, _l, _s, ev, mine in games[:N]:
        live, done = ev["state"] == "in", ev["state"] == "post"
        if live:
            when = f"LIVE {ev.get('status') or ''}".strip()
        elif done:
            when = tr("Full time", "Afgelopen")
        else:
            when = sc.local_time(ev["start"])
        league = sc.league_name_of(ev["league"])
        h, a = ev["home"], ev["away"]

        def col(side):
            value = sc.club_hex(side.get("color"), side.get("alt"))
            return value.upper() if value else "2A3441"
        rows.append({"id": ev["id"], "hname": h.get("short") or h.get("name", ""), "aname": a.get("short") or a.get("name", ""),
                     "hlogo": h.get("logo", ""), "alogo": a.get("logo", ""), "hcol": col(h), "acol": col(a),
                     "hs": str(h.get("score", "")) if (live or done) else "", "as": str(a.get("score", "")) if (live or done) else "",
                     "when": when, "live": "1" if live else "", "league": league,
                     "kick": " · ".join(p for p in (("LIVE" if live else when), league, (ev.get("status") or "") if live else "") if p).upper(),
                     "mine": "1" if mine else "",
                     "big": f"{h.get('score', '')} – {a.get('score', '')}" if (live or done) else sc.local_time(ev["start"])})
    return rows


def update():
    for prefix, rows in (("lucent.pc", calendar_rows), ("lucent.ps", sport_rows)):
        try:
            fill(prefix, rows())
        except Exception as error:  # noqa: BLE001 - one panel must not stop the other
            log(f"{prefix}: {error}")
    tv_path()


def tv_path():
    """The channels the TV tab shows: your favourite guide group, else all channels (Kodi wants 'name@client')."""
    if not xbmc.getCondVisibility("Pvr.HasTVChannels"):
        put("lucent.ptv.path", "")
        return
    want = xbmc.getInfoLabel("Skin.String(lucent.guide.group)")
    path = "pvr://channels/tv/*/"
    if want:
        import json
        try:
            reply = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
                                                                "params": {"directory": "pvr://channels/tv/", "media": "files"}})))
            for f in (reply.get("result") or {}).get("files") or []:
                if f.get("label") == want and f.get("file"):
                    path = f["file"]
                    break
        except Exception as error:  # noqa: BLE001
            log(f"tv group: {error}")
    put("lucent.ptv.path", path)
    put("lucent.ptv.title", tr("On your channels now", "Nu op je zenders") if want else tr("On TV now", "Nu op tv"))


def open_calendar(n):
    import agenda_core as ac
    p = f"lucent.pc.{n}."
    name, kind, tmdb = HOME.getProperty(p + "title"), HOME.getProperty(p + "kind") or "tv", HOME.getProperty(p + "tmdb")
    if name:
        ac.open_in_seren(name, kind, int(tmdb) if tmdb.isdigit() else None)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:2] == ["open", "cal"] and len(args) > 2:
        open_calendar(args[2])
    else:
        update()
