# -*- coding: utf-8 -*-
"""Lucent: backup and restore of everything you set up.

    RunScript(special://skin/scripts/backup.py)            a small menu: make a backup / restore
    RunScript(special://skin/scripts/backup.py,backup)     make one now
    RunScript(special://skin/scripts/backup.py,restore)    put one back

One zip file with: Lucent's settings and menu (skin settings), its own files (keys, calendar, sport, favourites of the
guide ...), Kodi's favourites, sources and advancedsettings, the keymaps Lucent writes, and the settings of Seren,
IPTV Simple, Lucent Library and Lucent Subtitles. Not included: caches, databases and the library's .strm files (Lucent
Library writes those again by itself).

Restoring: the skin settings are put back one by one with Kodi's own commands (Kodi keeps them in memory and would
overwrite a file put back underneath it); everything else is copied back, after which Kodi restarts so add-ons read it.
Only paths under userdata/ are ever written.
"""
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

import xbmc
import xbmcgui
import xbmcvfs

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
PROFILE = "special://profile/"
LAST = "lucent.backup.last"
SKIN_SETTINGS = "addon_data/skin.lucent/settings.xml"

# what goes into the backup: single files under userdata, and folders with a rule for which files to keep
FILES = ["favourites.xml", "sources.xml", "advancedsettings.xml"]
FOLDERS = {
    "keymaps": lambda rel: rel.startswith("lucent-") and rel.endswith(".xml"),
    "addon_data/skin.lucent": lambda rel: not (rel.endswith("_cache.json") or rel.startswith("subs_ai/")
                                               or rel in ("sport_epg.json", "sport_cache.json") or rel.endswith(".tmp")),
    "addon_data/plugin.video.seren": lambda rel: rel == "settings.xml",
    "addon_data/pvr.iptvsimple": lambda rel: rel.endswith(".xml") and "/" not in rel,
    "addon_data/script.lucent.library": lambda rel: rel.endswith(".json") and "/" not in rel and rel != "busy.lock",
    "addon_data/service.subtitles.lucent": lambda rel: rel == "settings.xml",
    "addon_data/screensaver.lucent": lambda rel: rel == "settings.xml",
}


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] backup: {text}", xbmc.LOGINFO)


def real(path):
    return xbmcvfs.translatePath(PROFILE + path)


def collect():
    """[(path on disk, name in the zip)] of everything worth keeping."""
    out = []
    for rel in FILES:
        if os.path.isfile(real(rel)):
            out.append((real(rel), "userdata/" + rel))
    for folder, keep in FOLDERS.items():
        base = real(folder)
        for root, _dirs, names in os.walk(base):
            for name in names:
                full = os.path.join(root, name)
                inner = os.path.relpath(full, base).replace("\\", "/")
                if keep(inner):
                    out.append((full, f"userdata/{folder}/{inner}"))
    return out


def write_zip(folder, prefix):
    """Zip everything worth keeping into folder; returns (target path, number of files). Raises OSError when it fails."""
    name = time.strftime(f"{prefix}-%Y%m%d-%H%M.zip")
    temp = xbmcvfs.translatePath("special://temp/" + name)
    files = collect()
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("lucent-backup.txt", f"Lucent backup {time.strftime('%Y-%m-%d %H:%M')}\n"
                                                  f"Kodi {xbmc.getInfoLabel('System.BuildVersion')}\n")
            for full, inner in files:
                archive.write(full, inner)
        target = folder.rstrip("/\\") + "/" + name
        if not xbmcvfs.copy(temp, target):
            raise OSError(t("could not write to that folder", "kon niet naar die map schrijven"))
    finally:
        try:
            os.remove(temp)
        except OSError:
            pass
    return target, len(files)


AUTO_DIR, AUTO_LAST, AUTO_DAYS, AUTO_KEEP = "lucent.backup.auto.dir", "lucent.backup.auto.last", 7, 4


