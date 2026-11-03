"""Lucent: the Solis Dashboard tab on Home (example C) - the numbers of now from the Solis app on your Homey.

The helper calls tick() every few seconds; it fetches when Home shows the tab of script.solis.dashboard. It reads
http://<host>:<port>/lucent.json (Solis voor Homey 3.37.0 or newer; host and port from the Solis add-on's settings) and
the picture /beeld/kaart/stroom.png, and writes Window(home).Property(lucent.sol.*); Home.xml shows them.
OK on a card opens the Solis add-on itself.
"""
import json
import os
import time
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

HOME = xbmcgui.Window(10000)
ADDON = "script.solis.dashboard"
NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
DIR = xbmcvfs.translatePath("special://profile/addon_data/skin.lucent/solis/")
ORANGE, PURPLE, RED, GREEN, BLUE = "FFFF9F1C", "FF8B6CFF", "FFE5484D", "FF3DD68C", "FF7CC4FF"


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] solis: {text}", xbmc.LOGINFO)


def put(name, value):
    value = "" if value is None else str(value)
    if HOME.getProperty(name) != value:
        HOME.setProperty(name, value)


def wanted():
    """Only while Home shows a tab that starts the Solis add-on."""
    return (xbmc.getCondVisibility(f"System.AddonIsEnabled({ADDON}) + Window.IsVisible(home)")
            and ADDON in xbmc.getInfoLabel("Container(9000).ListItem.Property(act)"))


def base():
    try:
        a = xbmcaddon.Addon(ADDON)
        host, port = (a.getSetting("host") or "homey.local").strip(), a.getSetting("port") or "8765"
    except Exception:  # noqa: BLE001
        host, port = "homey.local", "8765"
    host = host.replace("http://", "").replace("https://", "").strip("/")
    return f"http://{host}" if ":" in host else f"http://{host}:{int(port or 8765)}"


def num(value, decimals=0):
    """1234.5 -> '1.234' / 1.8 -> '1,8' (Dutch) or '1,234' / '1.8' (English)."""
    if value is None:
        return None
    try:
        text = f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return None
    return text.replace(",", "#").replace(".", ",").replace("#", ".") if NL else text


def unit(value, u, decimals=0):
    n = num(value, decimals)
    return f"{n} {u}" if n is not None else "–"


def kwh(value):
    """1.8 -> '1,8 kWh', 6 -> '6 kWh'."""
    if value is None:
        return "–"
    return unit(value, "kWh", 0 if float(value) == int(float(value)) else 1)


def cards(d):
    grid = d.get("grid_w")
    if grid is None:
        net = (t("Grid", "Net"), "–", "", BLUE)
    elif grid >= 0:
        net = (t("From the grid", "Van het net"), unit(grid, "W"), t("bought", "ingekocht"), RED)
    else:
        net = (t("To the grid", "Naar het net"), unit(-grid, "W"), t("delivered", "teruggeleverd"), GREEN)
    expected = d.get("today_expected_kwh")
    self_use = d.get("self_use_pct")
    price = d.get("price_now_eur")
    rows = [
        (t("Solar panels", "Zonnepanelen"), unit(d.get("solar_w"), "W"),
         t(f"of {unit(d.get('solar_max_w'), 'W')}", f"van {unit(d.get('solar_max_w'), 'W')}") if d.get("solar_max_w") else "", ORANGE),
        (t("House uses", "Huis gebruikt"), unit(d.get("house_w"), "W"), t("now", "nu") if d.get("house_w") is not None else "", PURPLE),
        net,
        (t("Today", "Vandaag"), kwh(d.get("today_kwh")),
         t(f"expected {num(expected, 1)}", f"verwacht {num(expected, 1)}") if expected is not None else "", ORANGE),
        (t("This month", "Deze maand"), kwh(d.get("month_kwh")),
         t(f"{self_use} % used yourself", f"{self_use} % zelf gebruikt") if self_use is not None else "", GREEN),
        (t("Electricity price", "Stroomprijs"),
         f"€ {num(price, 2)}" if price is not None else (d.get("contract") or "–"),
         t("per kWh now", "per kWh nu") if price is not None else t("contract", "contract"), BLUE),
    ]
    return rows


