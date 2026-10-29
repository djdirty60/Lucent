# -*- coding: utf-8 -*-
"""Lucent: setup assistant - the most important settings and logins, step by step.

    RunScript(special://skin/scripts/setup.py)          open it (Settings > About > Setup assistant)
    RunScript(special://skin/scripts/setup.py,first)    from Home: only the very first time (Skin.String lucent.setup.done)

Every step says what it is for, shows how it stands right now (green tick / orange note) and has buttons that set it
up. The state is looked at again every two seconds, so after linking Trakt or installing an add-on the tick appears
by itself. Nothing is required: every step can be skipped, and the assistant can be opened again later.
"""
import json
import sys
import threading

import xbmc
import xbmcaddon
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
DONE = "lucent.setup.done"
SEREN = "plugin.video.seren"
IPTV = "pvr.iptvsimple"
A4K = "service.subtitles.a4ksubtitles"
SUBS = "service.subtitles.lucent"
LIB = "script.lucent.library"
GREEN, ORANGE, GREY = "FF4CC38A", "FFE8A33D", "FF8A96A3"


def t(en, nl):
    return nl if NL else en


def log(text):
    xbmc.log(f"[skin.lucent] setup: {text}", xbmc.LOGINFO)


def cond(text):
    return xbmc.getCondVisibility(text)


def rpc(method, params=None):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result")
    except Exception as error:  # noqa: BLE001
        log(f"{method}: {error}")
        return None


def setting(addon_id, key):
    try:
        return xbmcaddon.Addon(addon_id).getSetting(key)
    except Exception:  # noqa: BLE001 - not installed
        return ""


def has(addon_id):
    return cond(f"System.HasAddon({addon_id})")


def install(addon_id):
    xbmc.executebuiltin(f"InstallAddon({addon_id})")


def run(builtin):
    xbmc.executebuiltin(builtin)


# ----------------------------------------------------------------------------- the steps
# each: key, icon, title, body, status() -> (state 'ok' | 'todo' | 'info', text), actions() -> [(label, function)]

def st_welcome():
    return "info", ""


def ac_welcome():
    return []


def st_seren():
    if not has(SEREN):
        return "todo", t("Seren is not installed", "Seren is nog niet geïnstalleerd")
    if not setting(SEREN, "trakt.auth"):
        return "todo", t("Seren is there - Trakt is not linked yet", "Seren staat erop - Trakt is nog niet gekoppeld")
    user = setting(SEREN, "trakt.username")
    return "ok", t(f"Linked to Trakt{' as ' + user if user else ''}", f"Gekoppeld met Trakt{' als ' + user if user else ''}")


def ac_seren():
    if not has(SEREN):
        return [(t("Install Seren", "Seren installeren"), lambda: install(SEREN))]
    out = []
    if not setting(SEREN, "trakt.auth"):
        out.append((t("Link Trakt", "Trakt koppelen"), lambda: run(f"RunPlugin(plugin://{SEREN}/?action=authTrakt)")))
    out.append((t("Seren settings", "Seren-instellingen"), lambda: run(f"Addon.OpenSettings({SEREN})")))
    return out


def tmdb_key():
    try:
        import info
        info._KEY["time"] = 0.0                       # always look again
        return info.tmdb_key()
    except Exception as error:  # noqa: BLE001
        log(f"tmdb key: {error}")
        return ""


def st_tmdb():
    if tmdb_key():
        return "ok", t("A TMDb key is set", "Er is een TMDb-sleutel ingesteld")
    return "todo", t("No TMDb key yet", "Nog geen TMDb-sleutel")


def ac_tmdb():
    def enter():
        import info
        info.set_tmdb_key()
    return [(t("Enter key", "Sleutel invoeren"), enter)]


def tv_channels():
    result = rpc("PVR.GetChannels", {"channelgroupid": "alltv", "limits": {"end": 1}}) or {}
    return int((result.get("limits") or {}).get("total") or 0)


