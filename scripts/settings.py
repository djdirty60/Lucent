# -*- coding: utf-8 -*-
"""Lucent: the choices in the skin settings that need a list or a Kodi setting.

RunScript(special://skin/scripts/settings.py,<what>)
  sync        read Kodi's own settings into the labels of the skin settings page
  accent      colour theme            amoled      pure black surfaces (toggle)
  zoom        interface scale         ssdim       dim when idle (toggle)
  sstime      idle timeout            sslevel     dim strength
  landscape   landscape cards on Home watched     show / dim watched titles
  glow        edge glow on focused cards
  logos       where to put your own rating logos
  pauseinfo   pause screen delay      flags       own picture / sound logos
  reset       restore all skin settings
"""
import json
import sys

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

HEADING = "Lucent"
_NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
DIM = "screensaver.xbmc.builtin.dim"
LOGO_DIR = "special://profile/addon_data/skin.lucent/logos/"
FLAG_DIR = "special://profile/addon_data/skin.lucent/flags/"
FLAG_KEYS = ['8k', '4k', '1080', '720', 'sd', 'dolbyvision', 'hdr10plus', 'hdr10', 'hlg', 'hevc', 'av1', 'h264', 'vp9', 'atmos', 'dtsx', 'truehd', 'dtshd_ma', 'dtshd_hra', 'dts', 'eac3', 'ac3', 'aac', 'flac', 'opus', 'pcm', 'mp3', '71', '61', '51', '20', '10']


def tr(pair, *args):
    text = pair[1 if _NL else 0]
    return text.format(*args) if args else text


ACCENTS = [  # id, (en, nl)   — names as in Nuvio
    ("glass", ("Glass", "Glas")), ("white", ("White", "Wit")), ("crimson", ("Crimson", "Karmozijn")),
    ("emerald", ("Emerald", "Smaragd")), ("ocean", ("Ocean", "Oceaan")), ("violet", ("Violet", "Violet")),
    ("amber", ("Amber", "Amber")), ("gold", ("Gold", "Goud")), ("rose", ("Rose", "Roze")),
    ("rosegold", ("Rose Gold", "Roségoud")), ("copper", ("Copper", "Koper")), ("jade", ("Jade", "Jade")),
    ("arcticblue", ("Arctic Blue", "Arctisch blauw")), ("graphite", ("Graphite", "Grafiet")),
]
ZOOM = [-10, -6, -4, -2, 0, 2, 4, 6, 10]
SS_TIMES = [1, 2, 3, 5, 10, 15, 30]
SS_LEVELS = [(60, ("Gentle – the screen stays clearly visible", "Zacht – scherm blijft goed zichtbaar")),
             (30, ("Balanced – dark but readable", "Gebalanceerd – donker maar leesbaar")),
             (10, ("Strong – barely visible", "Sterk – nauwelijks zichtbaar"))]
LANDSCAPE = [("", ("Off", "Uit")), ("home", ("Home only", "Alleen startscherm"))]
WATCHED = [("", ("Show", "Tonen")), ("dim", ("Dim", "Dimmen"))]
PAUSE = [("3", ("After 3 seconds", "Na 3 seconden")), ("", ("After 5 seconds", "Na 5 seconden")),
         ("10", ("After 10 seconds", "Na 10 seconden")), ("15", ("After 15 seconds", "Na 15 seconden")),
         ("30", ("After 30 seconds", "Na 30 seconden")), ("60", ("After 1 minute", "Na 1 minuut")),
         ("off", ("Off", "Uit"))]
POSTERFOCUS = [("", ("Off", "Uit")), ("window", ("Trailer window with soft edge", "Trailervenster met zachte rand")),
               ("hero", ("Hero media", "Hero-media")), ("expand", ("Expanded card", "Uitgevouwen kaart"))]
TRAILER_DELAY = [("2", ("After 2 seconds", "Na 2 seconden")), ("", ("After 3 seconds", "Na 3 seconden")),
                 ("5", ("After 5 seconds", "Na 5 seconden")), ("8", ("After 8 seconds", "Na 8 seconden"))]
GLOW = [("off", ("Off", "Uit")), ("subtle", ("Subtle", "Subtiel")), ("", ("Balanced", "Gebalanceerd")),
        ("bold", ("Bold", "Sterk"))]


