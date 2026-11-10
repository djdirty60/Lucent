# -*- coding: utf-8 -*-
"""Lucent: extra subtitle help, used by subs_live.py, subtitles.py and helper.py.

1. Remember per series which release group / service gave the subtitle you used, and prefer it next time.
2. Get the subtitle for the next episode ready while you watch, so it is on at once when that episode starts.
3. (in subs_live.background) translate with AI when nothing in your language exists.
4. Shift a subtitle earlier / later, remembered per film or episode.
5. Size, colour and background of subtitles (Kodi's own settings), from the subtitle list.
7. A wish list: a video without a subtitle in your language is checked again every few hours; when one turns up,
   Lucent tells you.

plugin://plugin.video.lucent/?action=subs_prefetch   step 2 (started by subtitles.py during an episode)
"""
import json
import os
import re
import shutil
import time
import urllib.parse

import subconf
import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
DIR = subconf.data_dir("subs_extra")
OWN = "service.subtitles.lucent"
HOME = xbmcgui.Window(10000)


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[lucent.video] subs_extra: {text}", xbmc.LOGINFO)


def info(label):
    return xbmc.getInfoLabel(label) or ""


def load(name, default):
    try:
        with open(os.path.join(DIR, name), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def save(name, data):
    try:
        os.makedirs(DIR, exist_ok=True)
        tmp = os.path.join(DIR, name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, os.path.join(DIR, name))
    except Exception as error:  # noqa: BLE001
        log(f"save {name}: {error}")


# ----------------------------------------------------------------------------- the video
def now_video():
    """What is playing, in the form Lucent Ondertitels understands."""
    v = {"show": info("VideoPlayer.TVShowTitle"), "season": info("VideoPlayer.Season"),
         "episode": info("VideoPlayer.Episode"), "title": info("VideoPlayer.OriginalTitle") or info("VideoPlayer.Title"),
         "year": info("VideoPlayer.Year"), "imdb": info("VideoPlayer.IMDBNumber")}
    if not str(v["imdb"]).startswith("tt"):
        v["imdb"] = ""
    return v


def label(v):
    if v.get("show"):
        return f"{v['show']} S{v.get('season')} E{v.get('episode')}"
    return f"{v.get('title')}" + (f" ({v['year']})" if v.get("year") else "")


def show_key(v=None):
    v = v or now_video()
    return re.sub(r"\W+", " ", (v.get("show") or "").lower()).strip()


def episode_key(v):
    return f"{show_key(v)}|{int(v.get('season') or 0)}|{int(v.get('episode') or 0)}"


def media_key():
    try:
        import subs_ai
        return subs_ai.media_key()
    except Exception:  # noqa: BLE001
        return re.sub(r"\W+", "", label(now_video()).lower())


# ----------------------------------------------------------------------------- 1. remember per series
def split_label2(text):
    """Lucent Ondertitels writes 'release  ·  service' as the second line of a result."""
    parts = (text or "").split("  ·  ")
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


def group_of(release):
    name = re.sub(r"\.(srt|ass|ssa|sub|vtt|zip)$", "", (release or "").strip(), flags=re.I)
    m = re.search(r"-([A-Za-z0-9]{2,15})(?:\[[^\]]*\])?$", name)
    return m.group(1).lower() if m else ""


def remember(release, source=""):
    v = now_video()
    if not v.get("show") or not release:
        return
    data = load("series.json", {})
    data[show_key(v)] = {"group": group_of(release), "source": source, "at": int(time.time())}
    if len(data) > 300:                                   # keep the 300 most recent series
        data = dict(sorted(data.items(), key=lambda kv: -kv[1].get("at", 0))[:300])
    save("series.json", data)
    log(f"remembered for {v['show']}: {data[show_key(v)]}")


def preference(v=None):
    v = v or now_video()
    return load("series.json", {}).get(show_key(v)) if v.get("show") else None


def pref_rank(release, source, pref):
    """0 = same release group as last time, 1 = same service, 2 = no link (lower is better)."""
    if not pref:
        return 2
    group = pref.get("group")
    if group and group_of(release) == group:
        return 0
    if pref.get("source") and source and pref["source"].lower() == source.lower():
        return 1
    return 2


# ----------------------------------------------------------------------------- asking Lucent Ondertitels for any video
def own_installed():
    return xbmc.getCondVisibility(f"System.HasAddon({OWN})")


def own_search(video, languages, mine_name):
    query = urllib.parse.urlencode({"action": "search", "languages": ",".join(languages), "preferredlanguage": mine_name,
                                    "video": json.dumps(video)})
    from subs_live import rpc
    try:
        return rpc("Files.GetDirectory", {"directory": f"plugin://{OWN}/?{query}", "media": "files",
                                          "properties": ["thumbnail", "art"], "sort": {"method": "none"}}).get("files") or []
    except Exception as error:  # noqa: BLE001
        log(f"search {label(video)}: {error}")
        return []


def best_of(files, code, pref=None):
    """The add-on lists its best first; among those in your language, the one that fits your series wins."""
    from subs_live import lang_of
    mine = [(n, f) for n, f in enumerate(files) if f.get("file") and lang_of(f) == code]
    if not mine:
        return None
    return min(mine, key=lambda nf: (pref_rank(*split_label2(nf[1].get("label2", "")), pref), nf[0]))[1]


# ----------------------------------------------------------------------------- 2. next episode
def next_of(v):
    try:
        return {**v, "episode": str(int(v["episode"]) + 1), "imdb": v.get("imdb", "")}
    except (KeyError, ValueError, TypeError):
        return None


def prefetch():
    """While an episode plays: get the subtitle for the next one ready."""
    import subs_live
    v = now_video()
    if not v.get("show") or not own_installed():
        return
    nxt = next_of(v)
    if not nxt:
        return
    store = load("next.json", {})
    key = episode_key(nxt)
    if key in store and os.path.exists(store[key].get("path", "")):
        return
    languages, mine_name = subs_live.search_languages()
    code = subs_live.my_code()
    files = own_search(nxt, languages, mine_name)
    best = best_of(files, code, preference(v))
    if not best:
        log(f"next episode {label(nxt)}: nothing in {code} yet")
        return
    local = subs_live.download(best["file"])
    if not local or not os.path.exists(local):
        return
    os.makedirs(os.path.join(DIR, "next"), exist_ok=True)
    keep = os.path.join(DIR, "next", re.sub(r"[^\w.-]+", ".", f"{key}.{code}") + os.path.splitext(local)[1])
    shutil.copyfile(local, keep)
    release, source = split_label2(best.get("label2", ""))
    store[key] = {"path": keep, "lang": code, "release": release, "source": source, "at": int(time.time())}
    for k in [k for k, e in store.items() if time.time() - e.get("at", 0) > 14 * 86400]:   # two weeks at most
        try:
            os.remove(store[k]["path"])
        except OSError:
            pass
        store.pop(k)
    save("next.json", store)
    log(f"next episode {label(nxt)}: ready ({release})")


def prefetched(code):
    """The subtitle that was got ready for the episode now playing ('' when none)."""
    v = now_video()
    if not v.get("show"):
        return None
    entry = load("next.json", {}).get(episode_key(v))
    if entry and entry.get("lang") == code and os.path.exists(entry.get("path", "")):
        return entry
    return None


# ----------------------------------------------------------------------------- 4. timing
def get_offset():
    return float(load("offsets.json", {}).get(media_key(), 0.0))


def set_offset(value):
    data = load("offsets.json", {})
    value = round(value, 1)
    if abs(value) < 0.05:
        data.pop(media_key(), None)
    else:
        data[media_key()] = value
    if len(data) > 500:
        data = dict(list(data.items())[-500:])
    save("offsets.json", data)
    return value


def stamp(seconds):
    seconds = max(0.0, seconds)
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def shifted(path, offset):
    """A copy of an SRT subtitle that is `offset` seconds later (negative: earlier). '' when not possible."""
    if not path or abs(offset) < 0.05 or not path.lower().endswith(".srt"):
        return ""
    import subs_ai
    try:
        cues = subs_ai.parse_srt(subs_ai.read_text(path))
    except Exception as error:  # noqa: BLE001
        log(f"shift: {error}")
        return ""
    if not cues:
        return ""
    for c in cues:
        c["time"] = f"{stamp(c['start'] + offset)} --> {stamp(c['end'] + offset)}"
    os.makedirs(os.path.join(DIR, "shift"), exist_ok=True)
    for name in os.listdir(os.path.join(DIR, "shift")):           # only the newest few are needed
        full = os.path.join(DIR, "shift", name)
        if time.time() - os.path.getmtime(full) > 3600:
            try:
                os.remove(full)
            except OSError:
                pass
    out = os.path.join(DIR, "shift", f"{media_key()}.{int(time.time() * 1000)}.srt")
    subs_ai.write_srt(out, cues)
    return out


def with_offset(path):
    """The file to load for this video: shifted when you set a time for it before."""
    HOME.setProperty("lucent.subs.file", path or "")
    off = get_offset()
    return shifted(path, off) or path


# ----------------------------------------------------------------------------- 4 + 5. the menu in the subtitle list
SIZES = [(34, t("Small", "Klein")), (42, t("Normal", "Normaal")), (52, t("Large", "Groot")), (62, t("Extra large", "Extra groot"))]
COLOURS = [("FFFFFFFF", t("White", "Wit")), ("FFFFFF00", t("Yellow", "Geel")), ("FFDDDDDD", t("Light grey", "Lichtgrijs"))]
BACKS = [(0, t("None (black edge)", "Geen (zwarte rand)")), (1, t("Shadow", "Schaduw")), (2, t("Dark box", "Donker vlak"))]


def setting(name):
    from subs_live import rpc
    try:
        return rpc("Settings.GetSettingValue", {"setting": name}).get("value")
    except Exception:  # noqa: BLE001
        return None


def set_setting(name, value):
    from subs_live import rpc
    rpc("Settings.SetSettingValue", {"setting": name, "value": value})


def refresh():
    """Kodi draws subtitles with the new look after they are switched off and on again."""
    if xbmc.getCondVisibility("VideoPlayer.SubtitlesEnabled"):
        player = xbmc.Player()
        player.showSubtitles(False)
        xbmc.sleep(200)
        player.showSubtitles(True)


def menu(code=""):
    """Time and look. Returns True when a subtitle was reloaded (the list may then close)."""
    dialog = xbmcgui.Dialog()
    while True:
        off = get_offset()
        size = setting("subtitles.fontsize") or 42
        colour = str(setting("subtitles.colorpick") or "FFFFFFFF").upper()
        back = setting("subtitles.backgroundtype") or 0
        rows = [
            (t("Earlier", "Eerder") + "  −0,5 s", ("shift", -0.5)),
            (t("Later", "Later") + "  +0,5 s", ("shift", 0.5)),
            (t("Earlier", "Eerder") + "  −0,1 s", ("shift", -0.1)),
            (t("Later", "Later") + "  +0,1 s", ("shift", 0.1)),
            (t("Time back to normal", "Tijd terug naar normaal") + (f"  ({off:+.1f} s)".replace(".", ",") if off else ""), ("reset", 0)),
            (t("Text size", "Tekstgrootte") + f":  {next((n for v, n in SIZES if v == size), size)}", ("size", 0)),
            (t("Colour", "Kleur") + f":  {next((n for v, n in COLOURS if v == colour), colour)}", ("colour", 0)),
            (t("Background", "Achtergrond") + f":  {next((n for v, n in BACKS if v == back), back)}", ("back", 0)),
        ]
        head = t("Time and look", "Tijd en opmaak") + (f"  ·  {off:+.1f} s".replace(".", ",") if off else "")
        pick = dialog.select(head, [r[0] for r in rows])
        if pick < 0:
            return False
        what, amount = rows[pick][1]
        if what in ("shift", "reset"):
            original = HOME.getProperty("lucent.subs.file")
            if not original or not os.path.exists(original) or not original.lower().endswith(".srt"):
                # a subtitle that is part of the film: Kodi's own delay slider
                xbmc.executebuiltin("Action(SubtitleDelay)")
                return True
            new = set_offset(0 if what == "reset" else off + amount)
            import subs_live
            subs_live.activate(original, code, 5)
            dialog.notification("Lucent", t("Subtitle time", "Ondertiteltijd") + f": {new:+.1f} s".replace(".", ","),
                                xbmcgui.NOTIFICATION_INFO, 2000)
            continue
        if what == "size":
            i = dialog.select(t("Text size", "Tekstgrootte"), [n for _v, n in SIZES])
            if i >= 0:
                set_setting("subtitles.fontsize", SIZES[i][0])
        elif what == "colour":
            i = dialog.select(t("Colour", "Kleur"), [n for _v, n in COLOURS])
            if i >= 0:
                set_setting("subtitles.colorpick", COLOURS[i][0])
        elif what == "back":
            i = dialog.select(t("Background", "Achtergrond"), [n for _v, n in BACKS])
            if i >= 0:
                set_setting("subtitles.backgroundtype", BACKS[i][0])
                if BACKS[i][0] == 2:
                    set_setting("subtitles.bgopacity", 70)
        refresh()


# ----------------------------------------------------------------------------- 7. wish list
def want(code):
    """Nothing in your language for what is playing now: check again later."""
    v = now_video()
    if not (v.get("show") or v.get("title")):
        return
    data = load("wanted.json", [])
    key = episode_key(v) if v.get("show") else f"movie|{v.get('imdb') or v.get('title')}|{v.get('year')}"
    if any(w["key"] == key and w["lang"] == code for w in data):
        return
    data.append({"key": key, "lang": code, "video": v, "label": label(v), "at": int(time.time()), "checked": int(time.time())})
    save("wanted.json", data[-30:])
    log(f"wish list + {label(v)} ({code})")


def check_wanted():
    """Every few hours (helper.py): is there something now for the videos on the wish list?"""
    if not own_installed() or subconf.on("lucent.subs.wanted.off"):
        return
    import subs_live
    data = load("wanted.json", [])
    if not data:
        return
    keep, found, now = [], [], time.time()
    languages, mine_name = subs_live.search_languages()
    asked = 0
    for w in data:
        if now - w.get("at", 0) > 30 * 86400:
            continue                                     # a month without luck: stop looking
        if now - w.get("checked", 0) < 6 * 3600 or asked >= 8 or xbmc.Player().isPlayingVideo():
            keep.append(w)
            continue
        asked += 1
        w["checked"] = int(now)
        files = own_search(w["video"], languages, mine_name)
        if best_of(files, w["lang"]):
            found.append(w)
        else:
            keep.append(w)
    save("wanted.json", keep)
    for w in found:
        name = subs_live.full_name(w["lang"], w["lang"].upper())
        log(f"wish list: {w['label']} now has {w['lang']}")
        english = xbmc.convertLanguage(w["lang"], xbmc.ENGLISH_NAME) or w["lang"].upper()
        xbmcgui.Dialog().notification("Lucent", t(f"{english} subtitle now available: {w['label']}",
                                                  f"Ondertitel ({name}) nu beschikbaar: {w['label']}"),
                                      xbmcgui.NOTIFICATION_INFO, 8000)


def unwant():
    """A subtitle in your language is on now: take this video off the wish list."""
    v = now_video()
    key = episode_key(v) if v.get("show") else f"movie|{v.get('imdb') or v.get('title')}|{v.get('year')}"
    data = load("wanted.json", [])
    rest = [w for w in data if w["key"] != key]
    if len(rest) != len(data):
        save("wanted.json", rest)