def st_iptv():
    if not cond(f"System.HasAddon({IPTV})"):
        if xbmc.getInfoLabel(f"System.AddonVersion({IPTV})"):                # installed, but switched off
            return "todo", t("IPTV Simple Client is switched off", "IPTV Simple Client staat uit")
        return "todo", t("IPTV Simple Client is not installed (no IPTV? Skip this step)",
                         "IPTV Simple Client staat er nog niet op (geen IPTV? Sla over)")
    count = tv_channels()
    if count:
        return "ok", t(f"{count} TV channels", f"{count} tv-zenders")
    return "todo", t("No channels yet: fill in your channel list (M3U) and guide (EPG)",
                     "Nog geen zenders: vul je zenderlijst (M3U) en gids (EPG) in")


def ac_iptv():
    if not cond(f"System.HasAddon({IPTV})"):
        if xbmc.getInfoLabel(f"System.AddonVersion({IPTV})"):
            return [(t("Switch on", "Aanzetten"), lambda: rpc("Addons.SetAddonEnabled", {"addonid": IPTV, "enabled": True}))]
        return [(t("Install IPTV Simple Client", "IPTV Simple Client installeren"), lambda: install(IPTV))]
    out = [(t("Channel list and guide", "Zenderlijst en gids"), lambda: run(f"Addon.OpenSettings({IPTV})"))]
    if tv_channels():
        out.append((t("Open the TV guide", "Tv-gids openen"), lambda: run("ActivateWindow(TVGuide)")))
    return out


def subs_default():
    value = (rpc("Settings.GetSettingValue", {"setting": "subtitles.movie"}) or {}).get("value")
    return value == (SUBS if has(SUBS) else A4K)


def subs_keys():
    """(OpenSubtitles key + login filled in, SubDL key filled in) of Lucent Ondertitels."""
    try:
        import xbmcaddon
        addon = xbmcaddon.Addon(SUBS)
        return (bool(addon.getSetting("os_key").strip() and addon.getSetting("os_user").strip() and addon.getSetting("os_pass")),
                bool(addon.getSetting("subdl_key").strip()))
    except Exception:  # noqa: BLE001
        return False, False


def st_subs():
    if not has(SUBS):
        if has(A4K):
            return "todo", t("A4KSubtitles is used; Lucent Subtitles (faster, more Dutch) is not installed yet",
                             "A4KSubtitles wordt gebruikt; Lucent Ondertitels (sneller, meer Nederlands) staat er nog niet op")
        return "todo", t("No subtitle add-on installed", "Geen ondertitel-add-on geïnstalleerd")
    os_ok, subdl_ok = subs_keys()
    parts = [t("Lucent Subtitles is the default", "Lucent Ondertitels is de standaard") if subs_default()
             else t("Lucent Subtitles is not the default yet", "Lucent Ondertitels is nog niet de standaard"),
             "OpenSubtitles ✓" if os_ok else t("OpenSubtitles: no account", "OpenSubtitles: geen account"),
             "SubDL ✓" if subdl_ok else t("SubDL: no key", "SubDL: geen sleutel")]
    parts.append(t("searching automatically", "zoekt automatisch") if cond("Skin.HasSetting(nuvio.autosubs)")
                 else t("not searching automatically", "zoekt niet automatisch"))
    return ("ok" if subs_default() and (os_ok or subdl_ok) else "todo"), "  ·  ".join(parts)


def ac_subs():
    if not has(SUBS):
        return [(t("Install Lucent Subtitles", "Lucent Ondertitels installeren"), lambda: install(SUBS))]
    out = [(t("Accounts and keys", "Accounts en sleutels"), lambda: run(f"Addon.OpenSettings({SUBS})"))]
    if not subs_default():
        out.append((t("Make it the default", "Als standaard instellen"), lambda: run("RunScript(special://skin/scripts/subtitles.py,default)")))
    auto = cond("Skin.HasSetting(nuvio.autosubs)")
    out.append((t("Automatic search: on", "Automatisch zoeken: aan") if auto else t("Automatic search: off", "Automatisch zoeken: uit"),
                lambda: run("Skin.ToggleSetting(nuvio.autosubs)")))
    out.append((t("Gemini key (AI)", "Gemini-sleutel (AI)"), lambda: run("RunScript(special://skin/scripts/subs_live.py,key)")))
    return out


