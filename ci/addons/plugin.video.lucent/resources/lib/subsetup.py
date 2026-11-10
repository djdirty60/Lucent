# -*- coding: utf-8 -*-
"""The setup steps 'Subtitles' and 'Skip intro' (taken over from the Lucent skin), as short wizards:
action=subs_setup and action=skip_setup. Each shows what is done and offers the next steps."""
import json
import threading

import xbmc
import xbmcaddon
import xbmcgui

import subconf
import util

T = util.T
SUBS = subconf.SUBS_ADDON
SKIP = "plugin.video.tidb"            # TheIntroDB: skip intro, recap, credits and preview
SKIP_REPO = "repository.tidb.repo"    # its repository, in the Lucent repository
SKIP_KINDS = ("intro", "recap", "preview")


def has(addon_id):
    return xbmc.getCondVisibility("System.HasAddon(%s)" % addon_id)


def rpc(method, params):
    answer = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return answer.get("result") or {}


def install(addon_id):
    xbmc.executebuiltin("InstallAddon(%s)" % addon_id)


# ------------------------------------------------------------------ subtitles
def subs_default():
    return (rpc("Settings.GetSettingValue", {"setting": "subtitles.movie"}) or {}).get("value") == SUBS


def subs_keys():
    """(OpenSubtitles key + login filled in, SubDL key filled in) of Lucent Ondertitels."""
    try:
        addon = xbmcaddon.Addon(SUBS)
        return (bool(addon.getSetting("os_key").strip() and addon.getSetting("os_user").strip() and addon.getSetting("os_pass")),
                bool(addon.getSetting("subdl_key").strip()))
    except Exception:          # noqa: BLE001 - not installed
        return False, False


def subs_state():
    if not has(SUBS):
        return T("Lucent Ondertitels is niet geïnstalleerd", "Lucent Subtitles is not installed")
    os_ok, subdl_ok = subs_keys()
    parts = [T("Lucent Ondertitels is de standaard", "Lucent Subtitles is the default") if subs_default()
             else T("Lucent Ondertitels is nog niet de standaard", "Lucent Subtitles is not the default yet"),
             "OpenSubtitles ✓" if os_ok else T("OpenSubtitles: geen account", "OpenSubtitles: no account"),
             "SubDL ✓" if subdl_ok else T("SubDL: geen sleutel", "SubDL: no key")]
    parts.append(util.HOME.getProperty("lucent.video.subs.state") or "")
    return "  ·  ".join(p for p in parts if p)


def subs_actions():
    import subs_live
    if not has(SUBS):
        return [(T("Lucent Ondertitels installeren", "Install Lucent Subtitles"), lambda: install(SUBS))]
    out = [(T("Accounts en sleutels", "Accounts and keys"), lambda: xbmc.executebuiltin("Addon.OpenSettings(%s)" % SUBS))]
    if not subs_default():
        import subwatch
        out.append((T("Als standaard instellen", "Make it the default"), subwatch.set_default))
    out.append((T("Automatisch zoeken", "Search automatically"), subs_live.choose_mode))
    spoken = subconf.text("lucent.audio.label") or T("Kodi beslist", "Kodi decides")
    out.append((T("Gesproken taal: %s", "Spoken language: %s") % spoken, subs_live.choose_audio))
    out.append((T("AI-vertaling", "AI translation"), subs_live.enter_key))
    return out


INTRO_SUBS = T("Lucent Ondertitels vraagt OpenSubtitles, SubDL en Podnapisi tegelijk en zet de ondertitels die precies bij je video "
               "passen bovenaan. Maak twee gratis accounts en vul ze in bij 'Accounts en sleutels':[CR]"
               "1. opensubtitles.com: aanmelden, dan Profiel › API consumers › New consumer (de API-sleutel), plus je gebruikersnaam en wachtwoord.[CR]"
               "2. subdl.com: aanmelden, dan Account › API-sleutel.[CR]Optioneel: een AI-sleutel (Gemini is gratis, of OpenRouter of Claude) "
               "vertaalt Engelse ondertitels. Bij 'Gesproken taal' kies je met welk geluid een film start.",
               "Lucent Subtitles asks OpenSubtitles, SubDL and Podnapisi at the same time and puts the subtitles that fit your video "
               "exactly first. Make two free accounts and fill them in under 'Accounts and keys':[CR]"
               "1. opensubtitles.com: sign up, then Profile › API consumers › New consumer (the API key), plus your user name and password.[CR]"
               "2. subdl.com: sign up, then Account › API key.[CR]Optional: an AI key (Gemini is free, or OpenRouter or Claude) translates "
               "English subtitles. Under 'Spoken language' you choose which sound a film starts with.")


# ------------------------------------------------------------------ skip intro
def skip_auto():
    try:
        addon = xbmcaddon.Addon(SKIP)
        return all(addon.getSetting("auto_skip_%s" % kind) == "true" for kind in SKIP_KINDS)
    except Exception:          # noqa: BLE001 - not installed
        return False


def toggle_skip_auto():
    try:
        addon = xbmcaddon.Addon(SKIP)
        value = "false" if skip_auto() else "true"
        for kind in SKIP_KINDS:
            addon.setSetting("auto_skip_%s" % kind, value)
        # Lucent Video's own choice per series puts TheIntroDB's setting back for other series: keep that in step
        data = util.load_json("intro_skip.json", {})
        if "default" in data:
            data["default"] = {"auto_skip_%s" % k: value for k in SKIP_KINDS}
            util.save_json("intro_skip.json", data)
    except Exception as error:      # noqa: BLE001
        util.log("skip by itself: %s" % type(error).__name__)
    subconf.publish()