def auto_backup():
    """Called by the helper (every hour): once a week a silent backup into the chosen folder; keeps the last 4."""
    folder = xbmc.getInfoLabel(f"Skin.String({AUTO_DIR})")
    if not folder:
        return
    try:
        last = float(xbmc.getInfoLabel(f"Skin.String({AUTO_LAST})") or 0)
    except ValueError:
        last = 0
    if time.time() - last < AUTO_DAYS * 86400:
        return
    try:
        target, count = write_zip(folder, "lucent-auto")
        _dirs, names = xbmcvfs.listdir(folder)
        old = sorted(n for n in names if n.startswith("lucent-auto-") and n.endswith(".zip"))[:-AUTO_KEEP]
        for n in old:
            xbmcvfs.delete(folder.rstrip("/\\") + "/" + n)
        xbmc.executebuiltin(f"Skin.SetString({AUTO_LAST},{time.time():.0f})")
        xbmc.executebuiltin(f'Skin.SetString({LAST},"{time.strftime("%d-%m-%Y %H:%M")}")')
        log(f"auto backup: {count} files -> {target}")
    except Exception as error:  # noqa: BLE001
        log(f"auto backup failed: {error}")
        xbmcgui.Dialog().notification(t("Backup", "Back-up"), t("The automatic backup could not be saved (is the USB stick in?)",
                                                              "De automatische back-up kon niet worden bewaard (zit de USB-stick erin?)"),
                                      xbmcgui.NOTIFICATION_WARNING, 6000, True)
        xbmc.executebuiltin(f"Skin.SetString({AUTO_LAST},{time.time() - (AUTO_DAYS - 1) * 86400:.0f})")   # try again tomorrow


def auto_menu():
    folder = xbmc.getInfoLabel(f"Skin.String({AUTO_DIR})")
    if folder:
        pick = xbmcgui.Dialog().select(t("Automatic backup", "Automatische back-up"),
                                       [t(f"Switch off (now: {folder})", f"Uitzetten (nu: {folder})"), t("Choose another folder", "Andere map kiezen")])
        if pick == 0:
            xbmc.executebuiltin(f"Skin.Reset({AUTO_DIR})")
            return
        if pick != 1:
            return
    new = xbmcgui.Dialog().browse(3, t("Folder for the weekly backup (best: a USB stick)", "Map voor de wekelijkse back-up (liefst een USB-stick)"), "files")
    if not new:
        return
    xbmc.executebuiltin(f'Skin.SetString({AUTO_DIR},"{new}")')
    xbmc.executebuiltin(f"Skin.SetString({AUTO_LAST},0)")
    xbmcgui.Dialog().notification(t("Backup", "Back-up"), t("Once a week, the last 4 are kept", "Elke week een back-up, de laatste 4 blijven bewaard"),
                                  "special://skin/media/icons/cloud.png", 4000, False)


def make_backup():
    folder = xbmcgui.Dialog().browse(3, t("Where should the backup go? (USB stick, network share ...)",
                                          "Waar moet de back-up heen? (USB-stick, netwerkmap …)"), "files")
    if not folder:
        return
    try:
        target, count = write_zip(folder, "lucent-backup")
    except Exception as error:  # noqa: BLE001
        log(f"backup failed: {error}")
        xbmcgui.Dialog().ok(t("Backup", "Back-up"), t(f"The backup failed: {error}", f"De back-up is mislukt: {error}"))
        return
    files = range(count)
    when = time.strftime("%d-%m-%Y %H:%M")
    xbmc.executebuiltin(f'Skin.SetString({LAST},"{when}")')
    log(f"backup: {len(files)} files -> {target}")
    xbmcgui.Dialog().ok(t("Backup", "Back-up"),
                        t(f"Done: {len(files)} files saved in\n{target}\n\nIt holds your logins (Trakt, IPTV): keep it to yourself.",
                          f"Klaar: {len(files)} bestanden bewaard in\n{target}\n\nHierin staan je inlogs (Trakt, IPTV): houd het voor jezelf."))


def last_backup():
    return xbmc.getInfoLabel(f"Skin.String({LAST})")


def safe_target(inner):
    """userdata/<path> -> real path in the profile, or '' for anything that tries to leave the profile folder."""
    if not inner.startswith("userdata/") or inner.endswith("/"):
        return ""
    rel = inner[len("userdata/"):]
    if not rel or rel.startswith("/") or ".." in rel.split("/") or ":" in rel:
        return ""
    return real(rel)


