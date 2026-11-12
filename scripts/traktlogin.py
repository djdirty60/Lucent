# -*- coding: utf-8 -*-
"""Lucent: its own Trakt login, for every video add-on.

    RunScript(special://skin/scripts/traktlogin.py)          Skin settings > Follow > Trakt login (log in / out)
    RunScript(special://skin/scripts/traktlogin.py,login)    log in straight away

Trakt asks every app for its own keys. You make a free 'API app' on trakt.tv once (Settings > Your API Apps > New
application, redirect uri urn:ietf:wg:oauth:2.0:oob) and type its Client ID and Client Secret here. Then Lucent shows a
code that you enter on trakt.tv/activate. Keys and login stay on this box (addon_data/skin.lucent/trakt.json); they are
never in the skin itself. The login is renewed by itself before it runs out.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import xbmc
import xbmcgui
import xbmcvfs

HEADING = "Trakt"
API = "https://api.trakt.tv/"
OOB = "urn:ietf:wg:oauth:2.0:oob"
FILE = "special://profile/addon_data/skin.lucent/trakt.json"
USER = "lucent.trakt.user"            # Skin.String: the account name, shown in Skin settings
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] traktlogin: {text}", xbmc.LOGINFO)


# ----------------------------------------------------------------------------- the file
def load():
    try:
        with open(xbmcvfs.translatePath(FILE), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    path = xbmcvfs.translatePath(FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)
    xbmc.executebuiltin(f"Skin.SetString({USER},{data.get('user', '')})" if data.get("access_token")
                        else f"Skin.Reset({USER})")


def post(path, body, headers=None):
    request = urllib.request.Request(API + path, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers=dict({"Content-Type": "application/json",
                                                   "User-Agent": "skin.lucent (Kodi)"}, **(headers or {})))
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}


def keep_tokens(data, answer):
    data["access_token"] = answer.get("access_token") or ""
    data["refresh_token"] = answer.get("refresh_token") or data.get("refresh_token") or ""
    data["expires_at"] = float(answer.get("created_at") or time.time()) + float(answer.get("expires_in") or 0)


# ----------------------------------------------------------------------------- for the other scripts
def has_login():
    data = load()
    return bool(data.get("client_id") and data.get("access_token"))


def renew(data=None):
    """Renew the login with its refresh token. True when it worked."""
    data = data or load()
    if not (data.get("client_id") and data.get("client_secret") and data.get("refresh_token")):
        return False
    try:
        answer = post("oauth/token", {"refresh_token": data["refresh_token"], "client_id": data["client_id"],
                                      "client_secret": data["client_secret"], "redirect_uri": OOB,
                                      "grant_type": "refresh_token"})
    except Exception as error:  # noqa: BLE001
        log(f"renew: {error}")
        return False
    if not answer.get("access_token"):
        return False
    keep_tokens(data, answer)
    save(data)
    log("login renewed")
    return True


def credentials():
    """(client id, access token) of Lucent's own login, renewed when it runs out within a day; ("", "") without one."""
    data = load()
    if not (data.get("client_id") and data.get("access_token")):
        return "", ""
    try:
        soon = float(data.get("expires_at") or 0) < time.time() + 86400
    except (TypeError, ValueError):
        soon = True
    if soon and renew(data):
        data = load()
    return data.get("client_id", ""), data.get("access_token", "")


# ----------------------------------------------------------------------------- logging in
def ask_keys(data):
    dialog = xbmcgui.Dialog()
    if not dialog.yesno(HEADING, t(
            "Trakt needs your own (free) API app once:\n1. trakt.tv > Settings > Your API Apps > New application\n"
            "2. Name: Lucent - Redirect uri: urn:ietf:wg:oauth:2.0:oob\n3. Type its Client ID and Client Secret here.",
            "Trakt wil één keer je eigen (gratis) API-app:\n1. trakt.tv > Settings > Your API Apps > New application\n"
            "2. Naam: Lucent - Redirect uri: urn:ietf:wg:oauth:2.0:oob\n3. Typ hier de Client ID en Client Secret."),
            nolabel=t("Cancel", "Annuleren"), yeslabel=t("Enter keys", "Sleutels invullen")):
        return False
    client = dialog.input("Client ID", data.get("client_id", "")).strip()
    if not client:
        return False
    secret = dialog.input("Client Secret", data.get("client_secret", "")).strip()
    if not secret:
        return False
    data.update(client_id=client, client_secret=secret)
    save(data)
    return True