EVERY_NEXT = {"6": "12", "12": "24", "24": "0"}


def st_library():
    if not has(LIB):
        return "todo", t("Lucent Library is not installed", "Lucent Bibliotheek is niet geïnstalleerd")
    home = xbmcgui.Window(10000)
    movies, shows = home.getProperty("lucent.lib.movies"), home.getProperty("lucent.lib.shows")
    every = xbmc.getInfoLabel("Skin.String(lucent.lib.every)") or "6"
    when = t("updates by itself every {0} hours", "werkt zichzelf om de {0} uur bij").format(every) if every != "0" \
        else t("does not update by itself", "werkt niet vanzelf bij")
    if movies or shows:
        return "ok", t(f"{movies or 0} films, {shows or 0} series  ·  {when}", f"{movies or 0} films, {shows or 0} series  ·  {when}")
    return "todo", t(f"Not filled yet  ·  {when}", f"Nog niet gevuld  ·  {when}")


def ac_library():
    if not has(LIB):
        return [(t("Install", "Installeren"), lambda: install(LIB))]
    every = xbmc.getInfoLabel("Skin.String(lucent.lib.every)") or "6"
    label = t("Automatic: off", "Automatisch: uit") if every == "0" else t(f"Automatic: every {every} h", f"Automatisch: om de {every} uur")
    return [(t("Update now", "Nu bijwerken"), lambda: run(f"RunScript({LIB},update)")),
            (label, lambda: run(f'Skin.SetString(lucent.lib.every,{EVERY_NEXT.get(every, "6")})'))]


def st_look():
    lite = cond("Skin.HasSetting(lucent.lite)")
    fy = not cond("Skin.HasSetting(lucent.fy.off)")
    return "ok", "  ·  ".join([t("Light mode on", "Lichte modus aan") if lite else t("Light mode off", "Lichte modus uit"),
                               t("Tonight for you on", "Vanavond voor jou aan") if fy else t("Tonight for you off", "Vanavond voor jou uit")])


def ac_look():
    lite = cond("Skin.HasSetting(lucent.lite)")
    fy = not cond("Skin.HasSetting(lucent.fy.off)")
    return [(t("Light mode: on", "Lichte modus: aan") if lite else t("Light mode: off", "Lichte modus: uit"),
             lambda: run("Skin.ToggleSetting(lucent.lite)")),
            (t("Tonight for you: on", "Vanavond voor jou: aan") if fy else t("Tonight for you: off", "Vanavond voor jou: uit"),
             lambda: run("Skin.ToggleSetting(lucent.fy.off)")),
            (t("Menu and rows", "Menu en rijen"), lambda: run("RunScript(special://skin/scripts/menu.py)"))]


def kodi_setting(key):
    return (rpc("Settings.GetSettingValue", {"setting": key}) or {}).get("value")


def set_kodi(key, value):
    rpc("Settings.SetSettingValue", {"setting": key, "value": value})


def ram_mb():
    try:
        return int("".join(ch for ch in xbmc.getInfoLabel("System.Memory(total)") if ch.isdigit()) or 0)
    except ValueError:
        return 0


def buffer_advice():
    """A bigger buffer than Kodi's 64 MB smooths out streams. Kodi can use up to three times this size, so it follows
    the memory of the box: 96 MB up to 2 GB, 192 MB up to 4 GB, 384 MB above that."""
    ram = ram_mb()
    return 96 if 0 < ram <= 2200 else (192 if ram <= 4400 else 384)


PASS = ("audiooutput.ac3passthrough", "audiooutput.eac3passthrough", "audiooutput.dtspassthrough",
        "audiooutput.truehdpassthrough", "audiooutput.dtshdpassthrough")


