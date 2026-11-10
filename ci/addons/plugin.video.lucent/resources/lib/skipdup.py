"""Only one 'Skip intro' button (taken over from the Lucent skin; Lucent Video settings > Skip intro).

Since version 3.9.90 Seren has its own Skip intro / recap / credits / preview, with the same data from TheIntroDB that
the TheIntroDB add-on (plugin.video.tidb) uses. With both on, two skip windows open on top of each other and their
texts run through each other. When both are on for the same part, Lucent asks once which one to keep and switches the
other one off for that part (with the user's permission: this changes a setting of Seren or of TheIntroDB).
The choice is kept in Lucent Video's setting skip_by: 'tidb' or 'seren'.
"""
import xbmc
import xbmcaddon
import xbmcgui

import subconf

SEREN, TIDB = "plugin.video.seren", "plugin.video.tidb"
PARTS = ("intro", "recap", "credits", "preview")
CHOICE = "lucent.skipby"


def t(en, nl):
    return nl if xbmc.getLanguage(xbmc.ISO_639_1) == "nl" else en


def log(text):
    xbmc.log(f"[lucent.video] skipdup: {text}", xbmc.LOGINFO)


def _addon(addon_id):
    if not xbmc.getCondVisibility(f"System.HasAddon({addon_id}) + System.AddonIsEnabled({addon_id})"):
        return None
    try:
        return xbmcaddon.Addon(addon_id)
    except Exception:  # noqa: BLE001
        return None


def _on(addon, key):
    return (addon.getSetting(key) or "").lower() == "true"


def both_on():
    """The parts (intro, recap, ...) for which Seren and TheIntroDB both show a button."""
    seren, tidb = _addon(SEREN), _addon(TIDB)
    if not seren or not tidb or (tidb.getSetting("introdb_enabled") or "true").lower() == "false":
        return []
    return [p for p in PARTS if _on(seren, f"skip.{p}") and _on(tidb, f"enable_{p}")]


def _seren_off(parts):
    seren = xbmcaddon.Addon(SEREN)
    version = seren.getAddonInfo("version")
    home = xbmcgui.Window(10000)
    for p in parts:
        auto = "skip.auto" + p.capitalize()
        for key in (f"skip.{p}", auto):
            seren.setSetting(key, "false")
            home.clearProperty(f"{SEREN}.{version}.persisted.{key}")    # Seren's own settings cache: read it again
    log(f"Seren skip switched off for {parts}")


def _tidb_off(parts):
    tidb = xbmcaddon.Addon(TIDB)
    for p in parts:
        tidb.setSetting(f"enable_{p}", "false")
        tidb.setSetting(f"auto_skip_{p}", "false")
    log(f"TheIntroDB switched off for {parts}")


def ask():
    """Returns 'tidb', 'seren' or '' (closed without a choice)."""
    answer = xbmcgui.Dialog().yesnocustom(
        t("Skip intro is on twice", "Intro overslaan staat twee keer aan"),
        t("Seren has its own Skip intro button, and TheIntroDB shows one too. Together they open two windows on top of "
          "each other. Which one do you want to keep? Lucent switches the other one off.\n\n"
          "TheIntroDB also works outside Seren (for example for films in your library).",
          "Seren heeft een eigen knop Intro overslaan, en TheIntroDB toont er ook een. Samen openen ze twee vensters over "
          "elkaar heen. Welke wil je houden? Lucent zet de andere uit.\n\n"
          "TheIntroDB werkt ook buiten Seren (bijvoorbeeld voor films in je bibliotheek)."),
        t("Later", "Later"), nolabel="Seren", yeslabel="TheIntroDB")
    return {1: "tidb", 0: "seren"}.get(answer, "")          # -1 closed, 2 later: no choice


def apply(choice, parts):
    if not parts:
        return
    if choice == "tidb":
        _seren_off(parts)
    elif choice == "seren":
        _tidb_off(parts)


def check():
    """Called by the helper now and then: nothing to do, or apply the choice made before, or ask once."""
    if xbmc.getCondVisibility("Player.HasVideo"):
        return "later"                                   # never ask during a film
    parts = both_on()
    if not parts:
        return "ok"
    choice = subconf.text(CHOICE)
    if not choice:
        choice = ask()
        if not choice:
            return "asked, no answer"
        subconf.put(CHOICE, choice)
    apply(choice, parts)
    return f"{choice} for {parts}"


def label():
    choice = subconf.text(CHOICE)
    return {"tidb": "TheIntroDB", "seren": "Seren"}.get(choice, t("ask when needed", "vragen als het nodig is"))


def choose():
    """From the settings: pick again, and put the other one off right away."""
    choice = ask()
    if not choice:
        return
    subconf.put(CHOICE, choice)
    apply(choice, both_on())




def state_line():
    """For the skin: 'Button' or 'Skips by itself' (TheIntroDB), or that it is not installed."""
    tidb = _addon(TIDB)
    if not tidb:
        return t("Not installed", "Niet geïnstalleerd")
    if all((tidb.getSetting(f"auto_skip_{p}") or "").lower() == "true" for p in ("intro", "recap", "preview")):
        return t("Skips by itself", "Vanzelf overslaan")
    return t("Button", "Knop")
