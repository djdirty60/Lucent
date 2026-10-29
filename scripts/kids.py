# -*- coding: utf-8 -*-
"""Lucent: kids mode with a PIN.

    RunScript(special://skin/scripts/kids.py)          on: choose the menu items + PIN / off: asks the PIN
    RunScript(special://skin/scripts/kids.py,guard)    a settings window opened in kids mode: PIN, or back home

In kids mode the side menu only shows the items you chose (plus "Kids mode off"), the Options button on the info
page is gone, and the settings windows ask for the PIN. It is a lock on the menu, not a filter on what Seren shows.
Skin settings: lucent.kids (on/off), lucent.kids.pin, lucent.kids.tab1 … tab12 (which menu items stay).
"""
import sys

import xbmc
import xbmcgui

NL = xbmc.getLanguage(xbmc.ISO_639_1) == "nl"
HOME = xbmcgui.Window(10000)
NTABS = 12
OK_PROP = "lucent.kids.ok"                                 # PIN given: settings stay open until you are home again
KIDS_ICONS = ("home", "movies", "tv", "library", "favourites")


def t(en, nl):
    return nl if NL else en


def skin(key):
    return xbmc.getInfoLabel(f"Skin.String({key})")


def on():
    return xbmc.getCondVisibility("Skin.HasSetting(lucent.kids)")


def ask_pin(heading):
    return xbmcgui.Dialog().numeric(0, heading, "", True) or ""


def new_pin():
    """Ask a PIN twice; '' when cancelled or the two differ."""
    first = ask_pin(t("Choose a PIN (4 digits or more)", "Kies een pincode (4 cijfers of meer)"))
    if not first:
        return ""
    if len(first) < 4:
        xbmcgui.Dialog().ok(t("Kids mode", "Kinderstand"), t("Use at least 4 digits.", "Gebruik minstens 4 cijfers."))
        return ""
    if ask_pin(t("Type the PIN once more", "Typ de pincode nog een keer")) != first:
        xbmcgui.Dialog().ok(t("Kids mode", "Kinderstand"), t("The two PINs differ. Try again.",
                                                            "De twee pincodes zijn niet gelijk. Probeer het opnieuw."))
        return ""
    return first


def check_pin():
    pin = skin("lucent.kids.pin")
    if not pin:
        return True
    given = ask_pin(t("Kids mode: PIN", "Kinderstand: pincode"))
    if not given:
        return False
    if given != pin:
        xbmcgui.Dialog().notification(t("Kids mode", "Kinderstand"), t("Wrong PIN", "Verkeerde pincode"),
                                      "special://skin/media/icons/lock.png", 3000, False)
        return False
    return True


def tabs():
    """[(number, label, icon)] of the menu items that exist."""
    out = []
    for n in range(1, NTABS + 1):
        label = skin(f"nuvio.tab{n}.label")
        if label:
            out.append((n, label, skin(f"nuvio.tab{n}.icon")))
    return out


def choose_tabs():
    items = tabs()
    if not items:
        return None
    chosen = [n for n, _l, _i in items if xbmc.getCondVisibility(f"Skin.HasSetting(lucent.kids.tab{n})")]
    if not chosen:                                          # first time: the watching tabs, not settings / add-ons / power
        chosen = [n for n, _l, icon in items if any(f"icons/{k}." in icon for k in KIDS_ICONS)]
    rows = []
    for _n, label, icon in items:
        row = xbmcgui.ListItem(label)
        row.setArt({"icon": icon})
        rows.append(row)
    picked = xbmcgui.Dialog().multiselect(t("Which menu items may stay?", "Welke menu-onderdelen mogen blijven?"), rows,
                                          preselect=[i for i, (n, _l, _ic) in enumerate(items) if n in chosen],
                                          useDetails=False)
    if picked is None:
        return None
    if not picked:
        xbmcgui.Dialog().ok(t("Kids mode", "Kinderstand"), t("Choose at least one.", "Kies er minstens één."))
        return None
    return [items[i][0] for i in picked]


def switch_on():
    pin = skin("lucent.kids.pin")
    if not pin:
        pin = new_pin()
        if not pin:
            return
    keep = choose_tabs()
    if keep is None:
        return
    xbmc.executebuiltin(f'Skin.SetString(lucent.kids.pin,"{pin}")')
    for n in range(1, NTABS + 1):
        xbmc.executebuiltin(f"Skin.SetBool(lucent.kids.tab{n})" if n in keep else f"Skin.Reset(lucent.kids.tab{n})")
    xbmc.executebuiltin("Skin.SetBool(lucent.kids)")
    HOME.clearProperty(OK_PROP)
    xbmcgui.Dialog().notification(t("Kids mode", "Kinderstand"), t("On", "Aan"), "special://skin/media/icons/lock.png", 3000, False)
    xbmc.executebuiltin("ActivateWindow(home)")


def menu_on():
    """Kids mode is on: the PIN first, then switch it off or change things."""
    if not HOME.getProperty(OK_PROP) and not check_pin():
        return
    pick = xbmcgui.Dialog().select(t("Kids mode", "Kinderstand"),
                                   [t("Switch kids mode off", "Kinderstand uitzetten"),
                                    t("Change the menu items", "Menu-onderdelen aanpassen"),
                                    t("Change the PIN", "Pincode wijzigen")])
    if pick == 0:
        xbmc.executebuiltin("Skin.Reset(lucent.kids)")
        HOME.clearProperty(OK_PROP)
        xbmcgui.Dialog().notification(t("Kids mode", "Kinderstand"), t("Off", "Uit"), "special://skin/media/icons/lock.png", 3000, False)
    elif pick == 1:
        keep = choose_tabs()
        if keep:
            for n in range(1, NTABS + 1):
                xbmc.executebuiltin(f"Skin.SetBool(lucent.kids.tab{n})" if n in keep else f"Skin.Reset(lucent.kids.tab{n})")
    elif pick == 2:
        pin = new_pin()
        if pin:
            xbmc.executebuiltin(f'Skin.SetString(lucent.kids.pin,"{pin}")')
            xbmcgui.Dialog().notification(t("Kids mode", "Kinderstand"), t("PIN changed", "Pincode gewijzigd"),
                                          "special://skin/media/icons/lock.png", 3000, False)


def menu_off():
    if not xbmcgui.Dialog().yesno(t("Kids mode", "Kinderstand"),
                                  t("Kids mode shows only the menu items you choose, hides Options on the info page "
                                    "and asks a PIN for the settings. Switch it on?",
                                    "De kinderstand laat alleen de menu-onderdelen zien die jij kiest, verbergt Opties "
                                    "op de infopagina en vraagt een pincode voor de instellingen. Aanzetten?")):
        return
    switch_on()


def guard():
    """A settings window opened while kids mode is on."""
    if not on() or HOME.getProperty(OK_PROP):
        return
    if check_pin():
        HOME.setProperty(OK_PROP, "1")
    else:
        xbmc.executebuiltin("ActivateWindow(home)")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "guard":
        guard()
    elif on():
        menu_on()
    else:
        menu_off()
