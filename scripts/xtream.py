# -*- coding: utf-8 -*-
"""Lucent: an Xtream Codes IPTV login -> a working IPTV Simple Client.

    RunScript(special://skin/scripts/xtream.py)

IPTV Simple Client has no Xtream login of its own: it wants a channel list (M3U) link and a guide (EPG) link.
With Xtream you get a server address, a user name and a password instead. This script asks for those three,
checks them with the server (player_api.php), builds the two links from them, writes them into IPTV Simple's
settings (an add-on instance file) and restarts the add-on, so the channels and the guide come in.
The login is never written to Kodi's log.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import xbmc
import xbmcgui
import xbmcvfs

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
IPTV = "pvr.iptvsimple"
DATA = f"special://profile/addon_data/{IPTV}/"
UA = "Lucent/1.0"


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] xtream: {text}", xbmc.LOGINFO)


def rpc(method, params=None):
    answer = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})))
    return answer.get("result")


def ask(heading, default="", hidden=False):
    value = xbmcgui.Dialog().input(heading, default, type=xbmcgui.INPUT_ALPHANUM,
                                   option=xbmcgui.ALPHANUM_HIDE_INPUT if hidden else 0)
    return (value or "").strip()


# ----------------------------------------------------------------------------- the login
def clean_server(text):
    """'host:8080', 'http://host:8080/', 'http://host/get.php?...' -> 'http://host:8080'"""
    text = text.strip()
    if not text:
        return ""
    if "://" not in text:
        text = "http://" + text
    parts = urllib.parse.urlsplit(text)
    if not parts.hostname:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def check(server, user, password):
    """What the server says about this login: (ok, message). Tried as several programs: some panels only talk to
    the apps they know (TiviMate, Smarters, VLC)."""
    url = f"{server}/player_api.php?{urllib.parse.urlencode({'username': user, 'password': password})}"
    data, kind, body = None, "", ""
    for _opt, agent in AGENTS:
        try:
            req = urllib.request.Request(url, headers=browser_headers(agent))
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = unpack(resp.read(), resp).decode("utf-8", "replace")
            data = json.loads(body or "{}")
            if isinstance(data, dict) and data.get("user_info"):
                break
        except json.JSONDecodeError:
            data = None                                   # a page instead of data: shown below
        except Exception as error:  # noqa: BLE001
            kind = type(error).__name__ + (f" {error.code}" if isinstance(error, urllib.error.HTTPError) else "")
            data = None
    if not isinstance(data, dict) or not data.get("user_info"):
        said = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()[:60]
        log(f"server did not answer the login ({said or kind or 'no user_info'})")
        return False, t(f"The server did not answer the login ({said or kind or 'no answer'}). Check the address and port.",
                        f"De server beantwoordt de inlog niet ({said or kind or 'geen antwoord'}). Controleer adres en poort.")
    LAST["login"] = data
    LAST["agent"] = agent
    info = data.get("user_info") or {}
    if str(info.get("auth")) != "1":
        return False, t("The server does not accept this user name and password.",
                        "De server accepteert deze gebruikersnaam en dit wachtwoord niet.")
    status = info.get("status") or ""
    exp = info.get("exp_date")
    when = ""
    try:
        if exp and str(exp).isdigit() and int(exp) > 0:
            when = time.strftime("%d-%m-%Y", time.localtime(int(exp)))
    except (ValueError, OverflowError):
        when = ""
    parts = [t("Login OK", "Inloggen gelukt")]
    if status and status.lower() != "active":
        parts.append(t(f"status: {status}", f"status: {status}"))
    if when:
        parts.append(t(f"valid until {when}", f"geldig tot {when}"))
    if info.get("max_connections"):
        parts.append(t(f"{info['max_connections']} connections", f"{info['max_connections']} verbindingen"))
    return True, "  ·  ".join(parts)


LAST = {}                                   # the login answer and the user agent the panel accepted


AGENTS = [("", UA), ("VLC/3.0.20 LibVLC/3.0.20", "VLC/3.0.20 LibVLC/3.0.20"),
          ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
          ("TiviMate/5.1.6 (Android 11)", "TiviMate/5.1.6 (Android 11)"),
          ("IPTVSmartersPlayer", "IPTVSmartersPlayer"),
          ("okhttp/4.9.3", "okhttp/4.9.3"),
          ("Kodi/21.0 (Linux)", "Kodi/21.0 (Linux)")]


def browser_headers(agent):
    """What a real browser (and the requests library the IPTV apps use) sends along; some panels check for it."""
    return {"User-Agent": agent, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive"}


def unpack(raw, resp):
    enc = (resp.headers.get("Content-Encoding") or "").lower()
    try:
        if "gzip" in enc or raw[:2] == b"\x1f\x8b":
            import gzip
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            import zlib
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:  # noqa: BLE001 - then it was not compressed after all
        pass
    return raw


def fetch_head(url, agent, limit=6 * 1024 * 1024):
    """(HTTP code or exception name, text of the answer up to `limit`)"""
    try:
        req = urllib.request.Request(url, headers=browser_headers(agent))
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, unpack(resp.read(limit), resp).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except Exception as error:  # noqa: BLE001
        return type(error).__name__, ""


def probe_m3u(server, user, password, output, busy=None):
    """Fetch the channel list ourselves, trying what providers are picky about: the program that asks (user agent)
    and the list type. Returns (channels, note, working m3u url, user agent or '')."""
    cred = {"username": user, "password": password}
    variants = [(output, "m3u_plus"), (output, "m3u"), ("m3u8" if output == "ts" else "ts", "m3u_plus")]
    first = ""
    n = 0
    for agent_opt, agent in AGENTS:
        for out, kind in variants:
            n += 1
            if busy:
                busy.update(min(95, n * 8), t(f"Fetching the channel list… (try {n})", f"Zenderlijst ophalen… (poging {n})"))
            m3u = f"{server}/get.php?{urllib.parse.urlencode(dict(cred, type=kind, output=out))}"
            code, body = fetch_head(m3u, agent)
            if not first:
                first = str(code)
            if body and "#EXTM3U" in body[:2000]:
                count = body.count("#EXTINF")
                if count:
                    log(f"channel list ok with agent '{agent_opt or 'default'}', type={kind}, output={out}: {count} channels")
                    return count, "", m3u, agent_opt
            if code in (401, 403) and kind == "m3u_plus" and out == output:
                continue                                  # blocked for this agent: try the next agent quickly
    return 0, t(f"the server refuses the channel list (first answer: {first})",
                f"de server weigert de zenderlijst (eerste antwoord: {first})"), "", ""


API_NOTES = []                              # what the API answered, for the message when it gives nothing


def api(server, user, password, action, agent):
    url = f"{server}/player_api.php?{urllib.parse.urlencode({'username': user, 'password': password, 'action': action})}"
    code, body = fetch_head(url, agent, limit=40 * 1024 * 1024)
    try:
        data = json.loads(body) if body else None
    except ValueError:
        data = None
    if not isinstance(data, list):
        said = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body or "")).strip()[:40]
        API_NOTES.append(f"{action.replace('get_live_', '')}: {code}{' ' + said if said else ''}")
        return []
    return data


def own_m3u(server, user, password, output, agent):
    """Build the channel list ourselves through player_api.php (what the apps do): the panels that refuse get.php
    nearly always answer this. Returns (m3u text, channels, catch-up channels)."""
    cats = {str(c.get("category_id")): c.get("category_name") or "" for c in api(server, user, password, "get_live_categories", agent)}
    streams = api(server, user, password, "get_live_streams", agent)
    if not streams:
        return "", 0, 0
    lines = [f'#EXTM3U x-tvg-url="{server}/xmltv.php?{urllib.parse.urlencode({"username": user, "password": password})}"']
    catchup = 0
    for st in sorted(streams, key=lambda x: int(x.get("num") or 0)):
        sid = st.get("stream_id")
        if sid is None:
            continue
        name = str(st.get("name") or "").replace('"', "'").replace(",", " ")
        attrs = [f'tvg-id="{st.get("epg_channel_id") or ""}"', f'tvg-name="{name}"', f'tvg-logo="{st.get("stream_icon") or ""}"',
                 f'group-title="{cats.get(str(st.get("category_id")), "").replace(chr(34), chr(39))}"']
        if st.get("num"):
            attrs.append(f'tvg-chno="{st.get("num")}"')
        if str(st.get("tv_archive")) == "1":
            days = st.get("tv_archive_duration") or 1
            attrs.append(f'catchup="xc" catchup-days="{days}"')
            catchup += 1
        lines.append(f"#EXTINF:-1 {' '.join(attrs)},{name}")
        lines.append(f"{server}/live/{urllib.parse.quote(user)}/{urllib.parse.quote(password)}/{sid}.{output}")
    return "\n".join(lines) + "\n", len(streams), catchup


M3U_DIR = "special://profile/addon_data/skin.lucent/"
LOGIN_FILE = M3U_DIR + "xtream.json"


def save_login(server, user, password, output, agent, path):
    xbmcvfs.mkdirs(M3U_DIR)
    with xbmcvfs.File(LOGIN_FILE, "w") as fh:
        fh.write(json.dumps({"server": server, "user": user, "password": password, "output": output, "agent": agent, "m3u": path}))


def refresh_file():
    """Once a day (from the Lucent helper): build the channel list again, so new channels of the provider come in."""
    if not xbmcvfs.exists(LOGIN_FILE):
        return
    try:
        with xbmcvfs.File(LOGIN_FILE) as fh:
            cfg = json.loads(fh.read() or "{}")
        text, count, _cu = own_m3u(cfg["server"], cfg["user"], cfg["password"], cfg.get("output", "ts"), cfg.get("agent") or UA)
        if count:
            with xbmcvfs.File(cfg["m3u"], "w") as fh:
                fh.write(text)
            log(f"channel list refreshed: {count} channels")
    except Exception as error:  # noqa: BLE001
        log(f"refresh: {type(error).__name__}")


def probe_epg(server, user, password):
    """The guide link that works (xmltv.php, else the lite-panel variant), with the agent: ('' when none works)."""
    cred = urllib.parse.urlencode({"username": user, "password": password})
    for name in ("xmltv.php", "get_litepanels_xmltv.php"):
        for _opt, agent in AGENTS:
            code, body = fetch_head(f"{server}/{name}?{cred}", agent)
            if body and "<tv" in body[:4000]:
                return f"{server}/{name}?{cred}", _opt
    return "", ""


def strip_secrets(text):
    return re.sub(r"(username|password)=[^&\s\"']*", r"\1=***", text)


def iptv_log_lines(limit=3):
    """What IPTV Simple complained about lately (Kodi's log, without any logins)."""
    try:
        path = xbmcvfs.translatePath("special://logpath/kodi.log")
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 600 * 1024))
            tail = fh.read().decode("utf-8", "replace").splitlines()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for line in reversed(tail):
        low = line.lower()
        if "iptvsimple" in low and ("error" in low or "unable" in low or "fail" in low or "warning" in low):
            out.append(strip_secrets(line.split("]: ", 1)[-1].split(": ", 1)[-1])[:140])
            if len(out) >= limit:
                break
    return out


