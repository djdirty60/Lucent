# -*- coding: utf-8 -*-
"""Lucent: pop-up when a new version of anything from Lucent is in the repository (the skin, the screensaver,
 the repository add-on, and whatever is added there later - when it is installed here).

The Lucent helper (helper.py) calls check() every 6 hours.
RunScript(special://skin/scripts/updater.py,check)     look now (Skin settings > Add-ons > Check for updates)

All updates come in one pop-up: Update now / Later / Skip these versions. "Update now" refreshes the repositories and installs the new version.
"""
import json
import os
import re
import time
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

HEADING = "Lucent"
ADDONS_XML = "https://raw.githubusercontent.com/djdirty60/Lucent/main/repo/addons.xml"
ZIPS_URL = "https://raw.githubusercontent.com/djdirty60/Lucent/main/repo/zips/"
# 2.1.0: the second source of the Lucent repository (the video add-on publishes itself there)
SOURCES = [(ADDONS_XML, ZIPS_URL),
           ("https://raw.githubusercontent.com/djdirty60/Lucent-video/main/repo/addons.xml",
            "https://raw.githubusercontent.com/djdirty60/Lucent-video/main/repo/zips/")]
# every add-on in the Lucent repository that is installed here is kept up to date (also the ones installed from a
# zip, which Kodi itself does not update from this repository), whatever its name
STATE_PATH = "special://profile/addon_data/skin.lucent/update_state.json"
HOME = xbmcgui.Window(10000)
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"

