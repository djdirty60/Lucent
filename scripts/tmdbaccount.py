# -*- coding: utf-8 -*-
"""Lucent 3.0.10: your TMDb account (as an alternative to Trakt).

    RunScript(special://skin/scripts/tmdbaccount.py)       Skin settings > Accounts > TMDb account

Log in with your TMDb user name and password (TMDb's own login for apps: a request token that your login approves,
then a session). Lucent keeps only the session, never the password. With it, Home can show your TMDb watchlist,
rated titles and favourites as rows (plugin://skin.lucent/?list=tmdbacct&what=watchlist/movies, scripts/plugin.py).
"""
import json

import xbmc
import xbmcgui
import xbmcvfs

import info

PATH = "special://profile/addon_data/skin.lucent/tmdb_account.json"
_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
T = {
    "user": ("TMDb user name", "TMDb-gebruikersnaam"),
    "password": ("TMDb password (Lucent does not keep it)", "TMDb-wachtwoord (Lucent bewaart het niet)"),
    "busy": ("Logging in at TMDb…", "Inloggen bij TMDb…"),
    "ok": ("Logged in at TMDb as {0}. Add your TMDb rows under Settings > Lucent > Customise menu and widgets > "
           "+ Add a widget > TMDb lists.",
           "Ingelogd bij TMDb als {0}. Zet je TMDb-rijen op Home via Instellingen > Lucent > Menu en widgets aanpassen > "
           "+ Widget toevoegen > TMDb-lijsten."),
    "wrong": ("TMDb did not accept this user name and password.", "TMDb accepteert deze gebruikersnaam en dit wachtwoord niet."),
    "failed": ("Could not reach TMDb. Try again later.", "TMDb is niet bereikbaar. Probeer het later opnieuw."),
    "logout": ("You are logged in at TMDb as {0}. Log out?", "Je bent ingelogd bij TMDb als {0}. Uitloggen?"),
    "out": ("Logged out at TMDb", "Uitgelogd bij TMDb"),
    "sub_in": ("Logged in as {0}", "Ingelogd als {0}"),
}


def tr(key, *args):
    text = T[key][1 if _NL else 0]
    return text.format(*args) if args else text


def log(text):
    xbmc.log(f"[skin.lucent] tmdbaccount: {text}", xbmc.LOGINFO)


def load():
    try:
        with xbmcvfs.File(PATH) as fh:
            return json.loads(fh.read() or "{}")
    except Exception:  # noqa: BLE001
        return {}


def save(data):
    xbmcvfs.mkdirs("special://profile/addon_data/skin.lucent/")
    with xbmcvfs.File(PATH, "w") as fh:
        fh.write(json.dumps(data))


def show_state(data=None):
    data = load() if data is None else data
    if data.get("session"):
        xbmc.executebuiltin(f"Skin.SetString(lucent.tmdb.user,{data.get('user', '')})")
    else:
        xbmc.executebuiltin("Skin.Reset(lucent.tmdb.user)")


def post(path, body):
    key = info.tmdb_key()
    return info.http(f"{info.TMDB}{path}?api_key={key}", data=body,
                     headers={"Content-Type": "application/json"}, method="POST")


def login():
    user = xbmcgui.Dialog().input(tr("user"))
    if not user:
        return
    password = xbmcgui.Dialog().input(tr("password"), option=xbmcgui.ALPHANUM_HIDE_INPUT)
    if not password:
        return
    progress = xbmcgui.DialogProgress()
    progress.create("TMDb", tr("busy"))
    try:
        token = info.tmdb("authentication/token/new")["request_token"]
        post("authentication/token/validate_with_login", {"username": user, "password": password, "request_token": token})
        session = post("authentication/session/new", {"request_token": token})["session_id"]
        account = info.tmdb("account", session_id=session)
    except Exception as error:  # noqa: BLE001
        progress.close()
        code = getattr(error, "code", 0)
        log(f"login failed: {type(error).__name__} {code}")
        xbmcgui.Dialog().ok("TMDb", tr("wrong") if code in (401, 403) else tr("failed"))
        return
    progress.close()
    data = {"session": session, "account": account.get("id"), "user": account.get("username") or user}
    save(data)
    show_state(data)
    log(f"logged in as {data['user']}")
    xbmcgui.Dialog().ok("TMDb", tr("ok", data["user"]))


def logout(data):
    if not xbmcgui.Dialog().yesno("TMDb", tr("logout", data.get("user", ""))):
        return
    try:
        info.http(f"{info.TMDB}authentication/session?api_key={info.tmdb_key()}",
                  data={"session_id": data["session"]},
                  headers={"Content-Type": "application/json"}, method="DELETE")
    except Exception as error:  # noqa: BLE001 - the session is forgotten here either way
        log(f"logout: {type(error).__name__}")
    if xbmcvfs.exists(PATH):
        xbmcvfs.delete(PATH)
    show_state({})
    info.notify(tr("out"))


def account_list(what, page=1):
    """watchlist/movies, watchlist/tv, rated/movies, rated/tv, favorite/movies, favorite/tv: the newest first."""
    data = load()
    if not data.get("session"):
        return []
    lang = "nl-NL" if _NL else "en-US"
    res = info.tmdb(f"account/{data['account']}/{what}", session_id=data["session"], sort_by="created_at.desc",
                    page=page, language=lang)
    return res.get("results") or []


if __name__ == "__main__":
    current = load()
    if current.get("session"):
        logout(current)
    else:
        login()
