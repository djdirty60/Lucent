"""Lucent: scores from OMDb (IMDb, Rotten Tomatoes, Metacritic) on the info page, with your own free OMDb key.

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
CACHE = DIR + "omdb_cache.json"         # *_cache.json stays out of the backup
WEEK, DAY = 7 * 86400, 86400
PROPS = ("imdb", "votes", "rt", "rtc", "mc", "mcc", "for")
GREEN, YELLOW, RED = "FF3DD68C", "FFFFCC33", "FFE5484D"
SCORES = [("imdb", "IMDb"), ("rt", "Rotten Tomatoes"), ("mc", "Metacritic"), ("tmdb", "TMDB"), ("trakt", "Trakt")]


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
    if not key() or item.dbtype not in ("movie", "tvshow"):
        return
    imdb_id = imdb_of(item)
    d = fetch(imdb_id) if imdb_id else {}
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
    HOME.setProperty("lucent.omdb.for", item.key)


# ----------------------------------------------------------------------------- scores in the lists
LIST = {"id": "", "since": 0.0, "done": "", "busy": False, "key": "", "keyt": 0.0}
LPROPS = ("rt", "rtc", "mc", "mcc", "imdb")
TMDB_IMDB = {}                                     # tmdb id -> imdb id, for this session


def _key_cached():
    if time.time() - LIST["keyt"] > 30:
        LIST["key"], LIST["keyt"] = key(), time.time()
    return LIST["key"]


def _lclear():
    if HOME.getProperty("lucent.omdbl.for"):
        for p in LPROPS + ("for",):
            HOME.clearProperty("lucent.omdbl." + p)


def _fill(ident, imdb_id, tmdb_id, kind):
    try:
        if not imdb_id and tmdb_id:
            imdb_id = TMDB_IMDB.get(f"{kind}:{tmdb_id}")
            if imdb_id is None:
                class _I:                           # what imdb_of() reads
                    imdb, tmdb, dbtype = "", tmdb_id, kind
                imdb_id = TMDB_IMDB[f"{kind}:{tmdb_id}"] = imdb_of(_I())
        d = fetch(imdb_id) if imdb_id else {}
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
        LIST["id"] = ""
        _lclear()
        return
    label = xbmc.getInfoLabel
    imdb_id = label("ListItem.UniqueID(imdb)") or label("ListItem.IMDBNumber") or label("ListItem.Property(imdb_id)")
    imdb_id = imdb_id if imdb_id.startswith("tt") else ""
    tmdb_id = label("ListItem.UniqueID(tmdb)") or label("ListItem.Property(tmdb_id)")
    tmdb_id = tmdb_id if tmdb_id.isdigit() else ""
    kind = "tvshow" if label("ListItem.DBType") == "tvshow" or xbmc.getCondVisibility("Container.Content(tvshows)") else "movie"
    ident = imdb_id or (f"tmdb:{kind}:{tmdb_id}" if tmdb_id else "")
    now = time.time()
    if ident != LIST["id"]:
        LIST["id"], LIST["since"] = ident, now
        _lclear()
        return
    if not ident or LIST["done"] == ident or LIST["busy"] or now - LIST["since"] < 0.5:
        return
    LIST["busy"] = True
    import threading
    threading.Thread(target=_fill, args=(ident, imdb_id, tmdb_id, kind), daemon=True).start()


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
                 xbmcgui.ListItem(t("Scores to show", "Scores tonen"), chosen_label()),
                 xbmcgui.ListItem(t("Rotten Tomatoes and Metacritic in the lists", "Rotten Tomatoes en Metacritic in de lijsten"), lists_label())]
        for li, icon in zip(items, ("icons/lock.png", "icons/refresh.png", "icons/star.png", "icons/list.png")):
            li.setArt({"icon": icon})
        pick = xbmcgui.Dialog().select(t("Scores (OMDb)", "Scores (OMDb)"), items, useDetails=True)
        if pick < 0:
            break
        (set_key, test, choose, toggle_lists)[pick]()
        LIST["keyt"] = 0.0
    xbmc.executebuiltin(f'Skin.SetString(lucent.omdb.state,"{state_label()}")')


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "settings":
        settings()
