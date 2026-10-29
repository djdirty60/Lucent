# -*- coding: utf-8 -*-
"""Lucent: self-test and a safe log.

    RunScript(special://skin/scripts/diag.py,test)   checks the add-ons Lucent needs and says in plain words what is missing
    RunScript(special://skin/scripts/diag.py,log)    writes a copy of Kodi's log with every login blanked out, to share

The log copy removes: user names / passwords in links (?username=, /live/user/pass/), the Xtream login saved by Lucent,
tokens / API keys, and the server address of the provider. Nothing is sent anywhere; the file stays on the box.
"""
import hashlib
import json
import re
import sys
import time
import urllib.parse

import xbmc
import xbmcgui
import xbmcvfs

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
LOGIN_FILE = "special://profile/addon_data/skin.lucent/xtream.json"
OUT = "special://home/lucent-log.txt"
LOG = "special://logpath/kodi.log"


def t(en, nl):
    return nl if NL else en


def cond(expr):
    return xbmc.getCondVisibility(expr)


def addon_state(addon_id):
    if not cond(f"System.HasAddon({addon_id})"):
        return 0                                   # not installed
    return 2 if cond(f"System.AddonIsEnabled({addon_id})") else 1


def line(state, text, fix=""):
    mark = {2: "[COLOR FF3FB950]OK[/COLOR]", 1: "[COLOR FFE5A100]!![/COLOR]", 0: "[COLOR FFE5534B]XX[/COLOR]"}[state]
    return f"{mark}  {text}" + (f"\n      [COLOR 99FFFFFF]{fix}[/COLOR]" if fix and state != 2 else "")


def addon_line(addon_id, name, fix_missing, fix_off=None):
    st = addon_state(addon_id)
    note = t("installed and on", "geïnstalleerd en aan") if st == 2 else (
        t("installed but switched off", "geïnstalleerd maar uitgezet") if st == 1 else t("not installed", "niet geïnstalleerd"))
    return line(st, f"{name}: {note}", fix_missing if st == 0 else (fix_off or t("Switch it on in Add-ons.", "Zet hem aan bij Add-ons.")))


LIBDATA = "special://profile/addon_data/script.lucent.library/"


def read_json(path):
    try:
        with xbmcvfs.File(xbmcvfs.translatePath(path)) as fh:
            return json.loads(fh.read() or "null")
    except Exception:  # noqa: BLE001
        return None


def row_state(path):
    """(state 2/1/0, text) for one Home row: has the library fetched it yet?"""
    base = "plugin://script.lucent.library/?"
    if path.startswith(base + "action=tmdb"):
        q = urllib.parse.parse_qs(path.split("?", 1)[1])
        name = (q.get("list") or [""])[0]
        if name == "tl":
            name = f"tl_{(q.get('user') or [''])[0]}_{(q.get('id') or [''])[0]}"
        saved = read_json(f"{LIBDATA}tmdb/{name}.json") or {}
        reg = (read_json(f"{LIBDATA}tmdb/registry.json") or {}).get(name) or {}
        n = len(saved.get("items") or [])
        if n:
            age = int((time.time() - saved.get("time", 0)) / 60)
            return 2, t(f"{n} titles, fetched {age} min ago", f"{n} titels, {age} min geleden opgehaald")
        if reg.get("why"):
            return 0, t("nothing: ", "niets: ") + str(reg["why"])
        return 1, t("not fetched yet (the service does one row at a time)", "nog niet opgehaald (de service doet één rij tegelijk)")
    key = hashlib.md5(path.encode("utf-8")).hexdigest()
    saved = read_json(f"{LIBDATA}widgets/{key}.json") or {}
    reg = read_json(f"{LIBDATA}widgets/reg/{key}.json") or {}
    n = len(saved.get("items") or [])
    if n:
        age = int((time.time() - saved.get("time", 0)) / 60)
        return 2, t(f"{n} titles, fetched {age} min ago", f"{n} titels, {age} min geleden opgehaald")
    if reg.get("retry", 0) > time.time():
        wait = int((reg["retry"] - time.time()) / 60) + 1
        return 0, t(f"the last try failed, trying again in {wait} min", f"de vorige poging mislukte, opnieuw over {wait} min")
    if reg:
        return 1, t("waiting to be fetched (one row at a time, Seren can be slow)", "wacht om opgehaald te worden (één rij tegelijk, Seren kan traag zijn)")
    return 1, t("the library has not seen this row yet", "de bibliotheek heeft deze rij nog niet gezien")


def home_rows():
    out = []
    lite = cond("Skin.HasSetting(lucent.lite)")
    for tab in range(0, 13):                                   # 0 = start tab copy, then every tab of the side menu
        title = xbmc.getInfoLabel(f"Skin.String(nuvio.tab{tab}.label)") if tab else t("Start tab", "Starttab")
        rows = []
        for n in range(1, 11):
            base = f"nuvio.home.w{n}" if tab == 0 else f"nuvio.tab{tab}.w{n}"
            path = xbmc.getInfoLabel(f"Skin.String({base}.path)")
            if not path:
                continue
            label = xbmc.getInfoLabel(f"Skin.String({base}.label)") or f"{n}"
            if lite and n > 6:
                rows.append(line(1, f"{n}. {label}: " + t("not built (light mode)", "niet opgebouwd (lichte stand)"),
                                 t("Light mode only builds rows 1-6. Switch it off in Settings > Skin settings.",
                                   "De lichte stand bouwt alleen rij 1-6. Zet hem uit bij Instellingen > Skin-instellingen.")))
                continue
            state, text = row_state(path)
            rows.append(line(state, f"{n}. {label}: {text}"))
        if rows and (tab or True):
            out.append(f"[B]{title}[/B]")
            out.extend(rows)
    return out