T = {
    "title": ("{0} {1} is available", "{0} {1} is beschikbaar"),
    "titles": ("{0} updates for Lucent", "{0} updates voor Lucent"),
    "skips": ("Skip these versions", "Deze versies overslaan"),
    "installed": ("You have {0}.", "Je hebt nu {0}."),
    "new": ("What's new:", "Nieuw:"),
    "now": ("Update now", "Nu bijwerken"),
    "later": ("Later", "Later"),
    "skip": ("Skip this version", "Deze versie overslaan"),
    "busy": ("Updating {0}…", "{0} wordt bijgewerkt…"),
    "uptodate": ("Everything is up to date", "Alles is up-to-date"),
    "done": ("{0} {1} installed", "{0} {1} is geïnstalleerd"),
    "failed": ("Update failed, Kodi will try it again by itself", "Bijwerken mislukt, Kodi probeert het zelf opnieuw"),
    "offline": ("Could not check for updates", "Kon niet op updates controleren"),
    "restart_title": ("Restart Kodi", "Kodi herstarten"),
    "restart_text": ("{0} has new texts. Kodi shows them after a restart; until then some settings may have no name.",
                     "{0} heeft nieuwe teksten. Kodi laat die pas zien na een herstart; tot dan kunnen sommige instellingen zonder naam staan."),
    "restart_now": ("Restart now", "Nu herstarten"),
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
    """1.0.0~beta1 < 1.0.0~beta1+5 < 1.0.0~beta2 < 1.0.0 < 1.0.1 (Kodi's own order: a ~ version comes before the final
    one). Also the words of a news line: '1.0.0 beta 1, update 5' = 1.0.0~beta1+5."""
    version = re.sub(r"\s*beta\s*(\d+)(?:,?\s*update\s*(\d+))?", lambda m: f"~beta{m.group(1)}" + (f"+{m.group(2)}" if m.group(2) else ""),
                     str(version), flags=re.I)
    base, _sep, pre = version.partition("~")
    nums = [int(x) for x in re.findall(r"\d+", base)][:4]
    nums += [0] * (4 - len(nums))
    if not pre:
        return tuple(nums) + (1, 0, 0)
    pre_nums = [int(x) for x in re.findall(r"\d+", pre)][:2]
    pre_nums += [0] * (2 - len(pre_nums))
    return tuple(nums) + (0,) + tuple(pre_nums)


def installed_version(addon_id):
    if not xbmc.getCondVisibility(f"System.HasAddon({addon_id})"):
        return ""                                        # not installed: no 'Unknown addon id' in the log
    try:
        return xbmcaddon.Addon(addon_id).getAddonInfo("version")
    except Exception:  # noqa: BLE001 - not installed
        return ""


def fetch_available():
    """{addon id: (version, news, address of its zips)} from the sources of the Lucent repository. The first source
    (the skin) must answer; a second source that does not answer is skipped."""
    found = {}
    for n, (addons_xml, zips) in enumerate(SOURCES):
        try:
            # a new address every time: GitHub's cache could otherwise give the list of a few minutes ago
            request = urllib.request.Request(f"{addons_xml}?t={int(time.time())}",
                                             headers={"User-Agent": "skin.lucent (Kodi)", "Cache-Control": "no-cache"})
            with urllib.request.urlopen(request, timeout=20) as response:
                xml = response.read().decode("utf-8")
        except Exception as error:  # noqa: BLE001
            if n == 0:
                raise
            log(f"source {n + 1}: {error}")
            continue
        for block in re.finditer(r'<addon\s[^>]*?id="([^"]+)"[^>]*?version="([^"]+)".*?</addon>', xml, re.S):
            news = re.search(r"<news>(.*?)</news>", block.group(0), re.S)
            # 2.1.8: a <news lang="nl_NL"> in the language of Kodi wins (Lucent Video has Dutch notes); else <news>
            lang = (xbmc.getLanguage(xbmc.ISO_639_1) or "").lower()[:2]
            if lang:
                for own in re.finditer(r'<news\s+lang="([a-zA-Z]{2})[^"]*">(.*?)</news>', block.group(0), re.S):
                    if own.group(1).lower() == lang and own.group(2).strip():
                        news = own
                        break
            text = (news.group(news.lastindex).strip() if news else "")
            found.setdefault(block.group(1), (block.group(2), text, zips))
    return found


def release_notes(news, installed, limit=4):
    """The lines of <news> that are newer than the installed version."""
    head = r"\d+\.\d+(?:\.\d+)?(?:~[\w.+]+| beta \d+(?:, update \d+)?)?:"     # 2.1.3: '1.0.0 beta 1, update 5:' too
    parts = [p.strip() for p in re.split(rf"\s(?={head})", news) if p.strip()]
    keep = []
    for part in parts:
        match = re.match(r"(\d+(?:\.\d+)+(?:~[\w.+]+| beta \d+(?:, update \d+)?)?):", part)
        if match and installed and version_key(match.group(1)) <= version_key(installed):
            break
        keep.append(part)
    return "\n".join(keep[:limit])


# add-ons in the repository that this window leaves alone: Kodi keeps them up to date by itself, without a message
SILENT = set()                                           # 2.1.0: the video add-on is in this window too


def available_updates():
    available = fetch_available()
    out = []
    for addon_id in sorted(available):
        if addon_id in SILENT:
            continue                                     # updated quietly by Kodi itself, never in this window
        have = installed_version(addon_id)
        if not have:
            continue                                     # not installed here: never pushed on you
        version, news, zips = available[addon_id]
        if version_key(version) > version_key(have):
            out.append({"id": addon_id, "name": xbmcaddon.Addon(addon_id).getAddonInfo("name"), "have": have, "version": version, "zips": zips,
                        "notes": release_notes(news, have, limit=4 if addon_id == "skin.lucent" else 2)})
    # the skin last: installing it reloads the skin
    return sorted(out, key=lambda u: u["id"] == "skin.lucent")


def ask(updates):
    if len(updates) == 1:
        update = updates[0]
        title = tr("title", update["name"], update["version"])
        message = tr("installed", update["have"])
        if update["notes"]:
            message += "\n\n" + tr("new") + "\n" + update["notes"]
        skip = tr("skip")
    else:
        title = tr("titles", len(updates))
        lines = []
        for update in updates:
            lines.append(f"[B]{update['name']} {update['version']}[/B]  ({tr('installed', update['have']).rstrip('.')})")
            if update["notes"]:
                lines.append(update["notes"].split("\n")[0][:220])
        message = "\n".join(lines)
        skip = tr("skips")
    answer = xbmcgui.Dialog().yesnocustom(title, message, skip, tr("later"), tr("now"), autoclose=60000,
                                          defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)   # no answer within a minute: later
    return {1: "now", 0: "later", 2: "skip"}.get(answer, "later")


def download_zip(update):
    """Download the new version to a temporary file and return its path."""
    url = f"{update.get('zips') or ZIPS_URL}{update['id']}/{update['id']}-{update['version']}.zip"
    target = xbmcvfs.translatePath(f"special://temp/{update['id']}-{update['version']}.zip")
    request = urllib.request.Request(f"{url}?t={int(time.time())}", headers={"User-Agent": "skin.lucent (Kodi)", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=60) as response, open(target, "wb") as out:
        import shutil
        shutil.copyfileobj(response, out)
    return target


def _texts(folder):
    """The text files of an add-on (resources/language/*/strings.po) and their contents, to see if they changed."""
    out = {}
    base = os.path.join(folder, "resources", "language")
    for root, _dirs, files in os.walk(base):
        for name in files:
            if name.endswith(".po"):
                try:
                    with open(os.path.join(root, name), "rb") as fh:
                        out[os.path.relpath(os.path.join(root, name), base)] = fh.read()
                except OSError:
                    pass
    return out


def unpack(update, zip_path):
    """Replace the add-on folder by the one in the zip (the old one is kept until the new one is in place).
    Returns True when its texts changed: Kodi only reads those again after a restart (2.1.8)."""
    import shutil
    import zipfile
    addons = xbmcvfs.translatePath("special://home/addons/")
    staging = os.path.join(addons, f".{update['id']}.new")
    shutil.rmtree(staging, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if f"{update['id']}/addon.xml" not in names:
            raise RuntimeError("zip has no addon.xml")
        archive.extractall(staging)
    unpacked = os.path.join(staging, update["id"])
    with open(os.path.join(unpacked, "addon.xml"), encoding="utf-8") as fh:
        if f'version="{update["version"]}"' not in fh.read():
            raise RuntimeError("zip has another version")
    folder = os.path.join(addons, update["id"])
    texts_changed = _texts(folder) != _texts(unpacked)
    backup = folder + ".old"
    shutil.rmtree(backup, ignore_errors=True)
    if os.path.isdir(folder):
        os.rename(folder, backup)
    try:
        os.rename(unpacked, folder)
    except Exception:
        if os.path.isdir(backup) and not os.path.isdir(folder):
            os.rename(backup, folder)                   # put the old version back
        raise
    shutil.rmtree(backup, ignore_errors=True)
    shutil.rmtree(staging, ignore_errors=True)
    return texts_changed


def install(update, monitor):
    """Returns True when the add-on got new texts (then Kodi should restart to show them)."""
    progress = xbmcgui.DialogProgressBG()
    progress.create(HEADING, tr("busy", update["name"]))
    try:
        zip_path = download_zip(update)
        progress.update(60)
        texts_changed = unpack(update, zip_path)
        try:
            os.remove(zip_path)
        except OSError:
            pass
    except Exception as error:  # noqa: BLE001 - fall back to Kodi's own update
        log(f"direct update failed: {error}")
        progress.close()
        xbmcgui.Dialog().notification(HEADING, tr("failed"), xbmcgui.NOTIFICATION_WARNING, 5000)
        xbmc.executebuiltin("UpdateAddonRepos")
        return False
    progress.update(90)
    xbmc.executebuiltin("UpdateLocalAddons")             # Kodi reads the new addon.xml
    monitor.waitForAbort(3)
    if update["id"] != "skin.lucent":
        restart(update["id"], monitor)
    progress.close()
    xbmcgui.Dialog().notification(HEADING, tr("done", update["name"], update["version"]), xbmcgui.NOTIFICATION_INFO, 5000)
    # the skin reads its own texts again with ReloadSkin (check() does that last); other add-ons need a restart
    return texts_changed and update["id"] != "skin.lucent"


def reload_skin(monitor):
    monitor.waitForAbort(2)
    xbmcgui.Window(10000).setProperty("lucent.helper.stop", "1")   # the running helper makes way for the new code
    xbmcgui.Window(10000).clearProperty("nuvio.started")           # Home runs its start-up (and the new helper) again
    xbmc.executebuiltin("ReloadSkin()")             # show the new version right away


def ask_restart(names):
    """2.1.8: an add-on got new texts. Kodi only loads texts at start, so offer a restart (Restart now / Later)."""
    return xbmcgui.Dialog().yesno(tr("restart_title"), tr("restart_text", " · ".join(names)),
                                  nolabel=tr("later"), yeslabel=tr("restart_now"))


def rpc(method, params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result")
    except Exception as error:  # noqa: BLE001
        log(f"rpc {method}: {error}")
        return None


def restart(addon_id, monitor):
    """Switch an add-on off and on again, so a background part (like the service of the video add-on) starts with
    the new code right away instead of after a Kodi restart. Only for add-ons that have such a background part."""
    try:
        folder = xbmcvfs.translatePath(f"special://home/addons/{addon_id}/addon.xml")
        with open(folder, encoding="utf-8") as fh:
            if "xbmc.service" not in fh.read():
                return                                   # nothing runs in the background: nothing to restart
    except OSError:
        return
    rpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": False})
    monitor.waitForAbort(1)
    rpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True})


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
    if not manual:
        updates = [u for u in updates if state.get("skip", {}).get(u["id"]) != u["version"]
                   and state.get("later", {}).get(u["id"], 0) <= time.time()]
    if not updates:
        write_state(state)
        if manual:
            xbmcgui.Dialog().notification(HEADING, tr("uptodate"), xbmcgui.NOTIFICATION_INFO, 3000)
        return
    if not manual and xbmc.getCondVisibility("Player.HasMedia | System.ScreenSaverActive | System.HasModalDialog"):
        return                                           # never interrupt a film, the screensaver or another dialog
    choice = ask(updates)
    new_texts, skin = [], False
    for update in sorted(updates, key=lambda u: u["id"] == "skin.lucent"):     # the skin last (it reloads)
        if choice == "now":
            if install(update, monitor):
                new_texts.append(update["name"])
            skin = skin or update["id"] == "skin.lucent"
        elif choice == "skip":
            state.setdefault("skip", {})[update["id"]] = update["version"]
        else:
            state.setdefault("later", {})[update["id"]] = time.time() + 24 * 3600
    write_state(state)
    if new_texts and ask_restart(new_texts):
        xbmc.executebuiltin("RestartApp")
        return
    if skin:
        reload_skin(monitor)

if __name__ == "__main__":
    check(manual=True)