def links(server, user, password, output):
    cred = {"username": user, "password": password}
    m3u = f"{server}/get.php?{urllib.parse.urlencode(dict(cred, type='m3u_plus', output=output))}"
    epg = f"{server}/xmltv.php?{urllib.parse.urlencode(cred)}"
    return m3u, epg


# ----------------------------------------------------------------------------- IPTV Simple's instance settings
def instance_files():
    """[(number, path)] of IPTV Simple's add-on instances (Kodi 20+ keeps one file per instance)."""
    out = []
    if xbmcvfs.exists(DATA):
        _dirs, files = xbmcvfs.listdir(DATA)
        for name in files:
            m = re.match(r"instance-settings-(\d+)\.xml$", name)
            if m:
                out.append((int(m.group(1)), DATA + name))
    return sorted(out)


def read_settings(path):
    values = {}
    if path and xbmcvfs.exists(path):
        with xbmcvfs.File(path) as fh:
            raw = fh.read()
        try:
            for node in ET.fromstring(raw).iter("setting"):
                if node.get("id"):
                    values[node.get("id")] = node.text or ""
        except ET.ParseError:
            pass
    return values


def write_settings(path, values):
    root = ET.Element("settings", version="2")
    for key, value in values.items():
        node = ET.SubElement(root, "setting", id=key)
        node.text = value
    raw = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"
    xbmcvfs.mkdirs(DATA)
    with xbmcvfs.File(path, "w") as fh:
        fh.write(raw)