def login():
    data = load()
    if not (data.get("client_id") and data.get("client_secret")) and not ask_keys(data):
        return False
    try:
        code = post("oauth/device/code", {"client_id": data["client_id"]})
    except urllib.error.HTTPError as error:
        log(f"device code: {error}")
        xbmcgui.Dialog().ok(HEADING, t(f"Trakt does not accept the Client ID (Trakt code {error.code}). Check the keys.",
                                       f"Trakt accepteert de Client ID niet (Trakt-code {error.code}). Controleer de sleutels."))
        if ask_keys(data):
            return login()
        return False
    except Exception as error:  # noqa: BLE001
        xbmcgui.Dialog().ok(HEADING, t("No connection with Trakt: ", "Geen verbinding met Trakt: ") + str(error)[:120])
        return False
    interval = max(int(code.get("interval") or 5), 1)
    ends = time.time() + int(code.get("expires_in") or 600)
    url = code.get("verification_url") or "https://trakt.tv/activate"
    progress = xbmcgui.DialogProgress()
    progress.create(HEADING, t(f"Go to [B]{url}[/B] and enter this code:", f"Ga naar [B]{url}[/B] en vul deze code in:")
                    + f"\n\n[B][COLOR white]{code.get('user_code', '')}[/COLOR][/B]")
    monitor = xbmc.Monitor()
    answer = None
    while time.time() < ends and not progress.iscanceled() and not monitor.abortRequested():
        left = max(int(ends - time.time()), 0)
        progress.update(int(100 * left / max(int(code.get("expires_in") or 600), 1)))
        if monitor.waitForAbort(interval):
            break
        try:
            answer = post("oauth/device/token", {"code": code.get("device_code", ""), "client_id": data["client_id"],
                                                 "client_secret": data["client_secret"]})
            break
        except urllib.error.HTTPError as error:
            if error.code == 400:                # not entered yet
                continue
            if error.code == 429:                # too quick
                interval += 1
                continue
            log(f"device token: {error}")
            answer = {"error": error.code}
            break
        except Exception as error:  # noqa: BLE001
            log(f"device token: {error}")
    progress.close()
    if not answer or not answer.get("access_token"):
        if answer and answer.get("error") == 401:
            xbmcgui.Dialog().ok(HEADING, t("Trakt does not accept the Client Secret. Check the keys.",
                                           "Trakt accepteert de Client Secret niet. Controleer de sleutels."))
        elif answer and answer.get("error") == 418:
            xbmcgui.Dialog().ok(HEADING, t("You said no on trakt.tv.", "Je hebt op trakt.tv 'nee' gekozen."))
        elif answer:
            xbmcgui.Dialog().ok(HEADING, t("The code ran out. Try again.", "De code is verlopen. Probeer het opnieuw."))
        return False
    keep_tokens(data, answer)
    try:
        request = urllib.request.Request(API + "users/settings", headers={
            "Content-Type": "application/json", "trakt-api-version": "2", "trakt-api-key": data["client_id"],
            "Authorization": f"Bearer {data['access_token']}", "User-Agent": "skin.lucent (Kodi)"})
        with urllib.request.urlopen(request, timeout=20) as response:
            user = json.loads(response.read().decode("utf-8")).get("user") or {}
        data["user"] = user.get("username") or user.get("name") or "Trakt"
    except Exception as error:  # noqa: BLE001
        log(f"user: {error}")
        data["user"] = "Trakt"
    save(data)
    xbmcgui.Dialog().notification(HEADING, t(f"Logged in as {data['user']}", f"Ingelogd als {data['user']}"),
                                  xbmcgui.NOTIFICATION_INFO, 4000)
    return True


def logout(keep_keys=True):
    data = load()
    if data.get("access_token") and data.get("client_secret"):
        try:
            post("oauth/revoke", {"token": data["access_token"], "client_id": data["client_id"],
                                  "client_secret": data["client_secret"]})
        except Exception as error:  # noqa: BLE001
            log(f"revoke: {error}")
    data = {k: v for k, v in data.items() if keep_keys and k in ("client_id", "client_secret")}
    save(data)
    xbmcgui.Dialog().notification(HEADING, t("Logged out", "Uitgelogd"), xbmcgui.NOTIFICATION_INFO, 3000)


def menu():
    data = load()
    if not data.get("access_token"):
        login()
        return
    choice = xbmcgui.Dialog().select(t(f"Trakt - logged in as {data.get('user', '')}",
                                       f"Trakt - ingelogd als {data.get('user', '')}"),
                                     [t("Log in again", "Opnieuw inloggen"), t("Change the keys", "Sleutels wijzigen"),
                                      t("Log out", "Uitloggen")])
    if choice == 0:
        login()
    elif choice == 1:
        if ask_keys(data):
            logout()
            login()
    elif choice == 2:
        logout()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "menu"
    if action == "login":
        login()
    else:
        menu()
