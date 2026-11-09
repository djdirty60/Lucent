"""Lucent: scores from OMDb (IMDb, Rotten Tomatoes, Metacritic) and MDBList (also Letterboxd, the Rotten Tomatoes
audience score and the Metacritic user score) on the info page and in the lists, each with your own free key.
MDBList: the endpoint is https://api.mdblist.com/imdb/<movie|show>/<tt...>?apikey=..., its 'ratings' list gives per
source 'value' (own scale), 'score' (0-100) and 'votes'.

    RunScript(special://skin/scripts/omdb.py,settings)   Settings > Lucent > Scores (OMDb): key, test, which scores you see

info.py calls load(item) when the info page opens. The answer per title is kept for a week (omdb.json), so the free key
(1000 requests a day) is plenty. Fills Window(home).Property(lucent.omdb.*); DialogVideoInfo.xml shows them.
Which scores show: Skin.HasSetting(lucent.rate.hide.<imdb|rt|mc|tmdb|trakt>) hides one, lucent.rate.votes adds the
number of IMDb votes.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import xbmc
import xbmcgui
import xbmcvfs

HOME = xbmcgui.Window(10000)
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
DIR = "special://profile/addon_data/skin.lucent/"
KEYFILE = DIR + "omdb.key"
MDB_KEYFILE = DIR + "mdblist.key"
MDB_CACHE = DIR + "mdblist_cache.json"
CACHE = DIR + "omdb_cache.json"         # *_cache.json stays out of the backup
WEEK, DAY = 7 * 86400, 86400
PROPS = ("imdb", "votes", "rt", "rtc", "mc", "mcc", "lb", "lb.c", "rta", "rtac", "mcu", "mcu.c", "for")
GREEN, YELLOW, RED = "FF3DD68C", "FFFFCC33", "FFE5484D"
SCORES = [("imdb", "IMDb"), ("rt", "Rotten Tomatoes"), ("mc", "Metacritic"), ("tmdb", "TMDB"), ("trakt", "Trakt"),
          ("lb", "Letterboxd (MDBList)"), ("rta", "Rotten Tomatoes audience (MDBList)"), ("mcu", "Metacritic users (MDBList)")]


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] omdb: {text}", xbmc.LOGINFO)


def key():
    try:
        with xbmcvfs.File(KEYFILE) as fh:
            return (fh.read() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def _cache():
    try:
        with open(xbmcvfs.translatePath(CACHE), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save(cache):
    try:
        os.makedirs(xbmcvfs.translatePath(DIR), exist_ok=True)
        now = time.time()
        cache = {k: v for k, v in cache.items() if now - v.get("t", 0) < WEEK}     # keep the file small
        with open(xbmcvfs.translatePath(CACHE), "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
    except OSError as error:
        log(f"cache: {error}")


def ask(imdb_id, api_key):
    """OMDb's answer for one IMDb number (dict), or raises."""
    url = "https://www.omdbapi.com/?" + urllib.parse.urlencode({"i": imdb_id, "apikey": api_key})
    req = urllib.request.Request(url, headers={"User-Agent": "Kodi-skin.lucent"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch(imdb_id):
    """{'imdb', 'votes', 'rt', 'mc'} for an IMDb number (cached for a week; a title OMDb does not know for a day)."""
    api_key = key()
    if not api_key or not imdb_id.startswith("tt"):
        return {}
    cache = _cache()
    hit = cache.get(imdb_id)
    if hit and time.time() - hit.get("t", 0) < (WEEK if hit.get("d") else DAY):
        return hit.get("d") or {}
    try:
        data = ask(imdb_id, api_key)
    except Exception as error:  # noqa: BLE001 - no network: try again next time
        log(f"{imdb_id}: {type(error).__name__}")
        return (hit or {}).get("d") or {}
    if data.get("Response") != "True":
        log(f"{imdb_id}: {data.get('Error', 'no answer')}")
        if "limit" in str(data.get("Error", "")).lower() or "invalid api key" in str(data.get("Error", "")).lower():
            return (hit or {}).get("d") or {}          # do not remember a key or limit problem as 'no scores'
        cache[imdb_id] = {"t": time.time(), "d": {}}
        _save(cache)
        return {}
    out = {}
    if data.get("imdbRating") not in (None, "", "N/A"):
        out["imdb"] = data["imdbRating"]
    if data.get("imdbVotes") not in (None, "", "N/A"):
        out["votes"] = data["imdbVotes"].replace(",", "")
    for r in data.get("Ratings") or []:
        if r.get("Source") == "Rotten Tomatoes":
            out["rt"] = r.get("Value", "")
    if data.get("Metascore") not in (None, "", "N/A"):
        out["mc"] = data["Metascore"]
    cache[imdb_id] = {"t": time.time(), "d": out}
    _save(cache)
    return out


def mdb_key():
    try:
        with xbmcvfs.File(MDB_KEYFILE) as fh:
            return (fh.read() or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def mdb_ask(imdb_id, kind, api_key):
    url = f"https://api.mdblist.com/imdb/{'show' if kind == 'tvshow' else 'movie'}/{imdb_id}?" + urllib.parse.urlencode({"apikey": api_key})
    req = urllib.request.Request(url, headers={"User-Agent": "Kodi-skin.lucent"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def mdb_parse(data):
    """MDBList's answer -> {'imdb', 'votes', 'rt', 'mc', 'lb', 'rta', 'mcu'} (only what it knows)."""
    out = {}
    for r in data.get("ratings") or []:
        src = str(r.get("source") or "").lower()
        value, score = _num(r.get("value")), _num(r.get("score"))
        if src == "imdb" and value:
            out["imdb"] = f"{value:.1f}"
            if r.get("votes"):
                out["votes"] = str(r["votes"])
        elif src in ("tomatoes", "tomatometer") and score:
            out["rt"] = f"{round(score)}%"
        elif src in ("popcorn", "tomatoesaudience", "audience") and score:
            out["rta"] = f"{round(score)}%"
        elif src == "metacritic" and score:
            out["mc"] = str(round(score))
        elif src == "metacriticuser" and value:
            out["mcu"] = f"{value:.1f}"
        elif src == "letterboxd" and value:
            out["lb"] = f"{value:.1f}"
    return out


def mdb_fetch(imdb_id, kind="movie"):
    api_key = mdb_key()
    if not api_key or not imdb_id.startswith("tt"):
        return {}
    try:
        with open(xbmcvfs.translatePath(MDB_CACHE), encoding="utf-8") as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        cache = {}
    hit = cache.get(imdb_id)
    if hit and time.time() - hit.get("t", 0) < (WEEK if hit.get("d") else DAY):
        return hit.get("d") or {}
    try:
        data = mdb_ask(imdb_id, kind, api_key)
    except Exception as error:  # noqa: BLE001 - no network / key problem: try again next time
        log(f"mdblist {imdb_id}: {type(error).__name__}")
        return (hit or {}).get("d") or {}
    out = mdb_parse(data if isinstance(data, dict) else {})
    cache[imdb_id] = {"t": time.time(), "d": out}
    try:
        now = time.time()
        cache = {k: v for k, v in cache.items() if now - v.get("t", 0) < WEEK}
        with open(xbmcvfs.translatePath(MDB_CACHE), "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
    except OSError as error:
        log(f"mdblist cache: {error}")
    return out


def all_scores(imdb_id, kind="movie"):
    """OMDb (when there is a key) plus MDBList (when there is a key): MDBList fills what OMDb lacks."""
    d = dict(fetch(imdb_id)) if imdb_id else {}
    m = mdb_fetch(imdb_id, kind) if imdb_id else {}
    for k, v in m.items():
        if v and not d.get(k):
            d[k] = v
    return d


def any_key():
    return key() or mdb_key()


def _dot(k, v):
    """Dot colour for the MDBList scores: Metacritic users (0-10) and Letterboxd (0-5), green / yellow / red."""
    n = _num(v) or 0
    top, mid = (6.1, 4.0) if k == "mcu" else (3.5, 2.5)
    return GREEN if n >= top else YELLOW if n >= mid else RED


def _fresh(pct):
    return GREEN if int(str(pct).rstrip("%") or 0) >= 60 else RED


def list_text(d):
    """The short line for list views: 'RT 87%  MC 81  LB 3.9', only the scores you chose."""
    shown = lambda k: not xbmc.getCondVisibility(f"Skin.HasSetting(lucent.rate.hide.{k})")   # noqa: E731
    parts = [(k, label) for k, label in (("rt", "RT"), ("rta", "RT audience" if not NL else "RT publiek"), ("mc", "MC"),
                                         ("mcu", "MC users" if not NL else "MC gebruikers"), ("lb", "LB")) if d.get(k) and shown(k)]
    return "   ".join(f"{label} {d[k]}" for k, label in parts)


def short_votes(votes):
    try:
        n = int(votes)
    except (TypeError, ValueError):
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1000:
        return f"{round(n / 1000)}k"
    return str(n)


def clear():
    for p in PROPS:
        HOME.clearProperty("lucent.omdb." + p)


def imdb_of(item):
    """The IMDb number of the page's film or series (from the item, else from TMDb)."""
    if item.imdb.startswith("tt"):
        return item.imdb
    if not item.tmdb.isdigit():
        return ""
    try:
        import info
        kind = "tv" if item.dbtype == "tvshow" else "movie"
        return (info.tmdb(f"{kind}/{item.tmdb}/external_ids") or {}).get("imdb_id") or ""
    except Exception as error:  # noqa: BLE001
        log(f"TMDb external ids: {error}")
        return ""


def load(item):
    """Called by info.py when the info page opens."""
    clear()
    if not any_key() or item.dbtype not in ("movie", "tvshow"):
        return
    imdb_id = imdb_of(item)
    d = all_scores(imdb_id, item.dbtype) if imdb_id else {}
    if not d:
        return
    if HOME.getProperty("nuvio.info.key") not in ("", item.key):
        return                                          # another page opened meanwhile
    HOME.setProperty("lucent.omdb.imdb", d.get("imdb", ""))
    HOME.setProperty("lucent.omdb.votes", short_votes(d.get("votes")))
    rt = d.get("rt", "")
    if rt:
        HOME.setProperty("lucent.omdb.rt", rt)
        HOME.setProperty("lucent.omdb.rtc", GREEN if int(rt.rstrip("%") or 0) >= 60 else RED)   # fresh / rotten
    mc = d.get("mc", "")
    if mc:
        n = int(mc)
        HOME.setProperty("lucent.omdb.mc", mc)
        HOME.setProperty("lucent.omdb.mcc", GREEN if n >= 61 else YELLOW if n >= 40 else RED)  # Metacritic's own colours
    if d.get("rta"):
        HOME.setProperty("lucent.omdb.rta", d["rta"])
        HOME.setProperty("lucent.omdb.rtac", _fresh(d["rta"]))
    for k in ("lb", "mcu"):
        if d.get(k):
            HOME.setProperty("lucent.omdb." + k, d[k])
            HOME.setProperty(f"lucent.omdb.{k}.c", _dot(k, d[k]))
    HOME.setProperty("lucent.omdb.for", item.key)


# ----------------------------------------------------------------------------- scores in the lists
LIST = {"id": "", "since": 0.0, "done": "", "busy": False, "key": "", "keyt": 0.0}
LPROPS = ("rt", "rtc", "mc", "mcc", "imdb", "lb", "lb.c", "rta", "rtac", "mcu", "mcu.c", "text")
TMDB_IMDB = {}                                     # tmdb id -> imdb id, for this session


def _key_cached():
    if time.time() - LIST["keyt"] > 30:
        LIST["key"], LIST["keyt"] = any_key(), time.time()
    return LIST["key"]


def _lclear():
    if HOME.getProperty("lucent.omdbl.for"):
        for p in LPROPS + ("for",):
            HOME.clearProperty("lucent.omdbl." + p)


def _from_library(kind, dbid):
    """IMDb number (and TMDb id) of a library film or series, via JSON-RPC."""
    method = "VideoLibrary.GetTVShowDetails" if kind == "tvshow" else "VideoLibrary.GetMovieDetails"
    field = "tvshowid" if kind == "tvshow" else "movieid"
    req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": {field: int(dbid), "properties": ["uniqueid", "imdbnumber"]}}
    res = json.loads(xbmc.executeJSONRPC(json.dumps(req))).get("result") or {}
    details = res.get("tvshowdetails" if kind == "tvshow" else "moviedetails") or {}
    ids = details.get("uniqueid") or {}
    imdb = ids.get("imdb") or details.get("imdbnumber") or ""
    return (imdb if imdb.startswith("tt") else ""), str(ids.get("tmdb") or "")


def _fill(ident, imdb_id, tmdb_id, kind, dbid=""):
    try:
        if not imdb_id and not tmdb_id and dbid:
            got = TMDB_IMDB.get(f"db:{kind}:{dbid}")
            if got is None:
                got = _from_library(kind, dbid)
                if got[0] or got[1]:                    # remember only a real answer: the library may get the ids later
                    TMDB_IMDB[f"db:{kind}:{dbid}"] = got
            imdb_id, tmdb_id = got
            tmdb_id = tmdb_id if tmdb_id.isdigit() else ""
        if not imdb_id and tmdb_id:
            imdb_id = TMDB_IMDB.get(f"{kind}:{tmdb_id}")
            if imdb_id is None:
                class _I:                           # what imdb_of() reads
                    imdb, tmdb, dbtype = "", tmdb_id, kind
                imdb_id = imdb_of(_I())
                if imdb_id:
                    TMDB_IMDB[f"{kind}:{tmdb_id}"] = imdb_id
        d = all_scores(imdb_id, kind) if imdb_id else {}
        if LIST["id"] != ident:
            return                                  # the cursor moved on meanwhile
        for p in LPROPS:
            HOME.clearProperty("lucent.omdbl." + p)
        rt, mc = d.get("rt", ""), d.get("mc", "")
        if rt:
            HOME.setProperty("lucent.omdbl.rt", rt)
            HOME.setProperty("lucent.omdbl.rtc", GREEN if int(rt.rstrip("%") or 0) >= 60 else RED)
        if mc:
            n = int(mc)
            HOME.setProperty("lucent.omdbl.mc", mc)
            HOME.setProperty("lucent.omdbl.mcc", GREEN if n >= 61 else YELLOW if n >= 40 else RED)
        if d.get("imdb"):
            HOME.setProperty("lucent.omdbl.imdb", d["imdb"])
        if d.get("rta"):
            HOME.setProperty("lucent.omdbl.rta", d["rta"])
            HOME.setProperty("lucent.omdbl.rtac", _fresh(d["rta"]))
        for k in ("lb", "mcu"):
            if d.get(k):
                HOME.setProperty("lucent.omdbl." + k, d[k])
                HOME.setProperty(f"lucent.omdbl.{k}.c", _dot(k, d[k]))
        HOME.setProperty("lucent.omdbl.text", list_text(d))
        HOME.setProperty("lucent.omdbl.for", ident)
        LIST["done"] = ident
    except Exception as error:  # noqa: BLE001
        log(f"list: {error}")
    finally:
        LIST["busy"] = False


def list_tick():
    """Called by the helper several times a second: the scores of the film or series under the cursor in a video list,
    half a second after the cursor stopped there (fetched in the background, cached a week)."""
    if (not _key_cached() or xbmc.getCondVisibility("Skin.HasSetting(lucent.omdb.lists.off)")
            or not xbmc.getCondVisibility("Window.IsActive(videos) + [Container.Content(movies) | Container.Content(tvshows)]")):
        LIST["id"] = LIST["done"] = ""
        _lclear()
        return
    label = xbmc.getInfoLabel
    imdb_id = label("ListItem.UniqueID(imdb)") or label("ListItem.IMDBNumber") or label("ListItem.Property(imdb_id)")
    imdb_id = imdb_id if imdb_id.startswith("tt") else ""
    tmdb_id = label("ListItem.UniqueID(tmdb)") or label("ListItem.Property(tmdb_id)")
    tmdb_id = tmdb_id if tmdb_id.isdigit() else ""
    kind = "tvshow" if label("ListItem.DBType") == "tvshow" or xbmc.getCondVisibility("Container.Content(tvshows)") else "movie"
    dbid = label("ListItem.DBID")
    dbid = dbid if dbid.isdigit() and label("ListItem.DBType") in ("movie", "tvshow") else ""
    # Kodi gives the IMDb number of a library title only on its info page: in a list we ask the library by DBID
    ident = imdb_id or (f"tmdb:{kind}:{tmdb_id}" if tmdb_id else "") or (f"db:{kind}:{dbid}" if dbid else "")
    now = time.time()
    if ident != LIST["id"]:
        LIST["id"], LIST["since"], LIST["done"] = ident, now, ""     # back on a title seen before: fill it again
        _lclear()
        return
    if not ident or LIST["done"] == ident or LIST["busy"] or now - LIST["since"] < 0.5:
        return
    LIST["busy"] = True
    import threading
    threading.Thread(target=_fill, args=(ident, imdb_id, tmdb_id, kind, dbid), daemon=True).start()


# ----------------------------------------------------------------------------- settings
def state_label():
    k = key()
    return (t("key ", "sleutel ") + "••••" + k[-4:]) if k else t("no key yet", "nog geen sleutel")


def set_key():
    text = t("OMDb API key (free at omdbapi.com > API Key)", "OMDb API-sleutel (gratis op omdbapi.com > API Key)")
    new = xbmcgui.Dialog().input(text, defaultt=key())
    if new is None:
        return
    os.makedirs(xbmcvfs.translatePath(DIR), exist_ok=True)
    with open(xbmcvfs.translatePath(KEYFILE), "w", encoding="utf-8") as fh:
        fh.write(new.strip())
    if new.strip():
        test()


def test():
    k = key()
    if not k:
        xbmcgui.Dialog().ok("OMDb", t("Fill in your key first.", "Vul eerst je sleutel in."))
        return
    try:
        data = ask("tt0185937", k)                    # The Blair Witch Project
        ok = data.get("Response") == "True"
        why = data.get("Error", "")
    except Exception as error:  # noqa: BLE001
        ok, why = False, type(error).__name__
    if ok:
        xbmcgui.Dialog().ok("OMDb", t("The key works.", "De sleutel werkt."))
    else:
        xbmcgui.Dialog().ok("OMDb", t(f"The key does not work yet: {why}\n\nA new key must first be activated with the "
                                      "link OMDb e-mailed you.",
                                      f"De sleutel werkt nog niet: {why}\n\nEen nieuwe sleutel moet je eerst activeren met "
                                      "de link die OMDb je mailde."))


def mdb_state_label():
    k = mdb_key()
    return (t("key ", "sleutel ") + "••••" + k[-4:]) if k else t("no key yet (optional)", "nog geen sleutel (mag)")


def set_mdb_key():
    text = t("MDBList API key (free: mdblist.com > Preferences > API Access)", "MDBList API-sleutel (gratis: mdblist.com > Preferences > API Access)")
    new = xbmcgui.Dialog().input(text, defaultt=mdb_key())
    if new is None:
        return
    os.makedirs(xbmcvfs.translatePath(DIR), exist_ok=True)
    with open(xbmcvfs.translatePath(MDB_KEYFILE), "w", encoding="utf-8") as fh:
        fh.write(new.strip())
    if new.strip():
        test_mdb()


def test_mdb():
    k = mdb_key()
    if not k:
        xbmcgui.Dialog().ok("MDBList", t("Fill in your key first.", "Vul eerst je sleutel in."))
        return
    try:
        got = mdb_parse(mdb_ask("tt0185937", "movie", k))      # The Blair Witch Project
        ok, why = bool(got), "" if got else t("no scores in the answer", "geen scores in het antwoord")
    except Exception as error:  # noqa: BLE001
        ok, why = False, getattr(error, "code", "") or type(error).__name__
    if ok:
        names = {"imdb": "IMDb", "rt": "Rotten Tomatoes", "rta": t("RT audience", "RT publiek"), "mc": "Metacritic",
                 "mcu": t("Metacritic users", "Metacritic gebruikers"), "lb": "Letterboxd"}
        xbmcgui.Dialog().ok("MDBList", t("The key works. Scores it gave: ", "De sleutel werkt. Scores die het gaf: ")
                            + ", ".join(names[x] for x in names if x in got))
    else:
        xbmcgui.Dialog().ok("MDBList", t(f"The key does not work: {why}", f"De sleutel werkt niet: {why}"))


def toggle_lists():
    xbmc.executebuiltin("Skin.ToggleSetting(lucent.omdb.lists.off)")


def lists_label():
    return t("off", "uit") if xbmc.getCondVisibility("Skin.HasSetting(lucent.omdb.lists.off)") else t("on", "aan")


def choose():
    labels = [name for _k, name in SCORES] + [t("Number of IMDb votes", "Aantal IMDb-stemmen")]
    pre = [i for i, (k, _n) in enumerate(SCORES) if not xbmc.getCondVisibility(f"Skin.HasSetting(lucent.rate.hide.{k})")]
    if xbmc.getCondVisibility("Skin.HasSetting(lucent.rate.votes)"):
        pre.append(len(SCORES))
    picked = xbmcgui.Dialog().multiselect(t("Scores on the info page", "Scores op de infopagina"), labels, preselect=pre)
    if picked is None:
        return
    for i, (k, _n) in enumerate(SCORES):
        xbmc.executebuiltin(f"Skin.Reset(lucent.rate.hide.{k})" if i in picked else f"Skin.SetBool(lucent.rate.hide.{k})")
    xbmc.executebuiltin("Skin.SetBool(lucent.rate.votes)" if len(SCORES) in picked else "Skin.Reset(lucent.rate.votes)")


def chosen_label():
    names = [n for k, n in SCORES if not xbmc.getCondVisibility(f"Skin.HasSetting(lucent.rate.hide.{k})")]
    return ", ".join(names) or t("none", "geen")


def settings():
    while True:
        items = [xbmcgui.ListItem(t("OMDb key", "OMDb-sleutel"), state_label()),
                 xbmcgui.ListItem(t("Test the key", "Sleutel testen")),
                 xbmcgui.ListItem(t("MDBList key (Letterboxd, RT audience, Metacritic users)", "MDBList-sleutel (Letterboxd, RT publiek, Metacritic gebruikers)"), mdb_state_label()),
                 xbmcgui.ListItem(t("Test the MDBList key", "MDBList-sleutel testen")),
                 xbmcgui.ListItem(t("Scores to show", "Scores tonen"), chosen_label()),
                 xbmcgui.ListItem(t("Scores in the lists", "Scores in de lijsten"), lists_label())]
        for li, icon in zip(items, ("icons/lock.png", "icons/refresh.png", "icons/lock.png", "icons/refresh.png", "icons/star.png", "icons/list.png")):
            li.setArt({"icon": icon})
        pick = xbmcgui.Dialog().select(t("Scores (OMDb / MDBList)", "Scores (OMDb / MDBList)"), items, useDetails=True)
        if pick < 0:
            break
        (set_key, test, set_mdb_key, test_mdb, choose, toggle_lists)[pick]()
        LIST["keyt"] = 0.0
    xbmc.executebuiltin(f'Skin.SetString(lucent.omdb.state,"{state_label()}")')


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "settings":
        settings()
