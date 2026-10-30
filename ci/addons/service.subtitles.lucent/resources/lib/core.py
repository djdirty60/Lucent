# -*- coding: utf-8 -*-
"""Lucent Ondertitels: the sources and the ranking.

Every source gets the same 'video' (what is playing) and answers a list of dicts:
    {"src", "id", "lang" (ISO 639-1), "release", "sync" (fits this exact video), "hi", "score" (0-5), "extra"}
They run at the same time, each with a time limit, so one slow site never holds the list up.
"""
import io
import json
import os
import re
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
VERSION = ADDON.getAddonInfo("version")
UA = f"Lucent v{VERSION}"
DATA = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
TEMP = xbmcvfs.translatePath("special://temp/lucent_subs/")
CACHE_TTL = 30 * 60

OS_API = "https://api.opensubtitles.com/api/v1"
SUBDL_API = "https://api.subdl.com/api/v1/subtitles"
SUBDL_DL = "https://dl.subdl.com"
PODNAPISI = "https://www.podnapisi.net"

SUB_EXT = (".srt", ".ass", ".ssa", ".sub", ".vtt", ".smi")


def log(text):
    xbmc.log(f"[service.subtitles.lucent] {text}", xbmc.LOGINFO)


def setting(key):
    return ADDON.getSetting(key) or ""


def on(key):
    return setting(key).lower() == "true"


