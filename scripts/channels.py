# -*- coding: utf-8 -*-
"""Lucent: hide channels you never watch (IPTV Simple).

    RunScript(special://skin/scripts/channels.py)           menu
    RunScript(special://skin/scripts/channels.py,refresh)   from the helper once a day: build the filtered list again

A big IPTV list holds hundreds of channels in languages you do not watch. This makes IPTV Simple read a shorter list:
Lucent fetches the channel list (the link or file IPTV Simple used), leaves out the groups and channels you chose, saves
the rest as a local file and points IPTV Simple at that file. "Show everything again" puts the original link back.

Kept in special://profile/addon_data/skin.lucent/channel_filter.json: the original settings, the groups and the names
that are hidden. The filtered list contains your stream links (logins): it stays in that folder.
"""
import json
import re
import sys
import unicodedata

import xbmc
import xbmcgui
import xbmcvfs

import xtream

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
FOLDER = "special://profile/addon_data/skin.lucent/"
CFG = FOLDER + "channel_filter.json"
OUT = FOLDER + "channels-filtered.m3u"
UA = "Lucent/1.0"
BIG = 80 * 1024 * 1024


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] channels: {text}", xbmc.LOGINFO)


def norm(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load():
    try:
        with xbmcvfs.File(CFG) as fh:
            data = json.loads(fh.read() or "{}")
    except Exception:  # noqa: BLE001
        data = {}
    return data if isinstance(data, dict) else {}


def save(cfg):
    xbmcvfs.mkdirs(FOLDER)
    with xbmcvfs.File(CFG, "w") as fh:
        fh.write(json.dumps(cfg))


# ----------------------------------------------------------------------------- reading and filtering a list
def split_agent(url):
    """'http://x/get.php?..|User-Agent=VLC%2F3' -> (link, 'VLC/3')."""
    if "|" in url:
        link, _sep, rest = url.partition("|")
        m = re.search(r"User-Agent=([^&|]+)", rest, re.I)
        import urllib.parse
        return link, urllib.parse.unquote(m.group(1)) if m else ""
    return url, ""


def read_source(cfg):
    """Text of the original channel list, or '' when it cannot be had."""
    if cfg.get("kind") == "local":
        try:
            with xbmcvfs.File(cfg["source"]) as fh:
                return fh.read()
        except Exception:  # noqa: BLE001
            return ""
    code, text = xtream.fetch_head(cfg["source"], cfg.get("agent") or UA, BIG)
    if "#EXTINF" not in text:
        log(f"source answered {code}")
        return ""
    return text


def parse(text):
    """(header lines, [(group, name, [lines of the entry])])"""
    header, entries, current = [], [], None
    for line in text.splitlines():
        if line.startswith("#EXTINF"):
            m = re.search(r'group-title="([^"]*)"', line)
            current = [(m.group(1).strip() if m else ""), line.rsplit(",", 1)[-1].strip(), [line]]
            entries.append(current)
        elif current is None:
            header.append(line)
        elif line.strip():
            current[2].append(line)
    return header, [(g, n, ls) for g, n, ls in entries]


def groups_of(entries):
    out = {}
    for group, _name, _lines in entries:
        out[group] = out.get(group, 0) + 1
    return out


def filtered(header, entries, cfg):
    hide_g = set(cfg.get("hide_groups") or [])
    hide_n = {norm(n) for n in cfg.get("hide_names") or []}
    keep = [e for e in entries if e[0] not in hide_g and norm(e[1]) not in hide_n]
    lines = list(header) or ["#EXTM3U"]
    for _g, _n, ls in keep:
        lines.extend(ls)
    return "\n".join(lines) + "\n", len(keep)


# ----------------------------------------------------------------------------- IPTV Simple's instance
def pick_instance(cfg):
    if cfg.get("instance") and xbmcvfs.exists(cfg["instance"]):
        return cfg["instance"]
    files = xtream.instance_files()
    if not files:
        return ""
    if len(files) == 1:
        return files[0][1]
    names = []
    for num, path in files:
        values = xtream.read_settings(path)
        names.append(values.get("kodi_addon_instance_name") or f"#{num}")
    pick = xbmcgui.Dialog().select(t("Which channel list?", "Welke zenderlijst?"), names)
    return files[pick][1] if pick >= 0 else ""


def remember_original(cfg, path):
    """First time: note where IPTV Simple gets its list now."""
    values = xtream.read_settings(path)
    if cfg.get("source") and values.get("m3uPathType") == "0" and values.get("m3uPath") == OUT:
        return True                                           # still our filtered file: the original is already known
    cfg.pop("source", None)                                  # new setup (for example a new Xtream login): learn it again
    if values.get("m3uPathType") == "0" and values.get("m3uPath"):
        cfg.update(kind="local", source=values["m3uPath"], agent="")
    elif values.get("m3uUrl"):
        link, agent = split_agent(values["m3uUrl"])
        cfg.update(kind="remote", source=link, agent=agent or values.get("defaultUserAgent", ""))
    else:
        return False
    cfg["instance"] = path
    cfg["orig_agent"] = values.get("defaultUserAgent", "")
    return True


def point_to_file(cfg):
    values = xtream.read_settings(cfg["instance"])
    values.update({"m3uPathType": "0", "m3uPath": OUT, "m3uCache": "true", "m3uRefreshMode": "2", "m3uRefreshHour": "4"})
    values.pop("m3uUrl", None)
    if cfg.get("agent"):
        values["defaultUserAgent"] = cfg["agent"]            # the streams are still asked the way the panel accepts
    xtream.write_settings(cfg["instance"], values)
    clear_caches(cfg["instance"])


def point_back(cfg):
    """Give IPTV Simple its original list again."""
    import urllib.parse
    values = xtream.read_settings(cfg["instance"])
    if cfg.get("kind") == "remote":
        agent = cfg.get("agent") or ""
        values.update({"m3uPathType": "1", "m3uUrl": cfg["source"] + ("|User-Agent=" + urllib.parse.quote(agent, safe="") if agent else "")})
        values.pop("m3uPath", None)
    else:
        values.update({"m3uPathType": "0", "m3uPath": cfg["source"]})
        values.pop("m3uUrl", None)
    if cfg.get("orig_agent"):
        values["defaultUserAgent"] = cfg["orig_agent"]
    xtream.write_settings(cfg["instance"], values)
    clear_caches(cfg["instance"])


def clear_caches(path):
    m = re.search(r"instance-settings-(\d+)\.xml$", path)
    num = m.group(1) if m else "1"
    for name in (f"iptv.m3u.cache-{num}", "iptv.m3u.cache"):
        if xbmcvfs.exists(xtream.DATA + name):
            xbmcvfs.delete(xtream.DATA + name)


def restart(message):
    busy = xbmcgui.DialogProgress()
    busy.create(t("Channels", "Zenders"), message)
    try:
        state = xtream.restart_addon(busy)
    finally:
        busy.close()
    return state


def build_file(cfg, text=None):
    """Write the filtered list. Returns (visible, total) or None when the source cannot be read."""
    text = text if text is not None else read_source(cfg)
    if not text:
        return None
    header, entries = parse(text)
    body, kept = filtered(header, entries, cfg)
    xbmcvfs.mkdirs(FOLDER)
    with xbmcvfs.File(OUT, "w") as fh:
        fh.write(body)
    return kept, len(entries)


# ----------------------------------------------------------------------------- menu
def apply_and_restart(cfg, text):
    result = build_file(cfg, text)
    if not result:
        xbmcgui.Dialog().ok(t("Channels", "Zenders"), t("Could not read the channel list.", "De zenderlijst is niet te lezen."))
        return
    kept, total = result
    if kept == 0:
        xbmcgui.Dialog().ok(t("Channels", "Zenders"), t("That would hide every channel. Nothing was changed.", "Dan zou elke zender verborgen zijn. Er is niets veranderd."))
        return
    point_to_file(cfg)
    save(cfg)
    state = restart(t(f"Loading {kept} of {total} channels…", f"{kept} van {total} zenders laden…"))
    text = t(f"Done: {kept} of {total} channels are shown.", f"Klaar: {kept} van {total} zenders worden getoond.")
    if state != "ok":
        text += "\n" + t("The channels were not in yet; give it a minute, or restart Kodi.", "De zenders waren nog niet binnen; geef het een minuut, of start Kodi opnieuw.")
    xbmcgui.Dialog().ok(t("Channels", "Zenders"), text)


def choose_groups(cfg, entries):
    counts = groups_of(entries)
    names = sorted(counts, key=lambda g: (g == "", norm(g)))
    hidden = set(cfg.get("hide_groups") or [])
    labels = [f"{g or t('(no group)', '(zonder groep)')}  ·  {counts[g]}" for g in names]
    chosen = xbmcgui.Dialog().multiselect(t("Which groups do you want to see?", "Welke groepen wil je zien?"), labels,
                                          preselect=[i for i, g in enumerate(names) if g not in hidden])
    if chosen is None:
        return None
    keep = {names[i] for i in chosen}
    return [g for g in names if g not in keep]


def by_word(cfg, entries):
    words = xtream.ask(t("Show only groups with one of these words (comma between), for example: NL, BE, SPORT",
                         "Toon alleen groepen met een van deze woorden (komma ertussen), bijvoorbeeld: NL, BE, SPORT"))
    words = [norm(w) for w in re.split(r"[,;]", words or "") if norm(w)]
    if not words:
        return None
    counts = groups_of(entries)
    keep = [g for g in counts if any(re.search(rf"(^| ){re.escape(w)}( |$)", norm(g)) or w in norm(g) for w in words)]
    if not keep:
        xbmcgui.Dialog().ok(t("Channels", "Zenders"), t("No group contains those words.", "Geen enkele groep bevat die woorden."))
        return None
    shown = sum(counts[g] for g in keep)
    if not xbmcgui.Dialog().yesno(t("Channels", "Zenders"),
                                  t(f"{len(keep)} groups with {shown} of {len(entries)} channels stay. Go ahead?",
                                    f"{len(keep)} groepen met {shown} van {len(entries)} zenders blijven. Doorgaan?")):
        return None
    return [g for g in counts if g not in keep]


def menu():
    if not xbmc.getCondVisibility(f"System.HasAddon({xtream.IPTV})"):
        xbmcgui.Dialog().ok(t("Channels", "Zenders"), t("IPTV Simple is not installed.", "IPTV Simple staat er niet op."))
        return
    cfg = load()
    path = pick_instance(cfg)
    if not path or not remember_original(cfg, path):
        xbmcgui.Dialog().ok(t("Channels", "Zenders"), t("No channel list is set up in IPTV Simple yet (Xtream login first).",
                                                       "In IPTV Simple staat nog geen zenderlijst (eerst de Xtream-inlog)."))
        return
    busy = xbmcgui.DialogProgress()
    busy.create(t("Channels", "Zenders"), t("Reading the channel list…", "Zenderlijst lezen…"))
    text = read_source(cfg)
    busy.close()
    if not text:
        xbmcgui.Dialog().ok(t("Channels", "Zenders"), t("Could not read the channel list. Is the provider reachable?", "De zenderlijst is niet te lezen. Is de aanbieder bereikbaar?"))
        return
    _header, entries = parse(text)
    here = None
    try:
        import live
        here = live.current_channel()
    except Exception:  # noqa: BLE001
        pass
    hidden_n = len(cfg.get("hide_groups") or []) + len(cfg.get("hide_names") or [])
    options = [("groups", t("Choose the groups to show", "Kies de groepen die je wilt zien")),
               ("words", t("Quick: only groups with a word (NL, BE, SPORT …)", "Snel: alleen groepen met een woord (NL, BE, SPORT …)"))]
    if here and here.get("name"):
        options.append(("now", t(f"Hide the channel I am watching: {here['name']}", f"Verberg de zender die ik kijk: {here['name']}")))
    if hidden_n:
        options.append(("all", t("Show everything again", "Alles weer tonen")))
    pick = xbmcgui.Dialog().select(t("Channels", "Zenders") + t(f"  ·  {len(entries)} in the list", f"  ·  {len(entries)} in de lijst"), [o[1] for o in options])
    if pick < 0:
        return
    kind = options[pick][0]
    if kind == "groups":
        new = choose_groups(cfg, entries)
        if new is None:
            return
        cfg["hide_groups"] = new
    elif kind == "words":
        new = by_word(cfg, entries)
        if new is None:
            return
        cfg["hide_groups"] = new
    elif kind == "now":
        cfg["hide_names"] = sorted(set(cfg.get("hide_names") or []) | {here["name"]})
    elif kind == "all":
        cfg["hide_groups"], cfg["hide_names"] = [], []
        point_back(cfg)
        save(cfg)
        restart(t("Loading all channels…", "Alle zenders laden…"))
        xbmcgui.Dialog().ok(t("Channels", "Zenders"), t("Everything is shown again.", "Alles wordt weer getoond."))
        return
    apply_and_restart(cfg, text)


def refresh():
    """Helper, once a day: the provider adds and removes channels; build the filtered list again with the same choices."""
    cfg = load()
    if not cfg.get("source") or not (cfg.get("hide_groups") or cfg.get("hide_names")):
        return
    result = build_file(cfg)
    log(f"refresh: {result}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        refresh()
    else:
        menu()