# ----------------------------------------------------------------------------- helpers
def jsonrpc(method, params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result")
    except Exception as error:  # noqa: BLE001
        xbmc.log(f"[skin.lucent] settings.py {method}: {error}", xbmc.LOGWARNING)
        return None


def kodi_get(setting):
    result = jsonrpc("Settings.GetSettingValue", {"setting": setting}) or {}
    return result.get("value")


def kodi_set(setting, value):
    return jsonrpc("Settings.SetSettingValue", {"setting": setting, "value": value})


def skin_string(name):
    return xbmc.getInfoLabel(f"Skin.String({name})")


def set_string(name, value):
    if value:
        xbmc.executebuiltin(f'Skin.SetString({name},"{value}")', True)
    else:
        xbmc.executebuiltin(f"Skin.Reset({name})", True)


def set_bool(name, on):
    xbmc.executebuiltin(f"Skin.SetBool({name})" if on else f"Skin.Reset({name})", True)


def has(name):
    return xbmc.getCondVisibility(f"Skin.HasSetting({name})")


def choose(heading, labels, current):
    preselect = current if 0 <= current < len(labels) else -1
    return xbmcgui.Dialog().select(heading, labels, preselect=preselect)


# ----------------------------------------------------------------------------- colour theme
def apply_colours():
    accent = skin_string("nuvio.accent") or "glass"
    name = accent + ("-amoled" if has("nuvio.amoled") else "")
    value = "SKINDEFAULT" if name == "glass" else name
    if kodi_get("lookandfeel.skincolors") != value:
        kodi_set("lookandfeel.skincolors", value)  # Kodi reloads the skin by itself


def pick_accent():
    ids = [a for a, _n in ACCENTS]
    current = skin_string("nuvio.accent") or "glass"
    choice = choose(tr(("Colour theme", "Kleurthema")), [tr(n) for _a, n in ACCENTS], ids.index(current) if current in ids else 0)
    if choice < 0:
        return
    accent, name = ACCENTS[choice]
    set_string("nuvio.accent", "" if accent == "glass" else accent)
    set_string("nuvio.accent.label", tr(name))
    apply_colours()


def toggle_amoled():
    set_bool("nuvio.amoled", not has("nuvio.amoled"))
    apply_colours()


# ----------------------------------------------------------------------------- interface scale
def zoom_label(value):
    return tr(("Standard", "Standaard")) if value == 0 else f"{value:+d}%"


def pick_zoom():
    current = kodi_get("lookandfeel.skinzoom") or 0
    labels = [zoom_label(z) for z in ZOOM]
    choice = choose(tr(("Interface scale", "Schaal van de interface")), labels, ZOOM.index(current) if current in ZOOM else 4)
    if choice >= 0:
        set_string("nuvio.zoom.label", labels[choice])
        kodi_set("lookandfeel.skinzoom", ZOOM[choice])


# ----------------------------------------------------------------------------- screensaver
def toggle_dim():
    on = kodi_get("screensaver.mode") == DIM
    kodi_set("screensaver.mode", "" if on else DIM)
    set_bool("nuvio.ss.dim", not on)


def pick_time():
    current = kodi_get("screensaver.time") or 3
    labels = [tr(("{0} minutes", "{0} minuten"), m) if m > 1 else tr(("1 minute", "1 minuut")) for m in SS_TIMES]
    choice = choose(tr(("Idle timeout", "Wachttijd")), labels, SS_TIMES.index(current) if current in SS_TIMES else -1)
    if choice >= 0:
        kodi_set("screensaver.time", SS_TIMES[choice])
        set_string("nuvio.ss.time.label", labels[choice])


def pick_level():
    try:
        addon = xbmcaddon.Addon(DIM)
        current = int(addon.getSetting("level") or 20)
    except Exception:  # noqa: BLE001
        return
    levels = [lv for lv, _n in SS_LEVELS]
    nearest = min(range(len(levels)), key=lambda i: abs(levels[i] - current))
    choice = choose(tr(("Dim strength", "Dimsterkte")), [tr(n) for _l, n in SS_LEVELS], nearest)
    if choice >= 0:
        addon.setSetting("level", str(levels[choice]))
        set_string("nuvio.ss.level.label", tr(SS_LEVELS[choice][1]).split(" – ")[0])


# ----------------------------------------------------------------------------- simple lists
def pick_option(name, options, heading):
    values = [v for v, _n in options]
    current = skin_string(name)
    choice = choose(heading, [tr(n) for _v, n in options], values.index(current) if current in values else 0)
    if choice >= 0:
        set_string(name, values[choice])
        set_string(name + ".label", tr(options[choice][1]))


# ----------------------------------------------------------------------------- logos
def explain_logos():
    if not xbmcvfs.exists(LOGO_DIR):
        xbmcvfs.mkdirs(LOGO_DIR)
    real = xbmcvfs.translatePath(LOGO_DIR)
    xbmcgui.Dialog().ok(HEADING, tr((
        "Put your own logos in this folder as imdb.png, tmdb.png and trakt.png:[CR][B]{0}[/B][CR]"
        "The info page then shows the logo instead of the name.",
        "Zet je eigen logo's als imdb.png, tmdb.png en trakt.png in deze map:[CR][B]{0}[/B][CR]"
        "De infopagina toont dan het logo in plaats van de naam."), real))


def scan_flags():
    """Remember which own picture / sound logos exist (shown on the pause screen)."""
    for key in FLAG_KEYS:
        path = FLAG_DIR + key + ".png"
        value = path if xbmcvfs.exists(path) else ""
        if skin_string("nuvio.flag." + key) != value:
            set_string("nuvio.flag." + key, value)


def explain_flags():
    if not xbmcvfs.exists(FLAG_DIR):
        xbmcvfs.mkdirs(FLAG_DIR)
    real = xbmcvfs.translatePath(FLAG_DIR)
    xbmcgui.Dialog().textviewer(HEADING, tr((
        "Put your own logos (PNG, preferably white on transparent) in this folder:[CR][B]{0}[/B][CR][CR]"
        "Use these file names:[CR]{1}[CR][CR]The pause screen then shows your logo instead of the built-in badge. "
        "Open the skin settings once more after adding files.",
        "Zet je eigen logo's (PNG, het liefst wit op transparant) in deze map:[CR][B]{0}[/B][CR][CR]"
        "Gebruik deze bestandsnamen:[CR]{1}[CR][CR]Het pauzescherm toont dan jouw logo in plaats van het ingebouwde label. "
        "Open de skin-instellingen nog een keer nadat je bestanden hebt toegevoegd."),
        real, ", ".join(k + ".png" for k in FLAG_KEYS)))
    scan_flags()


def pick_posterfocus():
    pick_option("nuvio.posterfocus", POSTERFOCUS, tr(("Trailer on focus", "Trailer bij focus")))
    if skin_string("nuvio.posterfocus"):
        if not xbmc.getCondVisibility("System.HasAddon(plugin.video.youtube)"):
            xbmc.executebuiltin("InstallAddon(plugin.video.youtube)", True)
        # the trailer helper runs from the Home screen; start it now (it quits if it already runs)
        xbmc.executebuiltin("RunScript(special://skin/scripts/trailers.py)")


# ----------------------------------------------------------------------------- sync + reset
def sync():
    """Fill the labels of the settings page from Kodi's own settings."""
    zoom = kodi_get("lookandfeel.skinzoom") or 0
    set_string("nuvio.zoom.label", zoom_label(zoom))
    set_bool("nuvio.ss.dim", kodi_get("screensaver.mode") == DIM)
    minutes = kodi_get("screensaver.time") or 3
    set_string("nuvio.ss.time.label", tr(("{0} minutes", "{0} minuten"), minutes) if minutes > 1 else tr(("1 minute", "1 minuut")))
    try:
        level = int(xbmcaddon.Addon(DIM).getSetting("level") or 20)
        nearest = min(SS_LEVELS, key=lambda item: abs(item[0] - level))
        set_string("nuvio.ss.level.label", tr(nearest[1]).split(" – ")[0])
    except Exception:  # noqa: BLE001
        pass
    accent = skin_string("nuvio.accent") or "glass"
    set_string("nuvio.accent.label", tr(dict(ACCENTS).get(accent, ACCENTS[0][1])))
    scan_flags()
    for name, options in (("nuvio.landscape", LANDSCAPE), ("nuvio.watched", WATCHED), ("nuvio.glow", GLOW),
                          ("nuvio.pauseinfo", PAUSE), ("nuvio.posterfocus", POSTERFOCUS),
                          ("nuvio.trailer.delay", TRAILER_DELAY)):
        set_string(name + ".label", tr(dict(options).get(skin_string(name), options[0][1])))


def reset_all():
    if xbmcgui.Dialog().yesno(HEADING, tr(("Restore all skin settings? Your menu and widgets stay as they are.",
                                           "Alle skin-instellingen herstellen? Je menu en widgets blijven zoals ze zijn."))):
        for name in ("nuvio.accent", "nuvio.accent.label", "nuvio.landscape", "nuvio.watched", "nuvio.glow",
                     "nuvio.pauseinfo", "nuvio.posterfocus", "nuvio.trailer.delay"):
            set_string(name, "")
        for name in ("nuvio.amoled", "nuvio.posterlabels.hide", "nuvio.sideicons.hide", "nuvio.fulldate",
                     "nuvio.fullbackdrop", "nuvio.info.hideratings", "nuvio.info.hidetrailer", "nuvio.hideclock",
                     "nuvio.pauseinfo.hideflags"):
            set_bool(name, False)
        kodi_set("lookandfeel.skinzoom", 0)
        apply_colours()
        sync()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "sync"
    {
        "sync": sync, "accent": pick_accent, "amoled": toggle_amoled, "zoom": pick_zoom,
        "ssdim": toggle_dim, "sstime": pick_time, "sslevel": pick_level, "logos": explain_logos,
        "landscape": lambda: pick_option("nuvio.landscape", LANDSCAPE, tr(("Landscape posters", "Liggende posters"))),
        "watched": lambda: pick_option("nuvio.watched", WATCHED, tr(("Watched titles", "Bekeken titels"))),
        "glow": lambda: pick_option("nuvio.glow", GLOW, tr(("Edge glow", "Randgloed"))),
        "pauseinfo": lambda: pick_option("nuvio.pauseinfo", PAUSE, tr(("Show info after", "Info tonen na"))),
        "flags": explain_flags,
        "posterfocus": pick_posterfocus,
        "trailerdelay": lambda: pick_option("nuvio.trailer.delay", TRAILER_DELAY, tr(("Start trailer after", "Trailer starten na"))),
        "reset": reset_all,
    }.get(what, sync)()