# ----------------------------------------------------------------------------- http
def request(url, data=None, headers=None, timeout=10, method=None):
    head = {"User-Agent": UA, "Accept": "application/json"}
    head.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        head["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=head, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_json(url, **kw):
    return json.loads(request(url, **kw).decode("utf-8") or "{}")


# ----------------------------------------------------------------------------- languages
SPECIAL = {"pb": "pt-BR", "pt": "pt-PT", "zh": "zh-CN"}


def to_code(name):
    """'Dutch' / 'Portuguese (Brazil)' -> 'nl' / 'pb'."""
    name = (name or "").strip()
    if name.lower() in ("portuguese (brazil)", "portuguese-br", "pob"):
        return "pb"
    if len(name) == 2:
        return name.lower()
    code = xbmc.convertLanguage(name, xbmc.ISO_639_1) or ""
    return code.lower()


def lang_name(code):
    if code == "pb":
        return "Portuguese (Brazil)"
    return xbmc.convertLanguage(code, xbmc.ENGLISH_NAME) or code


def os_code(code):
    return SPECIAL.get(code, code)


def from_os_code(code):
    code = (code or "").lower()
    return "pb" if code in ("pt-br", "pb") else code.split("-")[0]


# ----------------------------------------------------------------------------- what is playing
def rpc(method, params=None):
    req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return json.loads(xbmc.executeJSONRPC(json.dumps(req))).get("result", {})


def info(label):
    return xbmc.getInfoLabel(label) or ""


def current_video():
    video = {
        "title": info("VideoPlayer.OriginalTitle") or info("VideoPlayer.Title"),
        "year": info("VideoPlayer.Year"),
        "show": info("VideoPlayer.TVShowTitle"),
        "season": info("VideoPlayer.Season"),
        "episode": info("VideoPlayer.Episode"),
        "imdb": "", "tmdb": "", "show_imdb": "", "show_tmdb": "",
        "file": "",
    }
    player = xbmc.Player()
    try:
        video["file"] = player.getPlayingFile() if player.isPlayingVideo() else ""
        tag = player.getVideoInfoTag()
        video["imdb"] = tag.getUniqueID("imdb") or tag.getIMDBNumber() or ""
        video["tmdb"] = tag.getUniqueID("tmdb") or ""
    except Exception:  # noqa: BLE001 - not playing / old Kodi
        pass
    video["imdb"] = video["imdb"] or info("VideoPlayer.IMDBNumber")
    if video["show"]:
        # the series' own ids: from the Kodi library when it is a library episode, else what the player was given
        dbid = info("VideoPlayer.DBID")
        if dbid.isdigit() and int(dbid) > 0:
            try:
                ep = rpc("VideoLibrary.GetEpisodeDetails", {"episodeid": int(dbid), "properties": ["tvshowid"]}).get("episodedetails") or {}
                show = rpc("VideoLibrary.GetTVShowDetails", {"tvshowid": ep.get("tvshowid", -1), "properties": ["uniqueid"]}).get("tvshowdetails") or {}
                ids = show.get("uniqueid") or {}
                video["show_imdb"], video["show_tmdb"] = ids.get("imdb", ""), str(ids.get("tmdb", ""))
            except Exception:  # noqa: BLE001
                pass
        for key, prop in (("show_imdb", "tvshow.imdb_id"), ("show_tmdb", "tvshow.tmdb_id")):
            if not video[key]:
                video[key] = info(f"VideoPlayer.Property({prop})") or info(f"Window(home).Property(lucent.player.{prop})")
    for key in ("imdb", "show_imdb"):
        if video[key] and not str(video[key]).startswith("tt"):
            video[key] = ""
    video["release"] = release_name(video["file"])
    return video


def release_name(path):
    """The file name without folders, query and extension: what release groups put in their subtitle names."""
    if not path:
        return ""
    name = urllib.parse.unquote(path.split("|")[0].split("?")[0].rstrip("/").rsplit("/", 1)[-1])
    return re.sub(r"\.(mkv|mp4|avi|m4v|ts|m2ts|wmv|mov|strm)$", "", name, flags=re.I)


TOKEN = re.compile(r"[a-z0-9]+")
NOISE = {"mkv", "mp4", "avi", "srt", "nl", "en", "eng", "dut", "dutch", "english", "sub", "subs", "subtitle", "the"}


def tokens(text):
    return [t for t in TOKEN.findall((text or "").lower()) if t not in NOISE]


def release_match(release, video):
    """0..1: how well a subtitle's release name fits the playing file (quality, source, group)."""
    mine = set(tokens(video.get("release")))
    if not mine or not release:
        return 0.0
    theirs = set(tokens(release))
    if not theirs:
        return 0.0
    keys = {"2160p", "1080p", "720p", "480p", "web", "webrip", "webdl", "dl", "bluray", "brrip", "bdrip", "hdtv", "remux",
            "x264", "x265", "h264", "h265", "hevc", "amzn", "nf", "dsnp", "hmax", "atvp", "hulu", "proper", "repack"}
    group = tokens(video.get("release"))[-1:]
    score = len(mine & theirs) / max(len(mine), 1)
    important = (mine & keys)
    if important:
        score = 0.5 * score + 0.5 * len(important & theirs) / len(important)
    if group and group[0] in theirs:
        score = min(1.0, score + 0.25)
    return score


# ----------------------------------------------------------------------------- OpenSubtitles hash
def os_hash(path, timeout=4.0):
    """OpenSubtitles' movie hash (size + first and last 64 KB), also over http when the stream allows seeking."""
    if not path or path.startswith(("plugin://", "pvr://", "rtmp")):
        return "", 0
    out = {}

    def work():
        f = xbmcvfs.File(path)
        try:
            size = f.size()
            if size < 131072:
                return
            value = size
            for start in (0, size - 65536):
                if start:
                    f.seek(start, 0)
                chunk = bytes(f.readBytes(65536))
                if len(chunk) < 65536:
                    return
                for (word,) in struct.iter_unpack("<Q", chunk):
                    value = (value + word) & 0xFFFFFFFFFFFFFFFF
            out["hash"], out["size"] = f"{value:016x}", size
        finally:
            f.close()

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(timeout)
    return out.get("hash", ""), out.get("size", 0)


# ----------------------------------------------------------------------------- OpenSubtitles.com
TOKEN_PATH = os.path.join(DATA, "os_token.json")


def os_headers(auth=False):
    head = {"Api-Key": setting("os_key").strip()}
    if auth:
        token = os_login()
        if token:
            head["Authorization"] = f"Bearer {token['token']}"
    return head


def os_login(force=False):
    """A login token (kept 20 hours) so downloads count against your own account instead of the anonymous limit."""
    user, password = setting("os_user").strip(), setting("os_pass")
    if not user or not password:
        return None
    if not force:
        try:
            with open(TOKEN_PATH, encoding="utf-8") as fh:
                saved = json.load(fh)
            if saved.get("user") == user and time.time() - saved.get("at", 0) < 20 * 3600:
                return saved
        except Exception:  # noqa: BLE001
            pass
    try:
        answer = get_json(f"{OS_API}/login", data={"username": user, "password": password}, headers=os_headers(), timeout=10)
    except Exception as error:  # noqa: BLE001
        log(f"opensubtitles login: {error}")
        return None
    if not answer.get("token"):
        return None
    saved = {"user": user, "at": time.time(), "token": answer["token"], "base": answer.get("base_url") or ""}
    os.makedirs(DATA, exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as fh:
        json.dump(saved, fh)
    return saved


def os_search(video, langs, timeout):
    if not on("os_on") or not setting("os_key").strip():
        return []
    params = {"languages": ",".join(sorted({os_code(c) for c in langs}))}
    if video.get("query"):
        params["query"] = video["query"]
    elif video["show"]:
        params.update({"season_number": video["season"], "episode_number": video["episode"]})
        if video["show_imdb"]:
            params["parent_imdb_id"] = video["show_imdb"][2:].lstrip("0")
        elif video["show_tmdb"]:
            params["parent_tmdb_id"] = video["show_tmdb"]
        elif video["imdb"]:
            params = {"languages": params["languages"], "imdb_id": video["imdb"][2:].lstrip("0")}
        else:
            params["query"] = video["show"]
            params["type"] = "episode"
    elif video["imdb"]:
        params["imdb_id"] = video["imdb"][2:].lstrip("0")
    elif video["tmdb"]:
        params["tmdb_id"] = video["tmdb"]
    else:
        params["query"] = video["title"]
        if video["year"]:
            params["year"] = video["year"]
    if video.get("hash"):
        params["moviehash"] = video["hash"]
    # OpenSubtitles wants the parameters sorted and lower case (otherwise it answers with a redirect)
    query = urllib.parse.urlencode(sorted((k, str(v).lower()) for k, v in params.items() if v not in (None, "")), safe=",")
    data = get_json(f"{OS_API}/subtitles?{query}", headers=os_headers(), timeout=timeout)
    out = []
    for row in data.get("data") or []:
        a = row.get("attributes") or {}
        files = a.get("files") or []
        if not files or a.get("machine_translated"):
            continue
        downloads = int(a.get("download_count") or 0)
        score = 1 + min(2, downloads // 2000) + (1 if a.get("from_trusted") else 0) + (1 if float(a.get("ratings") or 0) >= 7 else 0)
        sync = bool(a.get("moviehash_match"))
        out.append({"src": "os", "id": str(files[0].get("file_id")), "lang": from_os_code(a.get("language")),
                    "release": a.get("release") or files[0].get("file_name") or "", "sync": sync,
                    "hi": bool(a.get("hearing_impaired")), "score": min(5, score), "ai": bool(a.get("ai_translated")), "hash": sync,
                    "downloads": downloads})
    return out


def os_download(item):
    head = os_headers(auth=True)
    base = OS_API
    token = os_login()
    if token and token.get("base"):
        base = f"https://{token['base']}/api/v1" if not token["base"].startswith("http") else token["base"].rstrip("/") + "/api/v1"
    try:
        answer = get_json(f"{base}/download", data={"file_id": int(item["id"])}, headers=head, timeout=15)
    except urllib.error.HTTPError as error:
        if error.code == 401 and token:
            os_login(force=True)
            answer = get_json(f"{base}/download", data={"file_id": int(item["id"])}, headers=os_headers(auth=True), timeout=15)
        elif error.code in (406, 429):
            raise RuntimeError("limit") from error
        else:
            raise
    link = answer.get("link")
    if not link:
        raise RuntimeError(answer.get("message") or "no link")
    log(f"opensubtitles: {answer.get('remaining', '?')} downloads left today")
    return request(link, headers={"Accept": "*/*"}, timeout=20), answer.get("file_name") or "subtitle.srt"


# ----------------------------------------------------------------------------- SubDL
def subdl_search(video, langs, timeout):
    key = setting("subdl_key").strip()
    if not on("subdl_on") or not key:
        return []
    params = {"api_key": key, "languages": ",".join(sorted({c.upper() if c != "pb" else "BR_PT" for c in langs})),
              "subs_per_page": "30"}
    if video.get("query"):
        params["film_name"] = video["query"]
    elif video["show"]:
        params.update({"type": "tv", "season_number": video["season"], "episode_number": video["episode"]})
        if video["show_imdb"]:
            params["imdb_id"] = video["show_imdb"]
        elif video["show_tmdb"]:
            params["tmdb_id"] = video["show_tmdb"]
        else:
            params["film_name"] = video["show"]
    else:
        params["type"] = "movie"
        if video["imdb"]:
            params["imdb_id"] = video["imdb"]
        elif video["tmdb"]:
            params["tmdb_id"] = video["tmdb"]
        else:
            params["film_name"] = video["title"]
            if video["year"]:
                params["year"] = video["year"]
    data = get_json(f"{SUBDL_API}?{urllib.parse.urlencode(params)}", timeout=timeout)
    if not data.get("status", True) and data.get("error"):
        log(f"subdl: {data.get('error')}")
    out = []
    for row in data.get("subtitles") or []:
        url = row.get("url") or ""
        if not url:
            continue
        lang = (row.get("lang") or row.get("language") or "").lower()
        lang = {"dutch": "nl", "english": "en", "br_pt": "pb", "brazillian portuguese": "pb"}.get(lang, lang[:2])
        if video["show"] and row.get("episode") not in (None, "", 0) and str(row.get("episode")) != str(video["episode"]):
            continue
        releases = row.get("releases") or []
        release = row.get("release_name") or (releases[0] if releases else "") or row.get("name") or ""
        out.append({"src": "subdl", "id": url, "lang": lang, "release": release, "sync": False,
                    "hi": bool(row.get("hi")), "score": 2, "season_pack": bool(row.get("full_season")),
                    "others": releases})
    return out


def subdl_download(item):
    return request(SUBDL_DL + item["id"], headers={"Accept": "*/*"}, timeout=20), "subtitle.zip"


# ----------------------------------------------------------------------------- Podnapisi
def podnapisi_search(video, langs, timeout):
    if not on("podnapisi_on"):
        return []
    out = []
    for lang in langs:
        params = {"language": "pt-br" if lang == "pb" else lang}
        if video.get("query"):
            params["keywords"] = video["query"]
        elif video["show"]:
            params.update({"keywords": video["show"], "movie_type": "tv-series", "seasons": video["season"],
                           "episodes": video["episode"]})
        else:
            params.update({"keywords": video["title"], "movie_type": "movie"})
            if video["year"]:
                params["year"] = video["year"]
        data = get_json(f"{PODNAPISI}/subtitles/search/advanced?{urllib.parse.urlencode(params)}", timeout=timeout)
        for row in data.get("data") or []:
            link = row.get("download") or (f"/subtitles/{row['id']}/download" if row.get("id") else "")
            if not link:
                continue
            releases = row.get("custom_releases") or row.get("releases") or []
            flags = row.get("flags") or []
            downloads = int((row.get("stats") or {}).get("downloads") or 0)
            out.append({"src": "podnapisi", "id": link, "lang": (row.get("language") or lang).lower()[:2] if lang != "pb" else "pb",
                        "release": releases[0] if releases else (row.get("title") or ""), "sync": False,
                        "hi": "hearing_impaired" in flags, "score": 1 + min(3, downloads // 1000), "others": releases})
    return out


def podnapisi_download(item):
    return request(PODNAPISI + item["id"], headers={"Accept": "*/*"}, timeout=20), "subtitle.zip"


SOURCES = {"os": (os_search, os_download, "OpenSubtitles"), "subdl": (subdl_search, subdl_download, "SubDL"),
           "podnapisi": (podnapisi_search, podnapisi_download, "Podnapisi")}


# ----------------------------------------------------------------------------- search all
def cache_path():
    return os.path.join(DATA, "search_cache.json")


def search(video, langs):
    """All sources at once; whatever is not back within the time limit is left out. Results ranked."""
    key = json.dumps([video.get("query") or video.get("release") or video.get("title"), video["show"], video["season"],
                      video["episode"], video["imdb"], sorted(langs)])
    try:
        with open(cache_path(), encoding="utf-8") as fh:
            saved = json.load(fh)
        if saved.get("key") == key and time.time() - saved.get("at", 0) < CACHE_TTL and saved.get("rows"):
            log(f"{len(saved['rows'])} subtitles from the last search")
            return saved["rows"]
    except Exception:  # noqa: BLE001
        pass
    timeout = max(4, int(setting("timeout") or 10))
    if not video.get("query"):
        video["hash"], video["size"] = os_hash(video.get("file"))
    results, threads = {}, []

    def run(name, fn):
        started = time.time()
        try:
            results[name] = fn(video, langs, timeout)
            log(f"{name}: {len(results[name])} in {time.time() - started:.1f}s")
        except Exception as error:  # noqa: BLE001
            log(f"{name}: {error}")
            results[name] = []

    for name, (fn, _dl, _label) in SOURCES.items():
        thread = threading.Thread(target=run, args=(name, fn), daemon=True)
        thread.start()
        threads.append(thread)
    deadline = time.time() + timeout + 1
    for thread in threads:
        thread.join(max(0, deadline - time.time()))
    rows = [r for name in SOURCES for r in results.get(name, [])]
    for r in rows:
        match = max([release_match(r["release"], video)] + [release_match(o, video) for o in (r.get("others") or [])[:10]])
        r["match"] = round(match, 2)
        if match >= 0.85:
            r["sync"] = True
    seen, unique = set(), []
    for r in rows:
        k = (r["lang"], re.sub(r"\W+", "", r["release"].lower()), r["src"])
        if k not in seen:
            seen.add(k)
            unique.append(r)
    order = {c: n for n, c in enumerate(langs)}
    hi_last = on("hi_last")
    unique.sort(key=lambda r: (order.get(r["lang"], 99), not r["sync"], not r.get("hash"), -r["match"], r.get("ai", False),
                               r["hi"] if hi_last else False, -r["score"], -r.get("downloads", 0)))
    complete = all(not thread.is_alive() for thread in threads)
    try:
        if not complete:                             # a source was too slow: ask everything again next time
            raise RuntimeError("not complete")
        os.makedirs(DATA, exist_ok=True)
        with open(cache_path(), "w", encoding="utf-8") as fh:
            json.dump({"key": key, "at": time.time(), "rows": unique}, fh)
    except Exception:  # noqa: BLE001
        pass
    return unique


# ----------------------------------------------------------------------------- download -> a local UTF-8 file
def to_utf8(raw):
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    for enc in ("cp1252", "iso-8859-15", "cp1250", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def pick_from_zip(raw, video):
    """The subtitle file in an archive; for a season pack the one of this episode."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(SUB_EXT) and not n.startswith("__MACOSX")]
        if not names:
            raise RuntimeError("no subtitle in the archive")
        best = names[0]
        if video.get("show") and len(names) > 1:
            s, e = int(video.get("season") or 0), int(video.get("episode") or 0)
            pattern = re.compile(rf"(?:s0*{s}[\s._-]*e0*{e}(?!\d)|\b0*{s}x0*{e}(?!\d))", re.I)
            hits = [n for n in names if pattern.search(n)]
            if hits:
                best = hits[0]
        elif len(names) > 1:
            best = max(names, key=lambda n: release_match(n, video))
        return archive.read(best), best.rsplit("/", 1)[-1]


def download(item, video):
    _search, fetch, _label = SOURCES[item["src"]]
    raw, name = fetch(item)
    if raw[:2] == b"PK":
        raw, name = pick_from_zip(raw, video)
    ext = os.path.splitext(name)[1].lower()
    if ext not in SUB_EXT:
        ext = ".srt"
    text = to_utf8(raw)
    os.makedirs(TEMP, exist_ok=True)
    for old in os.listdir(TEMP):                     # keep the folder small
        try:
            if time.time() - os.path.getmtime(os.path.join(TEMP, old)) > 3 * 86400:
                os.remove(os.path.join(TEMP, old))
        except OSError:
            pass
    safe = re.sub(r"[^\w.-]+", ".", (video.get("release") or video.get("title") or "subtitle"))[:80].strip(".") or "subtitle"
    path = os.path.join(TEMP, f"{safe}.{item['lang'] or 'xx'}{ext}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path
