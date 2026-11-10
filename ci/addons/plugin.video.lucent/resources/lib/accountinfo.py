# -*- coding: utf-8 -*-
"""'Account information' for every service: who you are linked as, your subscription and until when.
Also checks the connection. E-mail addresses, keys and tokens are never shown or logged."""
import datetime

import xbmcgui

import util

T = util.T


def _date(value):
    """An ISO date, a unix time or '' -> '12 maart 2027' style, or ''."""
    if not value:
        return ""
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            when = datetime.datetime.utcfromtimestamp(int(value))
        else:
            when = datetime.datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except (ValueError, OverflowError, OSError):
        return ""
    months = T("januari februari maart april mei juni juli augustus september oktober november december",
               "January February March April May June July August September October November December").split()
    return "%d %s %d" % (when.day, months[when.month - 1], when.year)


def _days_left(value):
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            when = datetime.datetime.utcfromtimestamp(int(value))
        else:
            when = datetime.datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except (ValueError, OverflowError, OSError):
        return None
    return (when - datetime.datetime.utcnow()).days


def _until(value):
    if not value:
        return ""
    left = _days_left(value)
    text = T("Geldig tot %s", "Valid until %s") % _date(value)
    if left is not None:
        text += T(" (nog %d dagen)", " (%d days left)") % max(0, left)
    return text


def trakt():
    import trakt as service
    if not service.logged_in():
        return [T("Niet gekoppeld.", "Not linked.")]
    data = service.call("users/settings")[0] or {}
    user = data.get("user") or {}
    lines = [T("Gekoppeld als %s", "Linked as %s") % (user.get("username") or "?")]
    lines.append("VIP" if user.get("vip") else T("Gratis account", "Free account"))
    if user.get("joined_at"):
        lines.append(T("Lid sinds %s", "Member since %s") % _date(user["joined_at"]))
    try:
        stats = service.call("users/me/stats")[0] or {}
        movies, episodes = stats.get("movies") or {}, stats.get("episodes") or {}
        hours = int(((movies.get("minutes") or 0) + (episodes.get("minutes") or 0)) / 60)
        lines.append(T("Bekeken: %d films, %d afleveringen (%d uur)", "Watched: %d films, %d episodes (%d hours)")
                     % (movies.get("watched") or 0, episodes.get("watched") or 0, hours))
    except util.HttpError:
        pass
    return lines


def simkl():
    import simkl as service
    if not service.logged_in():
        return [T("Niet gekoppeld.", "Not linked.")]
    data = service.call("users/settings", data={}) or {}
    user = data.get("user") or {}
    lines = [T("Gekoppeld als %s", "Linked as %s") % (user.get("name") or "?")]
    if user.get("joined_at"):
        lines.append(T("Lid sinds %s", "Member since %s") % _date(user["joined_at"]))
    return lines


def easynews():
    import usenet
    ok, text = usenet.check_easynews()
    lines = [text]
    if ok:
        lines.insert(0, T("Gebruikersnaam: %s", "Username: %s") % util.setting("easynews_user"))
    return lines


def torbox():
    if not util.setting("torbox_key"):
        return [T("Vul eerst je API-sleutel in.", "Enter your API key first.")]
    import usenet
    answer, _ = util.http(usenet.TB_API + "/user/me", headers=usenet._tb_head())
    data = (answer or {}).get("data") or {}
    plans = {0: T("Gratis", "Free"), 1: "Essential", 2: "Pro", 3: "Standard"}
    lines = [T("Verbonden met TorBox.", "Connected to TorBox."), T("Abonnement: %s", "Plan: %s") % plans.get(data.get("plan"), data.get("plan"))]
    if data.get("premium_expires_at"):
        lines.append(_until(data["premium_expires_at"]))
    if data.get("total_downloaded"):
        lines.append(T("Gedownload in totaal: %d", "Downloaded in total: %d") % data["total_downloaded"])
    return lines


def realdebrid():
    import debrid
    if not debrid.key("realdebrid"):
        return [T("Vul eerst je API-sleutel in.", "Enter your API key first.")]
    data, _ = util.http(debrid.RD + "user", headers=debrid._head("realdebrid"))
    data = data or {}
    lines = [T("Gekoppeld als %s", "Linked as %s") % (data.get("username") or "?"),
             "Premium" if data.get("type") == "premium" else T("Gratis account", "Free account")]
    if data.get("expiration"):
        lines.append(_until(data["expiration"]))
    if data.get("points") is not None:
        lines.append(T("Fidelity-punten: %s", "Fidelity points: %s") % data["points"])
    return lines


def alldebrid():
    import debrid
    if not debrid.key("alldebrid"):
        return [T("Vul eerst je API-sleutel in.", "Enter your API key first.")]
    user = (debrid._ad_call("v4/user").get("user") or {})
    lines = [T("Gekoppeld als %s", "Linked as %s") % (user.get("username") or "?"),
             "Premium" if user.get("isPremium") else T("Gratis account", "Free account")]
    if user.get("premiumUntil"):
        lines.append(_until(user["premiumUntil"]))
    return lines


def premiumize():
    import debrid
    if not debrid.key("premiumize"):
        return [T("Vul eerst je API-sleutel in.", "Enter your API key first.")]
    data, _ = util.http(debrid.PM + "account/info", headers=debrid._head("premiumize"))
    data = data or {}
    if data.get("status") != "success":
        return [T("Premiumize accepteert deze sleutel niet.", "Premiumize does not accept this key.")]
    lines = [T("Verbonden met Premiumize.", "Connected to Premiumize.")]
    if data.get("premium_until"):
        lines.append(_until(data["premium_until"]))
    if data.get("limit_used") is not None:
        lines.append(T("Fair use gebruikt: %d%%", "Fair use used: %d%%") % round(float(data["limit_used"]) * 100))
    return lines


def mdblist():
    import mdblist as service
    ok, text = service.check()
    return [text]


SERVICES = {"trakt": ("Trakt", trakt), "simkl": ("Simkl", simkl), "easynews": ("Easynews", easynews), "torbox": ("TorBox", torbox),
            "realdebrid": ("Real-Debrid", realdebrid), "alldebrid": ("AllDebrid", alldebrid), "premiumize": ("Premiumize", premiumize),
            "mdblist": ("MDBList", mdblist)}


def show(service):
    name, read = SERVICES[service]
    try:
        lines = read()
    except util.HttpError as error:
        lines = [T("Geen verbinding: %s", "No connection: %s") % error]
    except (KeyError, ValueError, TypeError):
        lines = [T("Het antwoord van %s kon niet worden gelezen.", "The answer from %s could not be read.") % name]
    xbmcgui.Dialog().ok(T("Accountinformatie · %s", "Account information · %s") % name, "\n".join(l for l in lines if l))


def publish_names():
    """Puts the linked account names in the settings, so the settings can show 'Linked as ...' (first profile only)."""
    import users
    if users.current_id() != users.MAIN:
        return
    for setting, module in (("trakt_user", "trakt"), ("simkl_user", "simkl")):
        account = __import__(module)
        name = account.account().get("user", "") if account.logged_in() else ""
        if not name and account.logged_in():
            name = T("ja", "yes")
        if util.setting(setting) != name:
            util.ADDON.setSetting(setting, name)