def test():
    rows = [
        addon_line("plugin.video.seren", "Seren", t("Settings > Lucent > Install Seren (or run the setup assistant).",
                                                    "Instellingen > Lucent > Seren installeren (of start de setup-assistent).")),
        addon_line("script.lucent.library", "Lucent Library", t("Install it from the Lucent repository.", "Installeer hem vanuit de Lucent-repository.")),
        addon_line("service.subtitles.lucent", "Lucent Subtitles", t("Install it from the Lucent repository.", "Installeer hem vanuit de Lucent-repository.")),
        addon_line("pvr.iptvsimple", "IPTV Simple", t("Install it: Add-ons > PVR clients.", "Installeer hem: Add-ons > PVR-clients.")),
    ]
    if addon_state("pvr.iptvsimple") == 2:
        ch = cond("Pvr.HasTVChannels")
        rows.append(line(2 if ch else 0, t("TV channels: ", "Tv-zenders: ") + (t("loaded", "ingelezen") if ch else t("none loaded", "geen ingelezen")),
                         t("Settings > Live TV > Xtream login, or fill in your channel list in IPTV Simple.",
                           "Instellingen > Live tv > Xtream-inlog, of vul je zenderlijst in bij IPTV Simple.")))
    free = xbmc.getInfoLabel("System.FreeMemory")
    rows.append(line(2, t("Memory free: ", "Vrij geheugen: ") + (free or "?")))
    rows.append(line(2, t("Kodi version: ", "Kodi-versie: ") + (xbmc.getInfoLabel("System.BuildVersion") or "?").split(" ")[0]))
    lite = cond("Skin.HasSetting(lucent.lite)")
    rows.append(line(2, t("Light mode: ", "Lichte stand: ") + (t("on", "aan") if lite else t("off", "uit"))))
    hr = home_rows()
    if hr:
        rows.append(t("Rows per tab:", "Rijen per tab:"))
        rows.extend(hr)
    bad = sum(1 for r in rows if r.startswith("[COLOR FFE5534B]") or r.startswith("[COLOR FFE5A100]"))
    head = t("Everything looks fine.", "Alles ziet er goed uit.") if not bad else \
        t(f"{bad} thing(s) need attention:", f"{bad} ding(en) vragen aandacht:")
    xbmcgui.Dialog().textviewer(t("Lucent self-test", "Lucent zelftest"), head + "\n\n" + "\n\n".join(rows))


# ----------------------------------------------------------------------------- safe log
def secrets():
    out = set()
    try:
        with xbmcvfs.File(LOGIN_FILE) as fh:
            cfg = json.loads(fh.read() or "{}")
        for key in ("user", "password"):
            if len(cfg.get(key) or "") >= 3:
                out.add(cfg[key])
        host = re.sub(r"^https?://", "", cfg.get("server") or "").split("/")[0]
        if host:
            out.add(host)
    except Exception:  # noqa: BLE001
        pass
    return out


def scrub(text, known):
    for value in sorted(known, key=len, reverse=True):
        text = text.replace(value, "***")
    text = re.sub(r"(?i)(username|password|user|pass|token|api[_-]?key|apikey|auth|key)=([^&\s\"']+)", r"\1=***", text)
    text = re.sub(r"(?i)(Api-Key|Authorization|Bearer|Cookie|Set-Cookie)(:\s*|\s+)[^\s\"']+", r"\1\2***", text)
    text = re.sub(r"(/(?:live|movie|series|timeshift)/)[^/\s\"']+/[^/\s\"']+/", r"\1***/***/", text)
    text = re.sub(r"(https?://)[^/\s:@\"']+:[^/\s@\"']+@", r"\1***:***@", text)
    return text


def safe_log():
    try:
        with open(xbmcvfs.translatePath(LOG), "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 1500 * 1024))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except Exception as error:  # noqa: BLE001
        xbmcgui.Dialog().ok(t("Safe log", "Veilig logboek"), t(f"Could not read the log: {error}", f"Het logboek is niet te lezen: {error}"))
        return
    known = secrets()
    keep = [scrub(x, known) for x in lines if re.search(r"(?i)lucent|seren|iptvsimple|pvr|error|exception|traceback|warning", x)]
    keep = keep[-1500:]
    body = t("Lucent safe log (logins blanked out)", "Lucent veilig logboek (logins weggehaald)") + "\n" + \
        f"Kodi {xbmc.getInfoLabel('System.BuildVersion')}  |  skin {xbmc.getInfoLabel('System.AddonVersion(skin.lucent)')}\n\n" + "\n".join(keep)
    with xbmcvfs.File(OUT, "w") as fh:
        fh.write(body)
    xbmcgui.Dialog().ok(t("Safe log", "Veilig logboek"),
                        t(f"Saved {len(keep)} lines to {xbmcvfs.translatePath(OUT)}. All logins are blanked out. Share that file or read it on screen next.",
                          f"{len(keep)} regels opgeslagen in {xbmcvfs.translatePath(OUT)}. Alle logins zijn weggehaald. Deel dat bestand, of lees het hierna op het scherm."))
    xbmcgui.Dialog().textviewer(t("Safe log", "Veilig logboek"), body[-60000:])


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    safe_log() if action == "log" else test()