def pick_instance(server):
    """Which instance file to write: the existing one (replace) or a new one. None = cancelled."""
    existing = instance_files()
    if not existing:
        return DATA + "instance-settings-1.xml", True
    names = []
    for num, path in existing:
        values = read_settings(path)
        label = values.get("kodi_addon_instance_name") or f"#{num}"
        host = urllib.parse.urlsplit(values.get("m3uUrl") or "").hostname or ""
        names.append(label + (f"  ·  {host}" if host else ""))
    choices = [t(f"Replace: {n}", f"Vervangen: {n}") for n in names] + [t("Add as a new list", "Toevoegen als nieuwe lijst")]
    pick = xbmcgui.Dialog().select(t("IPTV Simple already has a channel list", "IPTV Simple heeft al een zenderlijst"), choices)
    if pick < 0:
        return None, False
    if pick < len(existing):
        return existing[pick][1], False
    return DATA + f"instance-settings-{existing[-1][0] + 1}.xml", True


def apply(path, fresh, server, m3u, epg, output, local=False, agent=""):
    values = read_settings(path) if not fresh else {}
    host = urllib.parse.urlsplit(server).hostname or "xtream"
    values.update({
        "kodi_addon_instance_name": f"Xtream · {host}",
        "kodi_addon_instance_enabled": "true",
        "m3uPathType": "0" if local else "1", "m3uPath" if local else "m3uUrl": m3u, "m3uCache": "true",
        "m3uRefreshMode": "2", "m3uRefreshHour": "4",            # the list is fetched again once a day, at night
        "epgPathType": "1", "epgUrl": epg, "epgCache": "true",
        "epgTSOverride": "false",
        "catchupEnabled": "true",                                   # replay: Xtream builds the links for it
        "allChannelsCatchupMode": "5",                              # 5 = Xtream codes
        "useFFmpegReconnect": "true",
    })
    values.pop("m3uUrl" if local else "m3uPath", None)
    if agent:
        values["defaultUserAgent"] = agent                  # the streams are asked the way the panel accepts
    if fresh:
        values.setdefault("startNum", "1")
        values.setdefault("numberByOrder", "false")
        values.setdefault("epgTimeShift", "0")
        values.setdefault("useInputstreamAdaptiveforHls", "true" if output == "m3u8" else "false")
    write_settings(path, values)
    # the add-on clears its own caches when you change a setting in its dialog; we wrote the file, so do it here
    num = re.search(r"instance-settings-(\d+)\.xml$", path).group(1)
    for name in (f"iptv.m3u.cache-{num}", f"xmltv.xml.cache-{num}", "iptv.m3u.cache", "xmltv.xml.cache"):
        if xbmcvfs.exists(DATA + name):
            xbmcvfs.delete(DATA + name)


