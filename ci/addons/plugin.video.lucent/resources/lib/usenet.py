# -*- coding: utf-8 -*-
"""Easynews and TorBox: they do the usenet (NNTP) or debrid work on their side and give back a normal web stream.

Passwords and keys are never logged and never written to the cache.
"""
from concurrent.futures import ThreadPoolExecutor
import base64
import re
import time
import urllib.parse
import uuid

import xbmc

import ranking
import streams
import tmdb
import util

T = util.T
EASYNEWS = "https://members.easynews.com"
TB_SEARCH = "https://search-api.torbox.app"
TB_API = "https://api.torbox.app/v1/api"
VIDEO = (".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".mov", ".wmv", ".webm")
MIN_SECONDS = 600
KEEP_RESULTS = 600
FLAG_OF = [("dv2", "DV2"), ("fel", "aio_FEL"), ("p7", "aio_P7"), ("hdr", "HDR"), ("hlg", "HDR"), ("sdr", "SDR"), ("3d", "3D"), ("imax", "aio_IMAX"), ("hevc", "HEVC"), ("avc", "AVC"), ("av1", "AV1"),
           ("remux", "REMUX"), ("bluray", "BLURAY"), ("web", "WEB"), ("hdtv", "HDTV"), ("cam", "CAM"), ("atmos", "ATMOS"), ("truehd", "TRUEHD"), ("dtsx", "DTS-X"), ("dtsma", "DTS-HDMA"),
           ("dtshd", "DTS-HD"), ("ddplus", "DD+"), ("aac", "AAC"), ("opus", "OPUS"), ("71", "7.1"), ("51", "5.1"), ("20", "2.0"), ("nl", "aio_NL"), ("multi", "aio_MULTI"), ("nlsubs", "aio_NL-SUBS")]
AGENT = "Lucent-Video/0.7"


def _flags(name):
    tags = ranking.tags_of({"name": name, "resolution": "SD", "cached": True, "size": 0})
    flags = ["DV"] if "dv" in tags and "dv2" not in tags else []
    return flags + [flag for tag, flag in FLAG_OF if tag in tags]


def _source(name, size, service, url="", cached=True, resolve=None):
    size = size or 0
    return {"url": url, "name": name, "resolution": streams.resolution({}, name), "flags": _flags(name), "badges": [], "size": size, "service": service, "cached": cached, "resolve": resolve,
            "meta": " · ".join(p for p in (service, streams.size_text(size)) if p)}


def _words(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower().replace("&", " and ")).split()


def title_matches(name, titles, meta):
    """Search engines return lookalikes: the name must start with the title, then the right year or episode."""
    words = _words(name)
    for title in titles:
        wanted = _words(title)
        if wanted and words[:len(wanted)] == wanted:
            rest = " ".join(words[len(wanted):])
            if meta["kind"] == "movie":
                year = int(meta.get("year") or 0)
                if not year or any(re.search(r"\b%d\b" % y, rest) for y in (year - 1, year, year + 1)):
                    return not re.search(r"\bs\d{1,2} ?e\d{1,3}\b", rest)
            elif re.search(r"\bs0*%d ?e0*%d\b|\b0*%dx0*%d\b" % (int(meta["season"]), int(meta["episode"]), int(meta["season"]), int(meta["episode"])), rest):
                return True
    return False


def titles_for(meta):
    """English and original titles: releases are almost never named after the Dutch title."""
    kind = "movie" if meta["kind"] == "movie" else "tvshow"
    api = "movie" if kind == "movie" else "tv"
    names = [meta.get("show") or meta.get("title") or ""]
    raw = tmdb.get("%s/%s" % (api, meta["tmdb"]), ttl=7 * tmdb.DAY, language="en-US")
    for key in ("title", "name", "original_title", "original_name"):
        if raw.get(key):
            names.insert(0, raw[key]) if key in ("title", "name") else names.append(raw[key])
    return list(dict.fromkeys(n for n in names if n))


# ------------------------------------------------------------------------ Easynews
def _en_login():
    return util.setting("easynews_user"), util.setting("easynews_pass")


def _en_header():
    user, password = _en_login()
    return "Basic " + base64.b64encode(("%s:%s" % (user, password)).encode("utf-8")).decode("ascii")


def _en_size(value):
    if isinstance(value, (int, float)):
        return int(value)
    found = re.match(r"\s*([\d.]+)\s*([KMGT]?)B?", str(value or ""), re.I)
    if not found:
        return 0
    return int(float(found.group(1)) * 1024 ** " KMGT".index((found.group(2) or " ").upper()))


def _en_seconds(item):
    value = item.get("runtime") if isinstance(item, dict) else None
    if value is None and isinstance(item, dict):
        value = item.get("14")
    if isinstance(value, (int, float)):
        return value
    found = re.findall(r"(\d+)\s*([hms])", str(value or ""))
    return sum(int(n) * {"h": 3600, "m": 60, "s": 1}[u] for n, u in found) if found else None


def _en_item(raw):
    """(hash, id, name without extension, extension, size, passworded or infected?, seconds) from either answer shape."""
    if isinstance(raw, list):
        if len(raw) < 12:
            return None
        return raw[0], "", raw[10], raw[11], _en_size(raw[4]), False, None
    key = str(raw.get("hash") or raw.get("0") or "")
    extension = str(raw.get("extension") or raw.get("ext") or raw.get("11") or "")
    return key, str(raw.get("id") or ""), str(raw.get("fn") or raw.get("10") or ""), extension, _en_size(raw.get("rawSize") or raw.get("size") or raw.get("4")), \
        bool(raw.get("passwd") or raw.get("virus")), _en_seconds(raw)


def _en_search(query):
    key = "easynews" + query
    answer = util.cache_get(key, KEEP_RESULTS)
    if answer is None:
        params = {"gps": query, "pno": 1, "pby": 250, "u": 1, "safeO": 0, "s1": "relevance", "s1d": "-", "fty[]": "VIDEO", "fly": 2, "sb": 1, "st": "basic", "chxu": 1, "chxgx": 1, "vv": 1}
        answer, _ = util.http(EASYNEWS + "/2.0/search/solr-search/?" + urllib.parse.urlencode(params), headers={"Authorization": _en_header(), "User-Agent": AGENT}, timeout=25)
        util.cache_set(key, answer)
    return answer or {}


def easynews(meta):
    if not all(_en_login()):
        return None
    titles = titles_for(meta)
    query = "%s %s" % (titles[0], meta.get("year") or "") if meta["kind"] == "movie" else "%s S%02dE%02d" % (titles[0], int(meta["season"]), int(meta["episode"]))
    answer = _en_search(query.strip())
    base = "%s/%s/%s" % (answer.get("downURL") or EASYNEWS + "/dl", answer.get("dlFarm") or "auto", answer.get("dlPort") or "auto")
    # Login inside the address, not as a header: Kodi hides the first in its log but writes the second out in full.
    parts = urllib.parse.urlsplit(base)
    user, password = _en_login()
    base = "%s://%s:%s@%s%s" % (parts.scheme, urllib.parse.quote(user, safe=""), urllib.parse.quote(password, safe=""), parts.netloc, parts.path)
    agent = urllib.parse.urlencode({"User-Agent": AGENT})
    out = []
    for raw in answer.get("data") or []:
        item = _en_item(raw)
        if not item:
            continue
        key, suffix, stem, extension, size, bad, seconds = item
        extension = "." + extension.lstrip(".")
        low = stem.lower()
        if not key or bad or extension.lower() not in VIDEO or (seconds is not None and seconds < MIN_SECONDS) or "sample" in low[len(low) // 2:]:
            continue
        if not title_matches(stem, titles, meta):
            continue
        name = stem + extension
        path = "%s%s%s/%s" % (key, suffix, extension, urllib.parse.quote(name))
        out.append(_source(name, size, "EASYNEWS", url="%s/%s|%s" % (base, path, agent)))
    return out


def check_easynews():
    if not all(_en_login()):
        return False, T("Vul eerst je gebruikersnaam en wachtwoord in.", "Enter your username and password first.")
    try:
        answer, _ = util.http(EASYNEWS + "/2.0/search/solr-search/?fly=2&gps=test&pby=1&pno=1&safeO=0&sb=1&st=basic", headers={"Authorization": _en_header(), "User-Agent": AGENT}, timeout=25)
    except util.HttpError as error:
        return False, T("Geen verbinding: %s", "No connection: %s") % error
    return bool(answer is not None), T("Verbonden met Easynews.", "Connected to Easynews.")


# ------------------------------------------------------------------------ TorBox
def _tb_key():
    return util.setting("torbox_key")


def _tb_head():
    return {"Authorization": "Bearer %s" % _tb_key(), "User-Agent": AGENT}


def _tb_search(kind, meta):
    """kind: usenet or torrents. Returns the rows, or None when this search failed."""
    ident = "imdb_id:%s" % meta["imdb"] if meta.get("imdb") else "tmdb_id:%s" % meta["tmdb"]
    params = {"check_cache": "true", "metadata": "false"}
    if meta["kind"] == "episode":
        params.update(season=meta["season"], episode=meta["episode"])
    url = "%s/%s/%s?%s" % (TB_SEARCH, kind, ident, urllib.parse.urlencode(params))
    key = "torboxsearch" + url
    answer = util.cache_get(key, KEEP_RESULTS)
    if answer is None:
        try:
            answer, _ = util.http(url, headers=_tb_head(), timeout=25)
        except util.HttpError as error:
            util.log("TorBox %s: %s" % (kind, error))
            return None
        util.cache_set(key, answer)
    data = (answer or {}).get("data") or {}
    return data.get("nzbs" if kind == "usenet" else "torrents") or []


def torbox(meta):
    """Usenet and debrid (torrent) files. Only what TorBox already has, so it can stream right away."""
    if not _tb_key():
        return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        usenet_rows, torrent_rows = pool.map(lambda kind: _tb_search(kind, meta), ("usenet", "torrents"))
    if usenet_rows is None and torrent_rows is None:
        raise util.HttpError("TorBox")
    out = []
    for kind, label, rows, link_key in (("usenet", "USENET", usenet_rows, "nzb"), ("torrents", "DEBRID", torrent_rows, "magnet")):
        for row in rows or []:
            if not row.get(link_key) or not row.get("cached"):
                continue
            name = row.get("raw_title") or row.get("title") or ""
            source = _source(name, row.get("size"), "TORBOX %s" % label, resolve={"scraper": "TorBox", "kind": kind, "link": row[link_key], "name": name,
                                                                                  "season": meta.get("season"), "episode": meta.get("episode")})
            out.append(source)
    return out


def _tb_create(job):
    """Puts the release in the TorBox account. Returns its id."""
    boundary = uuid.uuid4().hex
    if job["kind"] == "usenet":
        path, fields, id_key = "/usenet/createusenetdownload", {"link": job["link"], "name": job["name"]}, "usenetdownload_id"
    else:
        path, fields, id_key = "/torrents/createtorrent", {"magnet": job["link"], "name": job["name"], "seed": "3"}, "torrent_id"
    body = "".join('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, k, v) for k, v in fields.items()) + "--%s--\r\n" % boundary
    answer, _ = util.http(TB_API + path, raw=(body.encode("utf-8"), "multipart/form-data; boundary=%s" % boundary), headers=_tb_head(), timeout=30)
    return ((answer or {}).get("data") or {}).get(id_key)


def _tb_file(item, season, episode):
    files = [f for f in item.get("files") or [] if str(f.get("name") or f.get("short_name") or "").lower().endswith(VIDEO)]
    if season and episode:
        pattern = re.compile(r"s0*%d[ ._-]?e0*%d\b" % (int(season), int(episode)), re.I)
        exact = [f for f in files if pattern.search(str(f.get("name") or ""))]
        files = exact or files
    return max(files, key=lambda f: f.get("size") or 0) if files else None


def torbox_link(job):
    """Adds the release to TorBox (instant when cached), then asks for its web stream. Returns the address, or None."""
    area, id_name = ("usenet", "usenet_id") if job["kind"] == "usenet" else ("torrents", "torrent_id")
    try:
        item_id = _tb_create(job)
        if not item_id:
            return None
        monitor = xbmc.Monitor()
        end = time.time() + 20
        chosen = None
        while time.time() < end and not chosen:
            answer, _ = util.http("%s/%s/mylist?id=%s&bypass_cache=true" % (TB_API, area, item_id), headers=_tb_head(), timeout=20)
            item = (answer or {}).get("data") or {}
            if isinstance(item, list):
                item = item[0] if item else {}
            chosen = _tb_file(item, job.get("season"), job.get("episode"))
            if not chosen and monitor.waitForAbort(1):
                return None
        if not chosen:
            return None
        query = urllib.parse.urlencode({"token": _tb_key(), id_name: item_id, "file_id": chosen["id"], "redirect": "false"})
        answer, _ = util.http("%s/%s/requestdl?%s" % (TB_API, area, query), headers=_tb_head(), timeout=25)
        return (answer or {}).get("data")
    except util.HttpError as error:
        util.log("TorBox link: %s" % error)
        return None


def check_torbox():
    if not _tb_key():
        return False, T("Vul eerst je API-sleutel in.", "Enter your API key first.")
    try:
        answer, _ = util.http(TB_API + "/user/me", headers=_tb_head())
    except util.HttpError as error:
        return False, T("Geen verbinding: %s", "No connection: %s") % error
    plan = ((answer or {}).get("data") or {}).get("plan")
    return True, T("Verbonden met TorBox (abonnement %s).", "Connected to TorBox (plan %s).") % plan