def apply_skin_settings(raw):
    """Put Lucent's skin settings back through Kodi (string -> Skin.SetString, bool -> Skin.SetBool / Skin.Reset)."""
    count = 0
    for setting in ET.fromstring(raw).iter("setting"):
        sid = (setting.get("id") or "").strip()
        if not sid or any(ch in sid for ch in ',()"'):
            continue
        value = setting.text or ""
        if setting.get("type") == "bool":
            xbmc.executebuiltin(f"Skin.SetBool({sid})" if value.strip().lower() == "true" else f"Skin.Reset({sid})")
        elif value:
            xbmc.executebuiltin(f'Skin.SetString({sid},"{value.replace(chr(34), chr(39))}")')
        else:
            xbmc.executebuiltin(f"Skin.Reset({sid})")
        count += 1
    return count


def restore():
    chosen = xbmcgui.Dialog().browse(1, t("Choose the backup (lucent-backup-….zip)", "Kies de back-up (lucent-backup-….zip)"),
                                     "files", ".zip")
    if not chosen or not chosen.lower().endswith(".zip"):
        return
    temp = xbmcvfs.translatePath("special://temp/lucent-restore.zip")
    if not xbmcvfs.copy(chosen, temp):
        xbmcgui.Dialog().ok(t("Restore", "Herstellen"), t("Could not read that file.", "Kon dat bestand niet lezen."))
        return
    try:
        with zipfile.ZipFile(temp) as archive:
            names = archive.namelist()
            if "lucent-backup.txt" not in names:
                xbmcgui.Dialog().ok(t("Restore", "Herstellen"), t("This is not a Lucent backup.", "Dit is geen back-up van Lucent."))
                return
            made = archive.read("lucent-backup.txt").decode("utf-8", "replace").splitlines()[0]
            if not xbmcgui.Dialog().yesno(t("Restore", "Herstellen"),
                                          t(f"{made}\n\nPut these settings back? What you set up now is replaced. Kodi restarts afterwards.",
                                            f"{made}\n\nDeze instellingen terugzetten? Wat je nu hebt ingesteld wordt vervangen. Kodi start daarna opnieuw.")):
                return
            written = skin = 0
            for inner in names:
                if inner == f"userdata/{SKIN_SETTINGS}":
                    skin = apply_skin_settings(archive.read(inner))
                    continue
                target = safe_target(inner)
                if not target:
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as fh:
                    fh.write(archive.read(inner))
                written += 1
    except Exception as error:  # noqa: BLE001
        log(f"restore failed: {error}")
        xbmcgui.Dialog().ok(t("Restore", "Herstellen"), t(f"Restoring failed: {error}", f"Herstellen is mislukt: {error}"))
        return
    finally:
        try:
            os.remove(temp)
        except OSError:
            pass
    log(f"restore: {skin} skin settings, {written} files from {chosen}")
    xbmcgui.Dialog().ok(t("Restore", "Herstellen"),
                        t(f"Done: {skin} Lucent settings and {written} files are back. Kodi restarts now.",
                          f"Klaar: {skin} Lucent-instellingen en {written} bestanden staan terug. Kodi start nu opnieuw."))
    xbmc.sleep(1500)                                          # the skin settings are saved before Kodi goes down
    xbmc.executebuiltin("RestartApp")


def menu():
    last = last_backup()
    pick = xbmcgui.Dialog().select(t("Backup", "Back-up") + (t(f"  ·  last: {last}", f"  ·  laatste: {last}") if last else ""),
                                   [t("Make a backup", "Back-up maken"), t("Restore a backup", "Back-up terugzetten"),
                                    t("Automatic weekly backup", "Automatische wekelijkse back-up") +
                                    (t("  (on)", "  (aan)") if xbmc.getInfoLabel(f"Skin.String({AUTO_DIR})") else t("  (off)", "  (uit)"))])
    if pick == 0:
        make_backup()
    elif pick == 1:
        restore()
    elif pick == 2:
        auto_menu()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "backup":
        make_backup()
    elif action == "restore":
        restore()
    elif action == "auto":
        auto_backup()
    else:
        menu()
