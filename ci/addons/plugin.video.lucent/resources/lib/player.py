# -*- coding: utf-8 -*-
"""Finds sources, asks about resuming, and starts the video."""
import base64
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcgui
import xbmcplugin

import dialogs
import items
import ranking
import scrapers
import tmdb
import tracker
import util

HANDOFF = "lucent.video.now"
RUN = "lucent.video.run"
LOCAL = "progress.json"
LAST_RELEASE = "last_release.json"
MIME = {"mkv": "video/x-matroska", "mp4": "video/mp4", "avi": "video/x-msvideo", "m2ts": "video/mp2t", "ts": "video/mp2t"}


def progress_key(meta):
    if meta.get("type", meta.get("kind")) == "movie":
        return "movie:%s" % meta["tmdb"]
    return "ep:%s:%s:%s" % (meta["tmdb"], meta["season"], meta["episode"])


def title_meta(kind, tmdb_id, season=None, episode=None):
    if kind == "movie":
        return tmdb.details("movie", tmdb_id)
    show = tmdb.details("tvshow", tmdb_id)
    if not show:
        return None
    for raw in tmdb.season(tmdb_id, season).get("episodes") or []:
        if raw["episode_number"] == int(episode):
            return tmdb.episode_meta(show, raw)
    return None


def _fail(handle, text=None):
    if text:
        xbmcgui.Dialog().notification("Lucent", text, xbmcgui.NOTIFICATION_WARNING, 5000)
    if handle >= 0:
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem(offscreen=True))


def link_works(source):
    if not scrapers.ready(source):
        return False
    return _answers(source)


def _answers(source, offset=0):
    """A tiny request (one byte) to see whether the link answers. Works with redirects to the debrid service."""
    url, _, extra = source["url"].partition("|")
    head = dict(urllib.parse.parse_qsl(extra))
    parts = urllib.parse.urlsplit(url)
    if parts.username:           # urllib does not read a login from the address
        login = "%s:%s" % (urllib.parse.unquote(parts.username), urllib.parse.unquote(parts.password or ""))
        head["Authorization"] = "Basic " + base64.b64encode(login.encode("utf-8")).decode("ascii")
        url = urllib.parse.urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[1], parts.path, parts.query, ""))
    head.setdefault("User-Agent", "Lucent-Video/0.1")
    head["Range"] = "bytes=%d-%d" % (offset, offset)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=head), timeout=10) as response:
            return response.status < 400
    except (urllib.error.URLError, OSError, ValueError):
        return False


def first_working(sources, index):
    """The chosen source, or the next one that works when its link is dead."""
    needs_wait = any(s.get("resolve") for s in sources[index:index + 5])
    if needs_wait:
        xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
    try:
        return _first(sources, index)
    finally:
        if needs_wait:
            xbmc.executebuiltin("Dialog.Close(busydialognocancel)")


def _first(sources, index):
    import learn
    for position in range(index, min(index + 5, len(sources))):
        if link_works(sources[position]):
            if position != index:
                util.notify(util.T("Link werkte niet, volgende bron gekozen", "Link failed, using the next source"))
            return sources[position]
        learn.record(learn.key(sources[position]), False)
    for source in sources[index:]:
        if scrapers.ready(source):
            return source
    return sources[index]


def ask_resume(meta):
    """Returns the second to start from, 0 from the beginning, or None when cancelled."""
    runtime = int(meta.get("runtime") or 0) * 60
    saved = util.load_json(LOCAL, {}).get(progress_key(meta)) or {}
    position = float(saved.get("position") or 0)
    if saved.get("total"):
        runtime = int(saved["total"])
    percent = tracker.resume_percent(meta["kind"], meta["tmdb"], meta.get("season"), meta.get("episode"))
    if percent and runtime:
        position = runtime * percent / 100.0
    if position < 60 or (runtime and position > runtime * 0.92):
        return 0
    if util.number("resume_mode", 0) == 1:
        return position
    answer = dialogs.ask_resume(meta, items.clock(position), position * 100.0 / runtime if runtime else 0)
    return None if answer is None else (position if answer else 0)


def build(meta, source):
    url = source["url"]
    item = xbmcgui.ListItem(meta["title"], path=url, offscreen=True)
    item.setArt(items.art_of(meta))
    # Kodi reports the default id as "the IMDb number": other add-ons (like PunchPlay) read that while playing
    items.fill_tag(item, meta, default_id="imdb")
    item.setProperty("IsPlayable", "true")
    if meta["kind"] == "episode":      # read by Lucent Ondertitels and TheIntroDB
        for key in ("tmdb", "imdb", "tvdb"):
            if meta.get(key):
                item.setProperty("tvshow.%s_id" % key, str(meta[key]))
    extension = source["name"].rsplit(".", 1)[-1].lower()
    if extension in MIME:             # saves Kodi an extra request to the link
        item.setMimeType(MIME[extension])
        item.setContentLookup(False)
    return item


