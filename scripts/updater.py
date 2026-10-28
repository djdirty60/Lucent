# -*- coding: utf-8 -*-
"""Lucent: pop-up when a new version of Lucent (or the Lucent screensaver) is in the repository.

RunScript(special://skin/scripts/updater.py,service)   background helper, started from the Home screen
RunScript(special://skin/scripts/updater.py,check)     look now (Skin settings > Add-ons > Check for updates)

The pop-up offers: Update now / Later / Skip this version. "Update now" refreshes the repositories and installs the new version.
"""
import json
import re
import sys
import time
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

HEADING = "Lucent"
ADDONS_XML = "https://raw.githubusercontent.com/djdirty60/Lucent/main/repo/addons.xml"
WATCH = ("skin.lucent", "screensaver.lucent")        # add-ons of this repository that are checked when installed
STATE_PATH = "special://profile/addon_data/skin.lucent/update_state.json"
RUNNING = "nuvio.update.running"
CHECK_EVERY = 6 * 3600
HOME = xbmcgui.Window(10000)
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"

T = {
    "title": ("{0} {1} is available", "{0} {1} is beschikbaar"),
    "installed": ("You have {0}.", "Je hebt nu {0}."),
    "new": ("What's new:", "Nieuw:"),
    "now": ("Update now", "Nu bijwerken"),
    "later": ("Later", "Later"),
    "skip": ("Skip this version", "Deze versie overslaan"),
    "busy": ("Updating {0}…", "{0} wordt bijgewerkt…"),
    "uptodate": ("Everything is up to date", "Alles is up-to-date"),
    "offline": ("Could not check for updates", "Kon niet op updates controleren"),
}


def tr(key, *args):
    text = T[key][1 if NL else 0]
    return text.format(*args) if args else text


def log(text):
    xbmc.log(f"[skin.lucent update] {text}", xbmc.LOGINFO)


def read_state():
    try:
        if xbmcvfs.exists(STATE_PATH):
            with xbmcvfs.File(STATE_PATH) as fh:
                data = json.loads(fh.read())
            if isinstance(data, dict):
                return data
    except Exception as error:  # noqa: BLE001 - a broken file must never break the skin
        log(f"state: {error}")
    return {}


def write_state(state):
    try:
        folder = STATE_PATH.rsplit("/", 1)[0] + "/"
        if not xbmcvfs.exists(folder):
            xbmcvfs.mkdirs(folder)
        with xbmcvfs.File(STATE_PATH, "w") as fh:
            fh.write(json.dumps(state))
    except Exception as error:  # noqa: BLE001
        log(f"cannot write state: {error}")


def version_key(version):
    return tuple(int(x) for x in re.findall(r"\d+", version))


def installed_version(addon_id):
    try:
        return xbmcaddon.Addon(addon_id).getAddonInfo("version")
    except Exception:  # noqa: BLE001 - not installed
        return ""


def fetch_available():
    """{addon id: (version, news)} from the repository."""
    request = urllib.request.Request(ADDONS_XML, headers={"User-Agent": "skin.lucent (Kodi)"})
    with urllib.request.urlopen(request, timeout=20) as response:
        xml = response.read().decode("utf-8")
    found = {}
    for block in re.finditer(r'<addon\s[^>]*?id="([^"]+)"[^>]*?version="([^"]+)".*?</addon>', xml, re.S):
        news = re.search(r"<news>(.*?)</news>", block.group(0), re.S)
        found[block.group(1)] = (block.group(2), (news.group(1).strip() if news else ""))
    return found


def release_notes(news, installed, limit=4):
    """The lines of <news> that are newer than the installed version."""
    parts = [p.strip() for p in re.split(r"\s(?=\d+\.\d+(?:\.\d+)?:)", news) if p.strip()]
    keep = []
    for part in parts:
        match = re.match(r"(\d+(?:\.\d+)+):", part)
        if match and installed and version_key(match.group(1)) <= version_key(installed):
            break
        keep.append(part)
    return "\n".join(keep[:limit])


def available_updates():
    available = fetch_available()
    out = []
    for addon_id in WATCH:
        have = installed_version(addon_id)
        if not have or addon_id not in available:
            continue
        version, news = available[addon_id]
        if version_key(version) > version_key(have):
            out.append({"id": addon_id, "name": xbmcaddon.Addon(addon_id).getAddonInfo("name"), "have": have, "version": version,
                        "notes": release_notes(news, have)})
    return out


def ask(update):
    message = tr("installed", update["have"])
    if update["notes"]:
        message += "\n\n" + tr("new") + "\n" + update["notes"]
    answer = xbmcgui.Dialog().yesnocustom(tr("title", update["name"], update["version"]), message,
                                          tr("skip"), tr("later"), tr("now"), defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
    return {1: "now", 0: "later", 2: "skip"}.get(answer, "later")


def install(update, monitor):
    xbmcgui.Dialog().notification(HEADING, tr("busy", update["name"]), xbmcgui.NOTIFICATION_INFO, 5000)
    xbmc.executebuiltin("UpdateAddonRepos")
    monitor.waitForAbort(8)                           # give Kodi a moment to learn about the new version
    xbmc.executebuiltin(f"InstallAddon({update['id']})")


def check(manual=False):
    monitor = xbmc.Monitor()
    try:
        updates = available_updates()
    except Exception as error:  # noqa: BLE001 - offline, GitHub down, ...
        log(f"check failed: {error}")
        if manual:
            xbmcgui.Dialog().notification(HEADING, tr("offline"), xbmcgui.NOTIFICATION_WARNING, 4000)
        return
    state = read_state()
    shown = False
    for update in updates:
        if not manual and (state.get("skip", {}).get(update["id"]) == update["version"]
                           or state.get("later", {}).get(update["id"], 0) > time.time()):
            continue
        if xbmc.getCondVisibility("Player.HasMedia"):    # never interrupt a film
            if not manual:
                continue
        shown = True
        choice = ask(update)
        if choice == "now":
            install(update, monitor)
        elif choice == "skip":
            state.setdefault("skip", {})[update["id"]] = update["version"]
        else:
            state.setdefault("later", {})[update["id"]] = time.time() + 24 * 3600
    write_state(state)
    if manual and not shown and not updates:
        xbmcgui.Dialog().notification(HEADING, tr("uptodate"), xbmcgui.NOTIFICATION_INFO, 3000)


def running():
    try:
        return time.time() - float(HOME.getProperty(RUNNING) or 0) < 30 * 60
    except ValueError:
        return False


def run_service():
    if running():
        return
    monitor = xbmc.Monitor()
    HOME.setProperty(RUNNING, f"{time.time():.1f}")
    if monitor.waitForAbort(90):                         # let Kodi finish starting up first
        return
    while not monitor.abortRequested():
        HOME.setProperty(RUNNING, f"{time.time():.1f}")
        if not xbmc.getCondVisibility("Skin.HasSetting(nuvio.update.off)"):
            try:
                check()
            except Exception as error:  # noqa: BLE001 - never die silently in a loop
                log(f"service error: {error}")
        waited = 0
        while waited < CHECK_EVERY and not monitor.abortRequested():
            HOME.setProperty(RUNNING, f"{time.time():.1f}")
            if monitor.waitForAbort(600):
                break
            waited += 600
        else:
            continue
        break
    HOME.clearProperty(RUNNING)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "check"
    if arg == "service":
        run_service()
    else:
        check(manual=True)
