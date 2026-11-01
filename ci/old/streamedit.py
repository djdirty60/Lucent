# -*- coding: utf-8 -*-
"""Lucent: choose the streaming services of the 'Streaming services' row yourself.

RunScript(special://skin/scripts/streamedit.py)          open the editor
RunScript(special://skin/scripts/streamedit.py,reset)    back to Lucent's standard list

Add a service (every service TMDb knows for your country and the US), remove one, change the order, or give a
service your own picture. Stored in Lucent Library's folder (tmdb/services.json), which builds the row from it.
"""
import json
import os
import sys
import time

import xbmc
import xbmcgui
import xbmcvfs

HEADING = "Lucent"
LIB = "script.lucent.library"
DIR = xbmcvfs.translatePath(f"special://profile/addon_data/{LIB}/tmdb/")
OWN = os.path.join(DIR, "services.json")
STANDARD = os.path.join(DIR, "providers.json")
IMG = "https://image.tmdb.org/t/p/"
_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"

T = {
    "title": ("Streaming services", "Streamingdiensten"),
    "add": ("+ Add a service", "+ Dienst toevoegen"),
    "reset": ("Back to the standard list", "Terug naar de standaardlijst"),
    "reset_q": ("Use Lucent's standard list of services again? Your own choice and pictures are removed.",
                "Weer Lucents standaardlijst gebruiken? Je eigen keuze en afbeeldingen worden verwijderd."),
    "up": ("Move up", "Omhoog"),
    "down": ("Move down", "Omlaag"),
    "remove": ("Remove this service", "Deze dienst verwijderen"),
    "image": ("Picture", "Afbeelding"),
    "own_image": ("your own", "eigen"),
    "std_image": ("standard logo", "standaardlogo"),
    "pick_file": ("Choose a picture…", "Kies een afbeelding…"),
    "type_url": ("Type an address (http… or a path)…", "Adres typen (http… of een pad)…"),
    "std": ("Use the standard logo", "Standaardlogo gebruiken"),
    "rename": ("Name", "Naam"),
    "already": ("{0} is already in the row.", "{0} staat al in de rij."),
    "none": ("No services found. Lucent Library needs the TMDb key (Skin settings).",
             "Geen diensten gevonden. Lucent Bibliotheek heeft de TMDb-sleutel nodig (Skin-instellingen)."),
    "us": ("US", "VS"),
}


def tr(key, *args):
    text = T[key][1 if _NL else 0]
    return text.format(*args) if args else text


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def save(items):
    os.makedirs(DIR, exist_ok=True)
    tmp = OWN + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"items": items}, fh)
    os.replace(tmp, OWN)
    reload_rows()


def reload_rows():
    """Ask Home to load its rows again, so the services row shows the change right away."""
    home = xbmcgui.Window(10000)
    now = str(time.time())
    for n in range(1, 11):
        home.setProperty(f"lucent.wr.{n}", now)


def current():
    own = read(OWN).get("items")
    if own:
        return own
    return [dict(p) for p in read(STANDARD).get("items") or []]


def catalog():
    xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
    try:
        result = json.loads(xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "Files.GetDirectory",
            "params": {"directory": f"plugin://{LIB}/?action=provcatalog", "media": "files"}})))
    finally:
        xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
    import urllib.parse
    out = []
    for f in (result.get("result") or {}).get("files") or []:
        q = urllib.parse.parse_qs((f.get("file") or "").split("?", 1)[-1])
        get = lambda k: (q.get(k) or [""])[0]  # noqa: E731
        if get("id").isdigit():
            out.append({"id": int(get("id")), "name": get("name"), "logo": get("logo"), "region": get("region")})
    return out


def picture(service):
    """Ask for a picture: a file, an address, or back to the standard logo. None = cancelled."""
    choice = xbmcgui.Dialog().select(tr("image"), [tr("pick_file"), tr("type_url"), tr("std")])
    if choice == 0:
        path = xbmcgui.Dialog().browseSingle(2, tr("image"), "files", ".png|.jpg|.jpeg|.webp|.gif", True)
        return path or None
    if choice == 1:
        text = xbmcgui.Dialog().input(tr("image"), service.get("image") or "")
        return text.strip() or None
    if choice == 2:
        return ""
    return None


def edit(items, index):
    while 0 <= index < len(items):
        p = items[index]
        state = tr("own_image") if p.get("image") else tr("std_image")
        options = [f"{tr('rename')}: {p.get('name')}", f"{tr('image')}: {state}", tr("up"), tr("down"), tr("remove")]
        choice = xbmcgui.Dialog().select(p.get("name") or "", options)
        if choice < 0:
            return
        if choice == 0:
            name = xbmcgui.Dialog().input(tr("rename"), p.get("name") or "")
            if name.strip():
                p["name"] = name.strip()
        elif choice == 1:
            img = picture(p)
            if img is None:
                continue
            if img:
                p["image"] = img
            else:
                p.pop("image", None)
        elif choice == 2 and index > 0:
            items[index - 1], items[index] = items[index], items[index - 1]
            index -= 1
        elif choice == 3 and index < len(items) - 1:
            items[index + 1], items[index] = items[index], items[index + 1]
            index += 1
        elif choice == 4:
            del items[index]
            save(items)
            return
        save(items)


def editor():
    while True:
        items = current()
        rows = []
        for p in items:
            li = xbmcgui.ListItem(p.get("name") or "?")
            icon = p.get("image") or (f"{IMG}w92{p['logo']}" if p.get("logo") else "icons/tv.png")
            li.setArt({"icon": icon, "thumb": icon})
            rows.append(li)
        for key, icon in (("add", "icons/plus.png"), ("reset", "icons/refresh.png")):
            li = xbmcgui.ListItem(tr(key))
            li.setArt({"icon": icon, "thumb": icon})
            rows.append(li)
        choice = xbmcgui.Dialog().select(tr("title"), rows, useDetails=True)
        if choice < 0:
            return
        if choice < len(items):
            edit(items, choice)
        elif choice == len(items):
            add(items)
        elif xbmcgui.Dialog().yesno(HEADING, tr("reset_q")):
            reset()


def add(items):
    found = catalog()
    if not found:
        xbmcgui.Dialog().ok(HEADING, tr("none"))
        return
    have = {str(p.get("id")) for p in items}
    labels = []
    for p in found:
        region = f"  ({tr('us')})" if p["region"] == "US" and _NL else ""
        labels.append(f"{'✔ ' if str(p['id']) in have else ''}{p['name']}{region}")
    pick = xbmcgui.Dialog().select(tr("add"), labels)
    if pick < 0:
        return
    p = found[pick]
    if str(p["id"]) in have:
        xbmcgui.Dialog().ok(HEADING, tr("already", p["name"]))
        return
    items.append(p)
    save(items)


def reset():
    try:
        os.remove(OWN)
    except OSError:
        pass
    reload_rows()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        reset()
    else:
        editor()
