# -*- coding: utf-8 -*-
"""'New season announced': once a day Lucent looks whether a series you follow got a date for a new season.
You get a message once per season, and it is in the row 'New seasons' (and the calendar shows its episodes once
they are near). For the skin: the row plugin://plugin.video.lucent/?action=list&name=new_seasons&widget=1 and the
Home property lucent.video.newseasons (number of announced seasons)."""
import datetime
import time

import tmdb
import tracker
import util

T = util.T
FILE = "new_seasons.json"
EVERY = 20 * 3600


def due():
    return util.flag("season_news") and time.time() - util.load_json(FILE, {}).get("at", 0) > EVERY


def _followed():
    try:
        shows = tracker.watched_episodes()
        listed = [str(i) for _k, i in tracker.pairs("watchlist_tv")][:40]
    except util.HttpError:
        return []
    recent = sorted(shows, key=lambda s: max(shows[s].values()) if shows[s] else "", reverse=True)[:60]
    return list(dict.fromkeys(recent + listed))


def run():
    data = util.load_json(FILE, {})
    data["at"] = time.time()
    found = {e["key"]: e for e in data.get("items") or []}
    today = datetime.date.today().isoformat()
    for show in _followed():
        try:
            raw = tmdb.get("tv/%s" % show, ttl=12 * 3600)
        except util.HttpError:
            continue
        coming = raw.get("next_episode_to_air") or {}
        seasons = [s for s in raw.get("seasons") or [] if (s.get("air_date") or "") > today and s.get("season_number", 0) > 0]
        number, date = None, None
        if coming.get("episode_number") == 1 and (coming.get("air_date") or "") >= today:
            number, date = coming.get("season_number"), coming.get("air_date")
        elif seasons:
            number, date = seasons[0]["season_number"], seasons[0]["air_date"]
        if not number or not date:
            continue
        key = "%s:%s" % (show, number)
        if key in found:
            found[key]["date"] = date
            continue
        found[key] = {"key": key, "show": show, "season": number, "date": date, "title": raw.get("name") or ""}
        util.notify(T("Nieuw seizoen: %s seizoen %d op %s", "New season: %s season %d on %s") % (raw.get("name") or "", number, date))
    data["items"] = sorted((e for e in found.values() if e["date"] >= today), key=lambda e: e["date"])
    util.save_json(FILE, data)
    publish(data)


def publish(data=None):
    data = data or util.load_json(FILE, {})
    count = len(data.get("items") or [])
    util.HOME.setProperty("lucent.video.newseasons", str(count) if count else "")


def titles():
    items = util.load_json(FILE, {}).get("items") or []
    metas = tmdb.many([("tvshow", e["show"]) for e in items])
    by_id = {m["tmdb"]: m for m in metas}
    out = []
    for entry in items:
        meta = by_id.get(str(entry["show"]))
        if meta:
            meta = dict(meta, plot=T("Seizoen %d begint op %s. ", "Season %d starts on %s. ") % (entry["season"], entry["date"]) + (meta.get("plot") or ""))
            out.append(meta)
    return out