def lighter_than(source, order):
    """Up to three sources that are much smaller than the one playing, for when it keeps buffering."""
    size = source.get("size") or 0
    if not size:
        return []
    return [s for s in order if s is not source and s.get("cached") and 0 < (s.get("size") or 0) < size * 0.55][:3]


def handoff(meta, resume, source, alternates=None, others=None, lighter=None, last=False):
    keep = ("kind", "tmdb", "imdb", "season", "episode", "title", "runtime")
    now = {k: meta.get(k) for k in keep}
    import learn
    now.update(resume=resume, started=time.time(), alternates=alternates or [], url=source.get("url"), size=source.get("size") or 0,
               learn=learn.key(source), together=others or [], lighter=lighter or [], bedtime_last=bool(last))
    util.HOME.setProperty(HANDOFF, json.dumps(now))
    return now


def cannot_play(source):
    """Does this device, by the setting 'Dolby Vision on this device', not handle this source?"""
    support = util.number("dv_support", 0)
    tags = ranking.tags_of(source)
    return (support == 1 and bool(tags & {"fel", "p7"})) or (support == 2 and "dv" in tags) or is_hidden(source, tags)


def is_hidden(source, tags=None):
    """A format hidden after the format check: left out of the source list, autoplay and the next episode."""
    import formatcheck
    gone = formatcheck.hidden()
    return bool(gone and (tags or ranking.tags_of(source)) & gone)


def same_release_first(meta, sources):
    """A series keeps the release group and quality of the previous episode, so sound and language do not jump."""
    if meta["kind"] != "episode" or not util.flag("same_release"):
        return sources
    last = util.load_json(LAST_RELEASE, {}).get(str(meta["tmdb"]))
    if not last:
        return sources
    return sorted(sources, key=lambda s: 0 if (ranking.release_group(s) or "").lower() == last["group"] and s["resolution"] == last["res"] else 1)


def remember_release(meta, source):
    group = ranking.release_group(source)
    if meta["kind"] == "episode" and group:
        saved = util.load_json(LAST_RELEASE, {})
        saved[str(meta["tmdb"])] = {"group": group.lower(), "res": source["resolution"]}
        util.save_json(LAST_RELEASE, saved)


def link_is_dead(now, position, total):
    """Kodi reports a stream that broke the same as you pressing stop. So: does the link still answer at this point?"""
    if not now.get("url") or not total:
        return False
    return not _answers({"url": now["url"]}, int((now.get("size") or 0) * position / total))


def resume_elsewhere(now, position, lighter=False):
    """The link broke (or kept buffering: lighter=True). Starts the next source at the same place. True when one was started."""
    alternates = (now.get("lighter") if lighter else now.get("alternates")) or []
    full = None
    while alternates:
        source = alternates.pop(0)
        if not scrapers.ready(source) or not _answers(source):
            continue
        full = full or title_meta(now["kind"], now["tmdb"], now.get("season"), now.get("episode"))
        if not full:
            return False
        handoff(full, position, source, alternates, now.get("together"))
        import learn
        learn.record(now.get("learn"), False)          # the one that broke
        util.notify(util.T("Verder met een lichtere versie", "Continuing with a lighter version") if lighter else
                    util.T("Link viel weg, verder met een andere bron", "Link dropped, continuing with another source"))
        xbmc.Player().play(source["url"], build(full, source))
        return True
    return False


def find(meta_out, params):
    """Runs next to the 'Finding sources' screen. Fills meta_out['meta'] and meta_out['sources'] or meta_out['error']."""
    kind, tmdb_id = params.get("type"), params.get("tmdb")
    season, episode = params.get("season"), params.get("episode")
    try:
        meta = meta_out["meta"] = title_meta(kind, tmdb_id, season and int(season), episode and int(episode))
    except util.HttpError:
        meta = None
    if not meta:
        meta_out["error"] = util.T("Titel niet gevonden", "Title not found")
        return
    meta_out["ready"] = True
    sources, problem = scrapers.search(meta)
    if problem == "failed":
        meta_out["error"] = util.T("Geen scraper bereikbaar", "No scraper could be reached")
    elif problem is None:
        meta_out["sources"] = sources


