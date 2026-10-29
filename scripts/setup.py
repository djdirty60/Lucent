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


def a4k_default():
    value = (rpc("Settings.GetSettingValue", {"setting": "subtitles.movie"}) or {}).get("value")
    return value == A4K


def st_subs():
    if not has(A4K):
        return "todo", t("A4KSubtitles is not installed", "A4KSubtitles is nog niet geïnstalleerd")
    parts = [t("A4KSubtitles is the default", "A4KSubtitles is de standaard") if a4k_default()
             else t("A4KSubtitles is there but not the default", "A4KSubtitles staat erop maar is niet de standaard")]
    parts.append(t("searching automatically", "zoekt automatisch") if cond("Skin.HasSetting(nuvio.autosubs)")
                 else t("not searching automatically", "zoekt niet automatisch"))
    if xbmc.getInfoLabel("Skin.String(lucent.gemini.key)"):
        parts.append(t("AI translation ready", "AI-vertalen klaar"))
    return ("ok" if a4k_default() else "todo"), "  ·  ".join(parts)


def ac_subs():
    if not has(A4K):
        return [(t("Install A4KSubtitles", "A4KSubtitles installeren"), lambda: install(A4K))]
    out = []
    if not a4k_default():
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
    ("subs", "icons/subtitles.png", ("Subtitles", "Ondertitels"),
     ("A4KSubtitles searches several subtitle sites at once. Lucent shows all results in one list, in your language "
      "first, and can put a subtitle in sync with the video.\n\nOptional: with a free Gemini key (aistudio.google.com) "
      "Lucent translates the best English subtitle into your language when there is none.",
      "A4KSubtitles zoekt op meerdere ondertitelsites tegelijk. Lucent toont alles in één lijst, jouw taal eerst, en kan "
      "een ondertitel gelijkzetten met de video.\n\nOptioneel: met een gratis Gemini-sleutel (aistudio.google.com) vertaalt "
      "Lucent de beste Engelse ondertitel naar jouw taal als er geen is."), st_subs, ac_subs),
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
                self.actions = STEPS[self.step][5]()[:3]
            except Exception as error:  # noqa: BLE001
                log(f"actions: {error}")
                self.actions = []
            for n in range(3):
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
        elif 301 <= control_id <= 303:
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