def show(d):
    put("lucent.sol.big", unit(d.get("solar_w"), "W"))
    online = d.get("online")
    put("lucent.sol.p1", d.get("status") or "")
    put("lucent.sol.p2", "" if online is None else (t("inverter online", "omvormer online") if online else t("inverter asleep", "omvormer slaapt")))
    put("lucent.sol.p3", t(f"{d['contract']} contract", f"{d['contract']} contract") if d.get("contract") else "")
    advice = (d.get("advice") or "").strip()
    if advice and not advice.endswith((".", "!", "?")):
        advice += "."
    best = d.get("best_hour_tomorrow")
    if best:
        advice += t(f" The cheapest hour tomorrow is {best}.", f" Het goedkoopste uur morgen is {best}.")
    put("lucent.sol.advice", advice.strip())
    for n, (title, value, sub, colour) in enumerate(cards(d), 1):
        put(f"lucent.sol.{n}.t", title)
        put(f"lucent.sol.{n}.v", value)
        put(f"lucent.sol.{n}.s", sub)
        put(f"lucent.sol.{n}.c", colour)
    stamp = (d.get("updated") or "")[11:16]
    put("lucent.sol.hint", t(f"OK: open the dashboard  ·  updated {stamp}", f"OK: open het dashboard  ·  bijgewerkt {stamp}")
        if stamp else t("OK: open the dashboard", "OK: open het dashboard"))
    put("lucent.sol.err", "")


def picture(url):
    """The rings picture under a new name each time (Kodi keeps a picture with the same name in its cache)."""
    try:
        os.makedirs(DIR, exist_ok=True)
        with urllib.request.urlopen(url + "/beeld/kaart/stroom.png", timeout=8) as resp:
            body = resp.read()
        if len(body) < 1000 or body[:4] != b"\x89PNG":
            return
        name = os.path.join(DIR, f"kaart_{int(time.time())}.png")
        with open(name, "wb") as fh:
            fh.write(body)
        for old in os.listdir(DIR):
            if old.startswith("kaart_") and os.path.join(DIR, old) != name:
                try:
                    os.remove(os.path.join(DIR, old))
                except OSError:
                    pass
        put("lucent.sol.img", name)
    except Exception as error:  # noqa: BLE001 - an older Solis app has no picture: the numbers still show
        log(f"picture: {type(error).__name__}")


STATE = {"t": 0.0, "on": False}


def tick(force=False):
    """Called every few seconds by the helper: fetches at once when the tab comes into view, then every 30 seconds."""
    if not force:
        if not wanted():
            STATE["on"] = False
            return
        if STATE["on"] and time.time() - STATE["t"] < 30:
            return
    STATE["on"], STATE["t"] = True, time.time()
    url = base()
    try:
        with urllib.request.urlopen(url + "/lucent.json", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("unexpected answer")
    except Exception as error:  # noqa: BLE001
        log(f"lucent.json: {type(error).__name__}: {error}")
        if not HOME.getProperty("lucent.sol.1.t"):
            put("lucent.sol.big", "Solis")
            put("lucent.sol.err", t("No connection with Solis on your Homey. Check the Homey address in the settings of Solis "
                                    "Dashboard (Solis voor Homey 3.37.0 or newer is needed). OK on the tab opens the add-on.",
                                    "Geen verbinding met Solis op je Homey. Kijk het Homey-adres na bij de instellingen van "
                                    "Solis Dashboard (Solis voor Homey 3.37.0 of nieuwer is nodig). OK op het tabblad opent de add-on."))
        return
    show(data)
    picture(url)


if __name__ == "__main__":
    tick(force=True)