def search_with_screen(params):
    """Shows the screen while searching. Returns (meta, sources), or None when cancelled or failed."""
    out = {}
    worker = threading.Thread(target=find, args=(out, params), daemon=True)
    worker.start()
    monitor = xbmc.Monitor()
    while worker.is_alive() and "ready" not in out and not monitor.waitForAbort(0.05):
        pass
    screen = dialogs.busy_dialog(out.get("meta"))
    started, limit = time.time(), max(5, util.number("timeout", 30))
    while worker.is_alive() and not screen.cancelled and not monitor.waitForAbort(0.1):
        screen.percent(min(90, (time.time() - started) * 90.0 / limit))
    if screen.cancelled:
        return None, "cancelled"
    if out.get("error") or out.get("sources") is None:
        screen.close()
        return None, out.get("error") or "address"
    screen.done(out["sources"])
    if out["sources"]:
        monitor.waitForAbort(0.8)
    screen.close()
    return out["meta"], out["sources"]


def play(params, handle):
    autoplay = params.get("autoplay") == "1"
    if not autoplay:
        util.HOME.clearProperty(RUN)
    if params.get("type") in ("movie", "episode", "tvshow"):
        import kids
        if kids.limit():
            check = tmdb.details("movie" if params["type"] == "movie" else "tvshow", params["tmdb"])
            if not check or not kids.allowed(check):
                return _fail(handle, util.T("Dit profiel mag deze titel niet kijken", "This profile may not watch this title"))
    if not autoplay and params.get("select") != "1" and params.get("type") in ("movie", "episode"):
        import abo
        try:
            first_meta = title_meta(params["type"], params["tmdb"], params.get("season") and int(params["season"]), params.get("episode") and int(params["episode"]))
        except util.HttpError:
            first_meta = None
        if first_meta and abo.offer(first_meta):
            return _fail(handle)
    import bedtime
    if params.get("type") in ("movie", "episode"):
        try:
            planned = title_meta(params["type"], params["tmdb"], params.get("season") and int(params["season"]), params.get("episode") and int(params["episode"]))
        except util.HttpError:
            planned = None
        allowed, last = bedtime.check(planned or {})
        if not allowed:
            return _fail(handle)
    else:
        last = False
    import together
    others = together.ask(params)
    import prefetch
    meta, sources = prefetch.take(params) if params.get("select") != "1" else (None, None)
    if meta is None:
        meta, sources = search_with_screen(params)
    if meta is None:
        if sources == "cancelled":
            return _fail(handle)
        if sources == "address":
            return _fail(handle, util.T("Stel eerst een scraper in, zoals AIOStreams, Easynews of TorBox", "Set up a scraper first, such as AIOStreams, Easynews or TorBox"))
        return _fail(handle, sources)
    if not sources:
        return _fail(handle, util.T("Geen bronnen over. Kijk naar je filters of probeer een ander profiel.", "No sources left. Check your filters or try another profile."))

    usable = sources if util.flag("include_uncached") or not any(s["cached"] for s in sources) else [s for s in sources if s["cached"]]
    for source in sources:
        source["cannot"] = cannot_play(source)
    usable = [s for s in usable if not s["cannot"]] or usable
    shown = [s for s in sources if not is_hidden(s)]
    sources = shown or sources
    if params.get("select") == "1" or (util.number("play_mode", 0) == 1 and not autoplay):
        chosen = dialogs.choose_source(meta, sources, util.flag("include_uncached"))
        if not chosen:
            return _fail(handle)
        if chosen["cannot"] and not xbmcgui.Dialog().yesno("Lucent", util.T("Dit apparaat kan deze bron volgens je instelling niet goed afspelen. Toch proberen?",
                                                                            "This device may not play this source properly, according to your setting. Try anyway?")):
            return _fail(handle)
        order = [chosen] + [s for s in usable if s is not chosen]
    else:
        order = same_release_first(meta, usable)
    # from the library Kodi itself asks about resuming; asking again would be a second pop-up
    resume = 0 if autoplay or params.get("lib") == "1" else ask_resume(meta)
    if resume is None:
        return _fail(handle)

    source = first_working(order, 0)
    if not source.get("url"):
        return _fail(handle, util.T("Deze bron kon niet worden gestart", "This source could not be started"))
    item = build(meta, source)
    remember_release(meta, source)
    handoff(meta, resume, source, [s for s in order if s is not source][:4], others, lighter_than(source, order), last)
    bedtime.counted()
    util.log("playing %s" % progress_key(meta))
    if handle >= 0:
        xbmcplugin.setResolvedUrl(handle, True, item)
    else:
        xbmc.Player().play(source["url"], item)
    return None