def st_play():
    size, advice = kodi_setting("filecache.memorysize"), buffer_advice()
    rate = kodi_setting("videoplayer.adjustrefreshrate")
    passthrough = kodi_setting("audiooutput.passthrough")
    parts = [t(f"Buffer {size} MB", f"Buffer {size} MB") + ("" if (size or 0) >= advice else t(f" (advice {advice})", f" (advies {advice})")),
             t("frame rate follows the video", "beeldfrequentie volgt de video") if rate in (1, 2, 3) else t("frame rate fixed", "beeldfrequentie vast"),
             t("sound to amplifier", "geluid naar versterker") if passthrough else t("Kodi decodes the sound", "Kodi zet het geluid om")]
    return ("ok" if (size or 0) >= advice and rate in (1, 2, 3) else "todo"), "  ·  ".join(parts)


def ac_play():
    advice = buffer_advice()
    rate = kodi_setting("videoplayer.adjustrefreshrate")
    passthrough = kodi_setting("audiooutput.passthrough")

    def buffer():
        set_kodi("filecache.memorysize", advice)
        set_kodi("filecache.readfactor", 400)                  # fill the buffer 4x faster than the video plays

    def toggle_rate():
        set_kodi("videoplayer.adjustrefreshrate", 0 if rate in (1, 2, 3) else 2)   # 2: on start and stop

    def toggle_pass():
        on = not passthrough
        set_kodi("audiooutput.passthrough", on)
        if on:
            for key in PASS:
                set_kodi(key, True)
    out = []
    if (kodi_setting("filecache.memorysize") or 0) < advice:
        out.append((t(f"Buffer {advice} MB (advice)", f"Buffer {advice} MB (advies)"), buffer))
    out.append((t("Frame rate: follows video", "Beeldfrequentie: volgt video") if rate in (1, 2, 3) else t("Frame rate: fixed", "Beeldfrequentie: vast"), toggle_rate))
    out.append((t("Sound to amplifier: on", "Geluid naar versterker: aan") if passthrough else t("Sound to amplifier: off", "Geluid naar versterker: uit"), toggle_pass))
    out.append((t("Player settings", "Spelerinstellingen"), lambda: run("ActivateWindow(PlayerSettings)")))
    return out


def st_backup():
    import backup
    last = backup.last_backup()
    if last:
        return "ok", t(f"Last backup: {last}", f"Laatste back-up: {last}")
    return "todo", t("No backup yet", "Nog geen back-up")


def ac_backup():
    return [(t("Make a backup", "Back-up maken"), lambda: run("RunScript(special://skin/scripts/backup.py,backup)")),
            (t("Restore", "Herstellen"), lambda: run("RunScript(special://skin/scripts/backup.py,restore)"))]


