# -*- coding: utf-8 -*-
"""Lucent: clean up and look after the box (Skin settings > Advanced > Maintenance).

    RunScript(special://skin/scripts/maintenance.py)        the menu: clean up now, automatic once a month on / off
    RunScript(special://skin/scripts/maintenance.py,auto)   (helper.py) the monthly clean-up, only when it is switched on

What it cleans - only things Kodi makes again by itself when it needs them:
  - pictures in the picture cache that were not shown for a long time (Kodi's own Textures API: the database entry and
    the file go together, so nothing breaks and no restart is needed)
  - the zip files Kodi keeps of every add-on it installed or updated (addons/packages)
  - old temporary files (not the log of this session)
  - the log of the previous session (kodi.old.log)
  - and, when you ask for it, titles in the Kodi library whose file is gone ('clean library')
Nothing of your settings, add-ons, library or watched marks is touched.
"""
import datetime
import json
import os
import sys
import time

import xbmc
import xbmcgui
import xbmcvfs

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
HEADING = "Lucent"
PICTURE_DAYS = 30          # pictures not shown for this long go (when you clean up yourself)
AUTO_PICTURE_DAYS = 60     # the monthly automatic clean-up is a bit more careful
AUTO_EVERY = 30 * 86400
TEMP_DAYS = 2


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] maintenance: {text}", xbmc.LOGINFO)


def cond(expr):
    return xbmc.getCondVisibility(expr)


def path(special):
    return xbmcvfs.translatePath(special)


def rpc(method, params=None):
    query = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(query)))
    except Exception as error:  # noqa: BLE001
        return {"error": str(error)}


def size_text(n):
    mb = n / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB".replace(".", "," if NL else ".")
    return f"{mb:.0f} MB" if mb >= 10 else f"{mb:.1f} MB".replace(".", "," if NL else ".")


def file_size(name):
    try:
        return os.path.getsize(name)
    except OSError:
        return 0


# ----------------------------------------------------------------------------- what can go
def old_pictures(days):
    """[(texture id, cached file)] of pictures that were not shown for `days` days."""
    before = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    res = rpc("Textures.GetTextures", {"properties": ["cachedurl", "sizes"],
                                       "filter": {"field": "lastused", "operator": "lessthan", "value": before}})
    if "error" in res:                              # an older Kodi without that filter: look at every picture
        res = rpc("Textures.GetTextures", {"properties": ["cachedurl", "sizes"]})
        textures = [x for x in (res.get("result") or {}).get("textures") or []
                    if max((s.get("lastused") or "") for s in x.get("sizes") or [{}]) < before]
    else:
        textures = (res.get("result") or {}).get("textures") or []
    thumbs = path("special://thumbnails/")
    return [(x["textureid"], os.path.join(thumbs, x["cachedurl"]) if x.get("cachedurl") else "") for x in textures]


def packages():
    folder = path("special://home/addons/packages/")
    try:
        return [os.path.join(folder, n) for n in os.listdir(folder) if n.lower().endswith(".zip")]
    except OSError:
        return []


def temp_files():
    """Files in Kodi's temp folder older than two days; never a log, never something of this session."""
    folder = path("special://temp/")
    limit = time.time() - TEMP_DAYS * 86400
    out = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            full = os.path.join(root, name)
            if name.lower().endswith(".log") or name.lower().startswith("kodi"):
                continue
            try:
                if os.path.getmtime(full) < limit:
                    out.append(full)
            except OSError:
                pass
    return out


def old_log():
    name = path("special://logpath/kodi.old.log")
    return [name] if os.path.exists(name) else []


def delete(files):
    freed = 0
    for name in files:
        size = file_size(name)
        try:
            os.remove(name)
            freed += size
        except OSError:
            pass
    return freed


def remove_pictures(items, progress=None):
    freed = 0
    for n, (tid, cached) in enumerate(items):
        size = file_size(cached) if cached else 0
        res = rpc("Textures.RemoveTexture", {"textureid": tid})
        if "error" not in res:
            freed += size
        if progress and n % 50 == 0:
            progress.update(int(n * 100 / max(1, len(items))))
    return freed


def free_space():
    return xbmc.getInfoLabel("System.FreeSpace")


