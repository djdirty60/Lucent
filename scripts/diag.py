# -*- coding: utf-8 -*-
"""Lucent: self-test and a safe log.

    RunScript(special://skin/scripts/diag.py,test)   checks the add-ons Lucent needs and says in plain words what is missing
    RunScript(special://skin/scripts/diag.py,log)    writes a copy of Kodi's log (this run and the previous one) with every login blanked out, to share;
                                                     on screen only the last lines about playing

The log copy removes: user names / passwords in links (?username=, /live/user/pass/), the Xtream login saved by Lucent,
tokens / API keys, and the server address of the provider. Nothing is sent anywhere; the file stays on the box.
"""
import json
import re
import sys

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


def row_state(path):
    """(state 2/1/0, text) for one Home row: where it comes from (Kodi reads it when the row is on screen)."""
    if path.startswith("plugin://plugin.video.lucent/"):
        return 2, t("from the video add-on", "uit de video-add-on")
    if path.startswith("plugin://script.lucent.library/"):
        return 0, t("from Lucent Library, which is no longer used: choose the row again", "uit Lucent Library, die niet meer gebruikt wordt: kies de rij opnieuw")
    if path.startswith("plugin://"):
        addon = path.split("/")[2]
        if not cond(f"System.AddonIsEnabled({addon})"):
            return 0, t(f"{addon} is not installed or switched off", f"{addon} is niet geïnstalleerd of uitgezet")
        return 2, t(f"from {addon}", f"uit {addon}")
    return 2, t("from Kodi", "uit Kodi")


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
        addon_line("plugin.video.lucent", "Lucent Video", t("Install it from the Lucent repository (or run the setup assistant).",
                                                            "Installeer hem vanuit de Lucent-repository (of start de setup-assistent).")),
        addon_line("pvr.iptvsimple", "IPTV Simple", t("Install it: Add-ons > PVR clients.", "Installeer hem: Add-ons > PVR-clients.")),
    ]
    for optional, name in (("service.subtitles.lucent", "Lucent Subtitles"),):
        if addon_state(optional):                     # optional: only shown when it is there
            rows.append(addon_line(optional, name, ""))
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
    text = re.sub(r"(https?://)([^/\s\"'<>@]+)(/[^\s\"'<>]*)?", _short_url, text)   # only the server name
    text = re.sub(r"(plugin://[\w.]+/)\?[^\s\"'<>\]]*", r"\1?…", text)                      # add-on yes, its arguments no
    return text


def _short_url(m):
    """'https://name-app.host.tld:123/api/v1/secret' -> 'https://….host.tld/…': a personal sub-domain or a token in the
    path (debrid playback links, AIOStreams) never shows."""
    host = m.group(2).split(":")[0]
    labels = host.split(".")
    if not re.fullmatch(r"[\d.]+", host) and len(labels) > 2:
        host = "…." + ".".join(labels[-2:])
    return m.group(1) + host + ("/…" if m.group(3) and m.group(3) != "/" else "")


KEEP = re.compile(r"(?i)lucent|iptvsimple|pvr|error|exception|traceback|warning|youtube|inputstream|videoplayer"
                  r"|ccurlfile|curl|ffmpeg|dash|cplayer|playlistplayer|onplayback|avstarted")
SHOW = re.compile(r"(?i)youtube|inputstream|ccurlfile|videoplayer|error|onplayback|trailer")


def tail(path, size):
    """The last part of a log file as lines ('' when it is not there)."""
    try:
        with open(xbmcvfs.translatePath(path), "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - size))
            return fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None


def screen_lines(lines, most=40):
    """The last lines about playing, newest first: time only, the same message once (with how often it came)."""
    seen, out = {}, []
    for x in reversed(lines):
        if not SHOW.search(x):
            continue
        m = re.match(r"\d{4}-\d\d-\d\d (\d\d:\d\d:\d\d)\.\d+ T:\d+\s+(.*)", x)
        when, msg = (m.group(1), m.group(2)) if m else ("", x)
        msg = re.sub(r"\s+", " ", msg)[:150]
        if msg in seen:
            seen[msg][1] += 1
            continue
        if len(out) >= most:
            continue
        seen[msg] = [when, 1]
        out.append(msg)
    return [f"{seen[m][0]}  {m}" + (f"   (×{seen[m][1]})" if seen[m][1] > 1 else "") for m in out]


def safe_log():
    bar = xbmcgui.DialogProgressBG()
    bar.create(t("Safe log", "Veilig logboek"), t("Reading the log...", "Logboek lezen..."))
    try:
        now = tail(LOG, 1500 * 1024)
        if now is None:
            bar.close()
            xbmcgui.Dialog().ok(t("Safe log", "Veilig logboek"), t("Could not read the log.", "Het logboek is niet te lezen."))
            return
        old = tail("special://logpath/kodi.old.log", 800 * 1024) or []   # the previous run: what happened before a crash
        known = secrets()
        bar.update(40)
        keep_now = [scrub(x, known) for x in now if KEEP.search(x)][-2500:]
        keep_old = [scrub(x, known) for x in old if KEEP.search(x)][-1200:]
        bar.update(80)
        body = (t("Lucent safe log (logins blanked out)", "Lucent veilig logboek (logins weggehaald)") + "\n"
                + f"Kodi {xbmc.getInfoLabel('System.BuildVersion')}  |  skin {xbmc.getInfoLabel('System.AddonVersion(skin.lucent)')}"
                + f"  |  YouTube {xbmc.getInfoLabel('System.AddonVersion(plugin.video.youtube)')}"
                + f"  |  InputStream Adaptive {xbmc.getInfoLabel('System.AddonVersion(inputstream.adaptive)')}\n\n"
                + "===== " + t("this run", "deze keer") + " =====\n" + "\n".join(keep_now)
                + "\n\n===== " + t("previous run (kodi.old.log)", "vorige keer (kodi.old.log)") + " =====\n" + "\n".join(keep_old))
        with xbmcvfs.File(OUT, "w") as fh:
            fh.write(body)
        # on screen only the last lines about playing (a long text makes the text window very slow on a TV box)
        short = screen_lines(keep_now)
    finally:
        bar.close()
    xbmcgui.Dialog().ok(t("Safe log", "Veilig logboek"),
                        t(f"Saved to {xbmcvfs.translatePath(OUT)} (logins blanked out). Next: the last lines about playing. "
                          "Take a photo of them with your phone.",
                          f"Opgeslagen in {xbmcvfs.translatePath(OUT)} (logins weggehaald). Hierna: de laatste regels over afspelen. "
                          "Maak daar een foto van met je telefoon."))
    xbmcgui.Dialog().textviewer(t("Last lines about playing (newest first)", "Laatste regels over afspelen (nieuwste bovenaan)"),
                                "\n".join(short) or t("No lines about playing yet.", "Nog geen regels over afspelen."))


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    safe_log() if action == "log" else test()