STEPS = [
    ("welcome", "icons/sparkle.png", ("Welcome", "Welkom"),
     ("Welcome to Lucent. In a few steps we set up what matters most: Seren with your Trakt account, a TMDb key for "
      "pictures and information, your IPTV channels, subtitles and your own library.\n\nEvery step shows how it stands "
      "right now. Something you do not use, you simply skip. You can open this assistant again later: "
      "Settings > About > Setup assistant.",
      "Welkom bij Lucent. In een paar stappen zetten we het belangrijkste klaar: Seren met je Trakt-account, een "
      "TMDb-sleutel voor plaatjes en informatie, je IPTV-zenders, ondertitels en je eigen bibliotheek.\n\nBij elke stap "
      "zie je meteen hoe het nu staat. Wat je niet gebruikt, sla je gewoon over. Je kunt deze assistent later opnieuw "
      "openen: Instellingen > Over > Setup-assistent."), st_welcome, ac_welcome),
    ("seren", "icons/trakt.png", ("Seren and Trakt", "Seren en Trakt"),
     ("Seren finds the streams and plays films and series. Your Trakt account keeps your lists, your collection and "
      "what you watched - Lucent reads its rows, the calendar and 'Tonight for you' from it.\n\nLink Trakt: a code "
      "appears, enter it on trakt.tv/activate (phone or computer).",
      "Seren zoekt de bronnen en speelt films en series af. Je Trakt-account bewaart je lijsten, je collectie en wat "
      "je gezien hebt - daar haalt Lucent zijn rijen, de kalender en 'Vanavond voor jou' uit.\n\nTrakt koppelen: er "
      "verschijnt een code, vul die in op trakt.tv/activate (telefoon of computer)."), st_seren, ac_seren),
    ("tmdb", "icons/movies.png", ("TMDb key", "TMDb-sleutel"),
     ("TMDb (The Movie Database) supplies posters, logos, cast, studios and trailers. A key of your own is free and "
      "makes everything faster and more complete.\n\nGet one: make an account on themoviedb.org, then Settings > API > "
      "'Create' (personal use). Copy the 'API key' (the short one, 32 characters).",
      "TMDb (The Movie Database) levert posters, logo's, acteurs, studio's en trailers. Een eigen sleutel is gratis en "
      "maakt alles sneller en vollediger.\n\nZo krijg je er een: maak een account op themoviedb.org, dan Instellingen > "
      "API > 'Aanmaken' (persoonlijk gebruik). Kopieer de 'API-sleutel' (de korte, 32 tekens)."), st_tmdb, ac_tmdb),
    ("iptv", "icons/tv.png", ("Live TV (IPTV)", "Live tv (IPTV)"),
     ("For live TV Kodi uses IPTV Simple Client. Fill in the link to your channel list (M3U) and to the TV guide (EPG/XMLTV) "
      "from your provider. With an Xtream login, your provider usually also gives an M3U link "
      "(…/get.php?username=…&password=…&type=m3u_plus).\n\nAfter that Lucent shows the TV guide, the Sport tab "
      "and live scores on the channels.",
      "Voor live tv gebruikt Kodi IPTV Simple Client. Vul daarin de link naar je zenderlijst (M3U) en naar de tv-gids "
      "(EPG/XMLTV) van je aanbieder in. Heb je een Xtream-login, dan geeft je aanbieder meestal ook een M3U-link "
      "(…/get.php?username=…&password=…&type=m3u_plus).\n\nDaarna toont Lucent de tv-gids, de Sport-tab en live "
      "standen bij de zenders."), st_iptv, ac_iptv),
    ("play", "icons/videosettings.png", ("Picture and sound", "Beeld en geluid"),
     ("Three things that make watching smoother. A bigger buffer: Kodi loads more of the stream ahead, so it stutters less "
      "(Lucent picks a size that suits the memory of this box). Frame rate that follows the video: films are made at 24 frames "
      "a second; when the TV switches to 23.976/24 Hz, panning shots run without jerks. Sound to the amplifier (passthrough): "
      "Dolby, DTS and Atmos go untouched to your soundbar or receiver - only switch it on when you have one.\n\nHDR and Dolby Vision "
      "are passed on by themselves on CoreELEC.",
      "Drie dingen die het kijken soepeler maken. Een grotere buffer: Kodi laadt meer van de stream vooruit, zodat het minder "
      "hapert (Lucent kiest een grootte die past bij het geheugen van deze box). Beeldfrequentie die de video volgt: films zijn "
      "gemaakt met 24 beelden per seconde; schakelt de tv naar 23,976/24 Hz, dan lopen pannende beelden zonder schokjes. Geluid naar "
      "de versterker (passthrough): Dolby, DTS en Atmos gaan onbewerkt naar je soundbar of receiver - zet dit alleen aan als je die hebt."
      "\n\nHDR en Dolby Vision geeft CoreELEC vanzelf door."), st_play, ac_play),
    ("subs", "icons/subtitles.png", ("Subtitles", "Ondertitels"),
     ("Lucent Subtitles asks OpenSubtitles, SubDL and Podnapisi at the same time and puts the subtitles that fit your "
      "video exactly first. Make two free accounts and fill them in under 'Accounts and keys':\n"
      "1. opensubtitles.com: sign up, then Profile > API consumers > New consumer (the API key) - plus your user name and password.\n"
      "2. subdl.com: sign up, then Account > API key.\nOptional: a free Gemini key (aistudio.google.com) translates English subtitles.",
      "Lucent Ondertitels vraagt OpenSubtitles, SubDL en Podnapisi tegelijk en zet de ondertitels die precies bij je video "
      "passen bovenaan. Maak twee gratis accounts en vul ze in bij 'Accounts en sleutels':\n"
      "1. opensubtitles.com: aanmelden, dan Profiel > API consumers > New consumer (de API-sleutel) - plus je gebruikersnaam en wachtwoord.\n"
      "2. subdl.com: aanmelden, dan Account > API-sleutel.\nOptioneel: een gratis Gemini-sleutel (aistudio.google.com) vertaalt Engelse ondertitels."), st_subs, ac_subs),
    ("library", "icons/library.png", ("Lucent Library", "Lucent Bibliotheek"),
     ("Lucent Library turns your Trakt collection into Kodi's own library: films and series with their own pages, "
      "'Continue watching' and 'Next episode' rows, and scores.\n\nImportant: first load your whole collection in Seren "
      "(Movies > My movies and TV shows > My shows) until everything is in, then press 'Update now'.",
      "Lucent Bibliotheek maakt van je Trakt-collectie de eigen bibliotheek van Kodi: films en series met eigen pagina's, "
      "rijen 'Verder kijken' en 'Volgende aflevering', en scores.\n\nBelangrijk: laad eerst je hele collectie in Seren "
      "(Films > Mijn films en Series > Mijn series) tot alles binnen is, en druk dan op 'Nu bijwerken'."), st_library, ac_library),
    ("look", "icons/palette.png", ("Look", "Weergave"),
     ("Light mode keeps Lucent quick on boxes with 2 GB of memory or less (fewer rows, no poster glow) - Lucent switches "
      "it on by itself on such boxes. 'Tonight for you' is a row on Home with titles that fit the moment of the day.\n\n"
      "Colours, the menu and the rows on Home can be changed any time in Skin settings.",
      "Lichte modus houdt Lucent vlot op boxen met 2 GB geheugen of minder (minder rijen, geen postergloed) - op zulke "
      "boxen zet Lucent hem zelf aan. 'Vanavond voor jou' is een rij op het startscherm met titels die passen bij het "
      "moment van de dag.\n\nKleuren, het menu en de rijen op het startscherm pas je altijd aan in Skin-instellingen."), st_look, ac_look),
    ("backup", "icons/cloud.png", ("Backup", "Back-up"),
     ("Save everything you set up in one file: Lucent's settings and menu, your favourites, the keys (TMDb, Gemini), the "
      "settings of Seren, IPTV Simple and Lucent Library, and your sources. Put it on a USB stick or a network share, and "
      "after a new installation (or on a second box) 'Restore' puts it all back.\n\nThe file holds your logins (Trakt, IPTV): "
      "keep it to yourself.",
      "Bewaar alles wat je hebt ingesteld in één bestand: de instellingen en het menu van Lucent, je favorieten, de sleutels "
      "(TMDb, Gemini), de instellingen van Seren, IPTV Simple en Lucent Bibliotheek, en je bronnen. Zet het op een USB-stick of "
      "netwerkmap; na een nieuwe installatie (of op een tweede box) zet 'Herstellen' alles terug.\n\nIn het bestand staan je "
      "inlogs (Trakt, IPTV): houd het voor jezelf."), st_backup, ac_backup),
]