# ----------------------------------------------------------------------------- clean up yourself
def clean_now():
    xbmc.executebuiltin("ActivateWindow(busydialognocancel)")          # counting can take a moment
    try:
        pictures = old_pictures(PICTURE_DAYS)
        pics_size = sum(file_size(c) for _i, c in pictures if c)
        pkgs = packages()
        temps = temp_files()
        logs = old_log()
    finally:
        xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
    options = [
        ("pictures", t(f"Pictures not shown for {PICTURE_DAYS} days: {len(pictures)} ({size_text(pics_size)})",
                       f"Afbeeldingen die {PICTURE_DAYS} dagen niet getoond zijn: {len(pictures)} ({size_text(pics_size)})")),
        ("packages", t(f"Old add-on zip files: {len(pkgs)} ({size_text(sum(map(file_size, pkgs)))})",
                       f"Oude zip-bestanden van add-ons: {len(pkgs)} ({size_text(sum(map(file_size, pkgs)))})")),
        ("temp", t(f"Old temporary files: {len(temps)} ({size_text(sum(map(file_size, temps)))})",
                   f"Oude tijdelijke bestanden: {len(temps)} ({size_text(sum(map(file_size, temps)))})")),
        ("log", t(f"Log of the previous session ({size_text(sum(map(file_size, logs)))})",
                  f"Log van de vorige sessie ({size_text(sum(map(file_size, logs)))})")),
        ("library", t("Library: remove titles whose file is gone", "Bibliotheek: titels weghalen waarvan het bestand weg is")),
    ]
    chosen = xbmcgui.Dialog().multiselect(t("What should be cleaned up?", "Wat moet er opgeruimd worden?"),
                                          [text for _k, text in options], preselect=[0, 1, 2, 3])
    if not chosen:
        return
    keys = {options[i][0] for i in chosen}
    progress = xbmcgui.DialogProgressBG()
    progress.create(HEADING, t("Cleaning up…", "Opruimen…"))
    freed = 0
    try:
        if "pictures" in keys:
            freed += remove_pictures(pictures, progress)
        if "packages" in keys:
            freed += delete(pkgs)
        if "temp" in keys:
            freed += delete(temps)
        if "log" in keys:
            freed += delete(logs)
        if "library" in keys:
            progress.update(90, HEADING, t("Cleaning the library…", "Bibliotheek opschonen…"))
            rpc("VideoLibrary.Clean", {"showdialogs": False})
    finally:
        progress.close()
    remember()
    log(f"cleaned {sorted(keys)}: {size_text(freed)} freed")
    xbmcgui.Dialog().ok(HEADING, t(f"Done: {size_text(freed)} freed.\nFree space now: {free_space()}",
                                   f"Klaar: {size_text(freed)} vrijgemaakt.\nVrije ruimte nu: {free_space()}"))


# ----------------------------------------------------------------------------- once a month by itself
def remember():
    xbmc.executebuiltin(f"Skin.SetString(lucent.maint.last,{int(time.time())})")


def last_time():
    try:
        return int(xbmc.getInfoLabel("Skin.String(lucent.maint.last)") or 0)
    except ValueError:
        return 0


def auto():
    """helper.py: once a month, when switched on, not while something plays. Pictures, zip files, temp files, old log."""
    if not cond("Skin.HasSetting(lucent.maint.auto)") or cond("Player.HasMedia"):
        return
    if time.time() - last_time() < AUTO_EVERY:
        return
    freed = remove_pictures(old_pictures(AUTO_PICTURE_DAYS)) + delete(packages()) + delete(temp_files()) + delete(old_log())
    remember()
    log(f"monthly clean-up: {size_text(freed)} freed")
    if freed >= 5 * 1024 * 1024:
        xbmcgui.Dialog().notification(HEADING, t(f"Monthly clean-up: {size_text(freed)} freed", f"Maandelijks opruimen: {size_text(freed)} vrijgemaakt"),
                                      xbmcgui.NOTIFICATION_INFO, 5000)


def menu():
    while True:
        on = cond("Skin.HasSetting(lucent.maint.auto)")
        last = last_time()
        when = datetime.datetime.fromtimestamp(last).strftime("%d-%m-%Y") if last else t("never", "nog nooit")
        rows = [t("Clean up now…", "Nu opruimen…"),
                t(f"Automatically once a month: {'on' if on else 'off'}", f"Automatisch één keer per maand: {'aan' if on else 'uit'}")]
        choice = xbmcgui.Dialog().select(t(f"Maintenance  ·  last time: {when}  ·  free: {free_space()}",
                                           f"Onderhoud  ·  laatste keer: {when}  ·  vrij: {free_space()}"), rows)
        if choice < 0:
            return
        if choice == 0:
            clean_now()
        elif choice == 1:
            xbmc.executebuiltin("Skin.ToggleSetting(lucent.maint.auto)")
            xbmc.sleep(200)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        auto()
    else:
        menu()