def enabled():
    return xbmc.getCondVisibility(f"System.AddonIsEnabled({IPTV})")


def wait_until(check, seconds, monitor):
    for _ in range(int(seconds * 2)):
        if check():
            return True
        if monitor.waitForAbort(0.5):
            return False
    return check()


def channel_count():
    result = rpc("PVR.GetChannels", {"channelgroupid": "alltv", "limits": {"end": 1}}) or {}
    return int((result.get("limits") or {}).get("total") or 0)


def restart_addon(busy):
    """IPTV Simple reads its instance files when it starts: switch it off, wait until Kodi's TV part has really let go
    of it, switch it on again and wait for the channels. Kodi needs a while for this; too quick and the 'on' is lost."""
    monitor = xbmc.Monitor()
    busy.update(10, t("Stopping IPTV Simple…", "IPTV Simple stoppen…"))
    rpc("Addons.SetAddonEnabled", {"addonid": IPTV, "enabled": False})
    wait_until(lambda: not enabled(), 20, monitor)
    monitor.waitForAbort(4)                                 # the PVR manager finishes stopping the client
    busy.update(30, t("Starting IPTV Simple…", "IPTV Simple starten…"))
    for attempt in range(3):
        rpc("Addons.SetAddonEnabled", {"addonid": IPTV, "enabled": True})
        if wait_until(enabled, 10, monitor):
            break
        log(f"enable attempt {attempt + 1} did not stick")
    if not enabled():
        return "off"
    for n in range(90):                                    # up to 45 s for the first channels
        count = channel_count()
        busy.update(40 + n // 2, t(f"Loading channels… {count}", f"Zenders laden… {count}"))
        if count:
            return "ok"
        if busy.iscanceled() or monitor.waitForAbort(0.5):
            break
    return "nochannels"


# ----------------------------------------------------------------------------- the flow
def run():
    if not xbmc.getCondVisibility(f"System.HasAddon({IPTV})"):
        if xbmcgui.Dialog().yesno("Xtream", t("IPTV Simple Client is not installed yet. Install it first?",
                                              "IPTV Simple Client staat er nog niet op. Eerst installeren?")):
            xbmc.executebuiltin(f"InstallAddon({IPTV})")
        return
    dialog = xbmcgui.Dialog()
    dialog.ok("Xtream", t("Your IPTV provider gave you three things: a server address (like http://host:8080), "
                          "a user name and a password. Fill them in on the next screens.",
                          "Van je IPTV-aanbieder heb je drie dingen gekregen: een serveradres (zoals http://host:8080), "
                          "een gebruikersnaam en een wachtwoord. Vul die op de volgende schermen in."))
    server = clean_server(ask(t("Server address", "Serveradres"), "http://"))
    if not server:
        return
    user = ask(t("User name", "Gebruikersnaam"))
    if not user:
        return
    password = ask(t("Password", "Wachtwoord"), hidden=True)
    if not password:
        return
    busy = xbmcgui.DialogProgress()
    busy.create("Xtream", t("Checking the login with the server…", "Inloggen controleren bij de server…"))
    ok, message = check(server, user, password)
    busy.close()
    if not ok:
        if dialog.yesno("Xtream", message + "\n\n" + t("Save anyway?", "Toch opslaan?")):
            ok = True
        else:
            return
    output = ("ts", "m3u8")[dialog.select(t("Stream type", "Soort stream"),
                                          [t("TS (most providers, best quality)", "TS (meeste aanbieders, beste kwaliteit)"),
                                           t("HLS / m3u8 (when TS stutters)", "HLS / m3u8 (als TS hapert)")]) == 1]
    path, fresh = pick_instance(server)
    if not path:
        return
    m3u, epg = links(server, user, password, output)
    busy = xbmcgui.DialogProgress()
    busy.create("Xtream", t("Fetching the channel list from the server…", "Zenderlijst ophalen bij de server…"))
    count, note, good_m3u, agent = probe_m3u(server, user, password, output, busy)
    busy.close()
    if good_m3u:
        m3u = good_m3u
        if agent:                                        # IPTV Simple must ask the same way (Kodi's |User-Agent= option)
            m3u += "|User-Agent=" + urllib.parse.quote(agent)
            epg += "|User-Agent=" + urllib.parse.quote(agent)
    local = False
    if count <= 0:
        # the panel refuses get.php: build the list ourselves through player_api (the way the IPTV apps do it)
        busy = xbmcgui.DialogProgress()
        busy.create("Xtream", t("The server refuses the list; building it ourselves…", "De server weigert de lijst; zelf opbouwen…"))
        agent = LAST.get("agent") or UA
        text, count, cu = own_m3u(server, user, password, output, agent)
        busy.close()
        if count:
            host = urllib.parse.urlsplit(server).hostname or "xtream"
            m3u = M3U_DIR + f"xtream-{re.sub(r'[^A-Za-z0-9.-]', '_', host)}.m3u"
            xbmcvfs.mkdirs(M3U_DIR)
            with xbmcvfs.File(m3u, "w") as fh:
                fh.write(text)
            save_login(server, user, password, output, agent, m3u)
            local = True
            message += "\n" + t(f"Channel list built by Lucent: {count} channels ({cu} with replay)",
                                 f"Zenderlijst door Lucent opgebouwd: {count} zenders ({cu} met terugkijken)")
            epg_url, epg_agent = probe_epg(server, user, password)
            epg = epg_url + ("|User-Agent=" + urllib.parse.quote(epg_agent) if epg_agent else "") if epg_url else ""
            if not epg_url:
                message += "\n" + t("No TV guide: the server refuses it", "Geen tv-gids: de server weigert hem")
        elif not dialog.yesno("Xtream", t(f"Channel list: {note}.", f"Zenderlijst: {note}.") + "\n" +
                              t("API: ", "API: ") + (" | ".join(API_NOTES[-2:]) or "-") + "\n\n" +
                              t("The server also gives no channels through its API. Save anyway?",
                                "De server geeft ook via zijn API geen zenders. Toch opslaan?")):
            log(f"api refused: {API_NOTES[-2:]}")
            return
    else:
        message += "\n" + t(f"Channel list: {count} channels", f"Zenderlijst: {count} zenders")
    try:
        apply(path, fresh, server, m3u, epg, output, local, (LAST.get("agent") or "") if local else agent)
    except Exception as error:  # noqa: BLE001
        log(f"could not write the settings: {type(error).__name__}")
        dialog.ok("Xtream", t("Could not write IPTV Simple's settings.", "Kon de instellingen van IPTV Simple niet opslaan."))
        return
    log(f"settings written to {path.rsplit('/', 1)[-1]} ({urllib.parse.urlsplit(server).hostname})")
    busy = xbmcgui.DialogProgress()
    busy.create("Xtream", t("Restarting IPTV Simple…", "IPTV Simple opnieuw starten…"))
    try:
        state = restart_addon(busy)
    finally:
        busy.close()
    if state == "ok":
        dialog.ok("Xtream", message + "\n\n" + t(f"IPTV Simple is set up: {channel_count()} channels. The guide can take a "
                                                 "few minutes the first time.",
                                                 f"IPTV Simple is ingesteld: {channel_count()} zenders. De gids kan de eerste "
                                                 "keer een paar minuten duren."))
        return
    why = t("IPTV Simple did not come back on.", "IPTV Simple is niet meer aangegaan.") if state == "off" else \
        t("IPTV Simple is on, but no channels came in yet (a big list can take a minute).",
          "IPTV Simple staat aan, maar er zijn nog geen zenders binnen (een grote lijst kan een minuut duren).")
    said = iptv_log_lines()
    if said:
        why += "\n" + t("IPTV Simple says: ", "IPTV Simple meldt: ") + " | ".join(said)
    log(f"no channels after setup; iptvsimple log: {said}")
    if dialog.yesno("Xtream", why + "\n\n" + t("The settings are saved. Restart Kodi now so it loads the channels cleanly?",
                                                 "De instellingen zijn opgeslagen. Kodi nu opnieuw starten, zodat hij de zenders "
                                                 "schoon laadt?")):
        xbmc.executebuiltin("RestartApp")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        refresh_file()
    else:
        run()