class Setup(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.step = 0
        self.actions = []
        self.closing = False
        self.lock = threading.Lock()

    def onInit(self):
        self.setProperty("heading", t("Set up Lucent", "Lucent instellen"))
        self.items = []
        for key, icon, title, _body, _st, _ac in STEPS:
            li = xbmcgui.ListItem(title[1 if NL else 0])
            li.setArt({"icon": icon})
            self.items.append(li)
        self.getControl(100).addItems(self.items)
        self.show_step(0)
        threading.Thread(target=self.watch, daemon=True).start()

    # ----------------------------------------------------------------- drawing
    def show_step(self, index):
        self.step = max(0, min(index, len(STEPS) - 1))
        key, _icon, title, body, _st, _ac = STEPS[self.step]
        self.setProperty("stepno", t(f"Step {self.step + 1} of {len(STEPS)}", f"Stap {self.step + 1} van {len(STEPS)}"))
        self.setProperty("title", title[1 if NL else 0])
        self.setProperty("body", body[1 if NL else 0])
        self.setProperty("prev", t("Back", "Vorige") if self.step else "")
        last = self.step == len(STEPS) - 1
        self.setProperty("next", t("Finish", "Klaar") if last else (t("Start", "Beginnen") if self.step == 0 else t("Next", "Volgende")))
        self.setProperty("later", "" if last else t("Set up later", "Later instellen"))
        for n, li in enumerate(self.items):
            li.setProperty("current", "1" if n == self.step else "")
        self.getControl(100).selectItem(self.step)
        self.refresh()
        self.setFocusId(300 if self.actions else 402)

    def refresh(self):
        """Status of every step (ticks in the list) and the buttons of this step."""
        with self.lock:
            for n, (_k, _i, _t, _b, status, _a) in enumerate(STEPS):
                try:
                    state, text = status()
                except Exception as error:  # noqa: BLE001
                    log(f"status {STEPS[n][0]}: {error}")
                    state, text = "info", ""
                self.items[n].setProperty("state", state)
                if n == self.step:
                    self.setProperty("status", text)
                    self.setProperty("statecolor", {"ok": GREEN, "todo": ORANGE}.get(state, GREY))
            try:
                self.actions = STEPS[self.step][5]()[:4]
            except Exception as error:  # noqa: BLE001
                log(f"actions: {error}")
                self.actions = []
            for n in range(4):
                self.setProperty(f"act{n + 1}", self.actions[n][0] if n < len(self.actions) else "")

    def watch(self):
        """Look again every two seconds: linking Trakt or installing an add-on happens in other windows."""
        monitor = xbmc.Monitor()
        while not self.closing and not monitor.abortRequested():
            if monitor.waitForAbort(2):
                break
            if not self.closing:
                self.refresh()

    # ----------------------------------------------------------------- input
    def onClick(self, control_id):
        if control_id == 100:
            self.show_step(self.getControl(100).getSelectedPosition())
        elif 301 <= control_id <= 304:
            n = control_id - 301
            if n < len(self.actions):
                try:
                    self.actions[n][1]()
                except Exception as error:  # noqa: BLE001
                    log(f"action: {error}")
                xbmc.sleep(300)
                self.refresh()
        elif control_id == 401:
            self.show_step(self.step - 1)
        elif control_id == 402:
            if self.step == len(STEPS) - 1:
                self.finish()
            else:
                self.show_step(self.step + 1)
        elif control_id == 403:
            self.finish(later=True)

    def onAction(self, action):
        if action.getId() in (10, 92):                       # back / previous menu
            self.finish(later=True)

    def finish(self, later=False):
        self.closing = True
        xbmc.executebuiltin(f'Skin.SetString({DONE},"1")')
        if later:
            xbmcgui.Dialog().notification("Lucent", t("Setup assistant: Settings > About", "Setup-assistent: Instellingen > Over"),
                                          "special://skin/resources/icon.png", 4000, False)
        self.close()


def open_window():
    path = xbmcaddon.Addon("skin.lucent").getAddonInfo("path")
    window = Setup("Lucent_Setup.xml", path, "Default", "1080i")
    try:
        if has(LIB):
            xbmc.executebuiltin(f"RunScript({LIB},status)")   # film / series numbers for the library step
        window.doModal()
    finally:
        window.closing = True
        del window


if __name__ == "__main__":
    first = len(sys.argv) > 1 and sys.argv[1] == "first"
    if first:
        home = xbmcgui.Window(10000)
        if xbmc.getInfoLabel(f"Skin.String({DONE})") or home.getProperty("lucent.setup.shown"):
            sys.exit()
        home.setProperty("lucent.setup.shown", "1")          # once per Kodi start, even when closed with Back
        if xbmc.Monitor().waitForAbort(2):                    # let Home settle first
            sys.exit()
    open_window()