def install_skip():
    """TheIntroDB is not in Kodi's own repository: first its repository (in the Lucent repository), then the add-on."""
    def go():
        monitor = xbmc.Monitor()
        if not has(SKIP_REPO):
            install(SKIP_REPO)
            for _ in range(120):
                if has(SKIP_REPO) or monitor.waitForAbort(1):
                    break
            if not has(SKIP_REPO):
                xbmcgui.Dialog().ok("TheIntroDB", T("De repository van TheIntroDB kon niet worden geïnstalleerd. Werk de Lucent-repository bij "
                                                    "(Add-ons › Controleren op updates) en probeer het opnieuw.",
                                                    "The TheIntroDB repository could not be installed. Update the Lucent repository "
                                                    "(Add-ons › Check for updates) and try again."))
                return
            xbmc.executebuiltin("UpdateAddonRepos")
            monitor.waitForAbort(6)
        install(SKIP)
    threading.Thread(target=go, daemon=True).start()


def skip_key():
    """TheIntroDB needs no API key; a wrong one makes every lookup fail."""
    try:
        return xbmcaddon.Addon(SKIP).getSetting("introdb_api_key").strip()
    except Exception:          # noqa: BLE001
        return ""


def clear_skip_key():
    try:
        addon = xbmcaddon.Addon(SKIP)
        addon.setSetting("introdb_api_key", "")
        addon.setSetting("test_api_key_now", "false")
    except Exception as error:      # noqa: BLE001
        util.log("skip key: %s" % type(error).__name__)


def skip_state():
    if not has(SKIP):
        return T("TheIntroDB is nog niet geïnstalleerd", "TheIntroDB is not installed")
    if skip_key():
        return T("Er staat een API-sleutel ingevuld. TheIntroDB heeft die niet nodig, en een verkeerde sleutel houdt de knop tegen: haal hem weg",
                 "An API key is filled in. TheIntroDB does not need one, and a wrong key stops the button: remove it")
    import skipdup
    both = skipdup.both_on()
    line = T("Slaat intro, terugblik en preview zelf over", "Skips intro, recap and preview by itself") if skip_auto() \
        else T("Laat een knop 'Overslaan' zien", "Shows a 'Skip' button")
    if both:
        line += T("  ·  Seren en TheIntroDB staan allebei aan", "  ·  Seren and TheIntroDB are both on")
    return line


def skip_actions():
    if not has(SKIP):
        return [(T("TheIntroDB installeren", "Install TheIntroDB"), install_skip)]
    import skipdup
    out = [(T("API-sleutel weghalen", "Remove API key"), clear_skip_key)] if skip_key() else []
    out.append((T("Vanzelf overslaan: aan", "Skip by itself: on") if skip_auto() else T("Vanzelf overslaan: uit", "Skip by itself: off"),
                toggle_skip_auto))
    if has("plugin.video.seren"):
        out.append((T("Eén knop: %s", "One button: %s") % skipdup.label(), skipdup.choose))
    out.append((T("Instellingen van TheIntroDB", "TheIntroDB settings"), lambda: xbmc.executebuiltin("Addon.OpenSettings(%s)" % SKIP)))
    return out


INTRO_SKIP = T("TheIntroDB weet waar de intro, de terugblik ('eerder in...') en de preview van een aflevering beginnen en eindigen. "
               "Komt er een langs, dan verschijnt rechtsonder een knop 'Overslaan'. Zet 'Vanzelf overslaan' aan en hij springt zonder te vragen. "
               "Per serie kan het ook: kies 'Intro vanzelf overslaan' in het menu van een serie.[CR]"
               "TheIntroDB werkt voor afleveringen van de meeste bekende series, niet voor films. Een API-sleutel is niet nodig.",
               "TheIntroDB knows where the intro, the recap ('previously on...') and the preview of an episode start and end. "
               "When one comes along, a 'Skip' button appears at the bottom right. Switch on 'Skip by itself' and it jumps without asking. "
               "It can also be done per series: choose 'Skip intro by itself' in the menu of a series.[CR]"
               "TheIntroDB works for episodes of most well-known series, not for films. It needs no API key.")


# ------------------------------------------------------------------ the wizard
def wizard(kind):
    """kind: subs or skip. A list with the state on top; choosing an action does it and shows the list again."""
    heading = T("Ondertitels", "Subtitles") if kind == "subs" else T("Intro overslaan", "Skip intro")
    if not util.HOME.getProperty("lucent.video.%s.explained" % kind):
        util.HOME.setProperty("lucent.video.%s.explained" % kind, "1")
        xbmcgui.Dialog().textviewer(heading, INTRO_SUBS if kind == "subs" else INTRO_SKIP)
    while True:
        state, actions = (subs_state(), subs_actions()) if kind == "subs" else (skip_state(), skip_actions())
        rows = [label for label, _do in actions] + [T("Klaar", "Done")]
        picked = xbmcgui.Dialog().select("%s  ·  %s" % (heading, state), rows)
        if picked < 0 or picked >= len(actions):
            break
        actions[picked][1]()
        xbmc.sleep(300)
    subconf.publish()
