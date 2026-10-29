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
    """What the server says about this login: (ok, message)."""
    url = f"{server}/player_api.php?{urllib.parse.urlencode({'username': user, 'password': password})}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except Exception as error:  # noqa: BLE001
        kind = type(error).__name__
        log(f"server did not answer ({kind})")
        return False, t(f"The server did not answer ({kind}). Check the address.",
                        f"De server antwoordt niet ({kind}). Controleer het adres.")
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


def apply(path, fresh, server, m3u, epg, output):
    values = read_settings(path) if not fresh else {}
    host = urllib.parse.urlsplit(server).hostname or "xtream"
    values.update({
        "kodi_addon_instance_name": f"Xtream · {host}",
        "kodi_addon_instance_enabled": "true",
        "m3uPathType": "1", "m3uUrl": m3u, "m3uCache": "true",
        "m3uRefreshMode": "2", "m3uRefreshHour": "4",            # the list is fetched again once a day, at night
        "epgPathType": "1", "epgUrl": epg, "epgCache": "true",
        "catchupEnabled": "true",                                   # replay: Xtream builds the links for it
        "allChannelsCatchupMode": "5",                              # 5 = Xtream codes
        "useFFmpegReconnect": "true",
    })
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
    try:
        apply(path, fresh, server, m3u, epg, output)
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
    if dialog.yesno("Xtream", why + "\n\n" + t("The settings are saved. Restart Kodi now so it loads the channels cleanly?",
                                                 "De instellingen zijn opgeslagen. Kodi nu opnieuw starten, zodat hij de zenders "
                                                 "schoon laadt?")):
        xbmc.executebuiltin("RestartApp")


if __name__ == "__main__":
    run()
