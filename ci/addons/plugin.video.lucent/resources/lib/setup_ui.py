# -*- coding: utf-8 -*-
"""The setup assistant and the 'Who is watching?' screen."""
import xbmc
import xbmcaddon
import xbmcgui

import dialogs
import floppy
import apikeys
import library
import mdblist
import ranking
import ranking_ui
import simkl
import streams
import tmdb
import tracker
import trakt
import usenet
import users
import util

T = util.T
FLAG_DONE = "setup_done.json"


def setting(name):
    return util.setting(name)


def put(name, value):
    xbmcaddon.Addon(util.ADDON_ID).setSetting(name, value)


def ask(heading, name, hidden=False):
    option = xbmcgui.ALPHANUM_HIDE_INPUT if hidden else 0
    typed = xbmcgui.Dialog().input(heading, setting(name) if not hidden else "", option=option)
    if typed:
        put(name, typed.strip())


CODE_IN = T("Testercode invoeren", "Enter tester code")
KEY_FILE = T("Sleutelbestand kiezen…", "Choose key file…")
CODE_OUT = T("Testercode maken", "Make tester code")
STEPS = [("welcome", T("Welkom", "Welcome")), ("account", "Account"), ("keys", T("Sleutels", "Keys")), ("scrapers", "Scrapers"),
         ("order", T("Volgorde", "Order")), ("dv", "Dolby Vision"), ("done", T("Klaar", "Done"))]
TEXT = {
    "welcome": (T("Welkom bij Lucent Video", "Welcome to Lucent Video"),
                T("In een paar stappen is alles klaar: je account, je sleutels en waar de films en series vandaan komen. Je kunt alles later veranderen bij de instellingen.",
                  "A few steps and you are ready: your account, your keys and where the films and shows come from. You can change everything later in the settings.")),
    "account": (T("Waarmee houd je bij wat je kijkt?", "What keeps track of what you watch?"),
                T("Je voortgang en lijsten worden daar bewaard. Je kunt het later altijd veranderen.", "Your progress and lists are kept there. You can always change this later.")),
    "keys": (T("Sleutels invullen", "Enter your keys"), T("Heb je een testercode gekregen? Kies dan Testercode invoeren. Anders maak je een gratis TMDB-sleutel aan op themoviedb.org.", "Did you get a tester code? Choose Enter tester code. Otherwise get a free TMDB key at themoviedb.org.")),
    "scrapers": (T("Waar komen de bronnen vandaan?", "Where do the sources come from?"), T("Vul er minstens één in. Lege regels worden overgeslagen.", "Fill in at least one. Empty rows are skipped.")),
    "order": (T("Welke bron komt bovenaan?", "Which source comes first?"), T("Kies een profiel, of laat het staan: dan verandert er niets aan de volgorde.", "Pick a profile or leave it: then the order does not change.")),
    "dv": (T("Wat kan je apparaat?", "What can your device do?"), T("Hiermee slaat de add-on bronnen over die je apparaat niet goed kan afspelen. Weet je het niet? Laat het op Speelt alles af staan.", "The add-on then skips sources your device cannot play properly. Not sure? Leave it on Plays everything.")),
    "done": (T("Je bent klaar", "You are done"), T("Veel kijkplezier. Dit scherm vind je terug bij de instellingen, onder Verbindingen.", "Enjoy. You can find this screen again in the settings, under Connections.")),
}


class Setup(dialogs.Base):
    def onInit(self):
        self.at = 0
        self.steps, self.options = self.getControl(100), self.getControl(110)
        self.show()

    def status(self, key):
        if key == "account":
            return tracker.logged_in() or users.tracker_choice() == 2
        if key == "keys":
            return bool(tmdb.key())
        if key == "scrapers":
            return bool(setting("manifest_url") or setting("torbox_key") or (setting("easynews_user") and setting("easynews_pass")))
        return True

    def rows(self):
        key = STEPS[self.at][0]
        filled = T("Ingevuld", "Filled in")
        empty = T("Nog niet ingevuld", "Not filled in yet")
        state = lambda name: filled if setting(name) else empty
        if key == "account":
            mode = users.tracker_choice()
            link = T("Koppelen met code", "Link with a code")
            linked = T("Gekoppeld", "Linked")
            return [("Trakt", linked if trakt.logged_in() else link, mode == 0), ("Simkl", linked if simkl.logged_in() else link, mode == 1),
                    (T("Alleen dit apparaat", "Only this device"), T("Geen account nodig", "No account needed"), mode == 2)]
        if key == "keys":
            out = [(CODE_IN, "", None), (KEY_FILE, "", None), (T("TMDB-sleutel", "TMDB key"), filled if tmdb.key() else empty, None)]
            mode = users.tracker_choice()
            if mode == 0 and not apikeys.trakt_id():
                out.append(("Trakt Client ID", empty, None))
            if mode == 1 and not apikeys.simkl_id():
                out.append(("Simkl Client ID", empty, None))
            if apikeys.exists():
                out.append((CODE_OUT, "", None))
            return out
        if key == "scrapers":
            return [(T("AIOStreams-adres", "AIOStreams address"), state("manifest_url"), None), (T("Easynews-gebruikersnaam", "Easynews username"), state("easynews_user"), None),
                    (T("Easynews-wachtwoord", "Easynews password"), state("easynews_pass"), None), (T("TorBox API-sleutel", "TorBox API key"), state("torbox_key"), None),
                    (T("Verbindingen testen", "Test connections"), "", None)]
        if key == "order":
            return [(T("Volgorde van bronnen openen", "Open the order of sources"), ranking.active()["name"], None)]
        if key == "dv":
            now = util.number("dv_support", 0)
            return [(label, "", now == number) for number, label in enumerate((T("Speelt alles af", "Plays everything"), T("Geen P7 / FEL", "No P7 / FEL"), T("Geen Dolby Vision", "No Dolby Vision")))]
        return []

    def show(self):
        key = STEPS[self.at][0]
        title, text = TEXT[key]
        self.fill({"stepline": T("Stap %d van %d", "Step %d of %d") % (self.at + 1, len(STEPS)), "stitle": title, "stext": text,
                   "next": T("Klaar", "Finish") if key == "done" else T("Volgende", "Next")})
        self.steps.reset()
        for number, (step, label) in enumerate(STEPS):
            item = xbmcgui.ListItem(label, offscreen=True)
            item.setProperty("mark", "ok" if number < self.at and self.status(step) else ("" if number == self.at else "todo"))
            item.setProperty("cur", "1" if number == self.at else "")
            self.steps.addItem(item)
        self.steps.selectItem(self.at)
        at = max(0, self.options.getSelectedPosition())
        self.options.reset()
        rows = self.rows()
        for label, value, chosen in rows:
            item = xbmcgui.ListItem(label, offscreen=True)
            item.setProperty("value", value)
            if chosen is not None:
                item.setProperty("check", "1" if chosen else "0")
            self.options.addItem(item)
        self.options.selectItem(min(at, max(0, len(rows) - 1)))
        self.setFocusId(110 if rows else 302)

    def go(self, position):
        self.at = max(0, min(position, len(STEPS) - 1))
        self.options.selectItem(0)
        self.show()

    def onClick(self, control):
        if control == 100:
            return self.go(self.steps.getSelectedPosition())
        if control == 301:
            return self.finish()
        if control == 302:
            if STEPS[self.at][0] == "done":
                return self.finish()
            return self.go(self.at + 1)
        self.activate(STEPS[self.at][0], self.options.getSelectedPosition())
        return self.show()

    def finish(self):
        util.save_json(FLAG_DONE, {"done": True})
        library.publish_status()
        self.close()

    def activate(self, key, at):
        if key == "account":
            users.set_tracker(at)
            module = {0: trakt, 1: simkl}.get(at)
            if module and not module.logged_in():
                module.login()
            library.publish_status()
        elif key == "keys":
            label = self.rows()[at][0]
            if label == CODE_IN:
                apikeys.enter_code()
            elif label == KEY_FILE:
                apikeys.choose_file()
            elif label == CODE_OUT:
                apikeys.show_code()
            else:
                ask(label, {"Trakt Client ID": "trakt_id", "Simkl Client ID": "simkl_id"}.get(label, "tmdb_key"))
        elif key == "scrapers":
            if at == 4:
                return self.test()
            name, hide, heading = (("manifest_url", True, "AIOStreams"), ("easynews_user", False, "Easynews"), ("easynews_pass", True, "Easynews"), ("torbox_key", True, "TorBox"))[at]
            ask(heading, name, hide)
        elif key == "order":
            ranking_ui.open_main()
        elif key == "dv":
            put("dv_support", str(at))
        return None

    def test(self):
        lines = []
        for name, on, check in (("AIOStreams", setting("manifest_url"), streams.check), ("Easynews", setting("easynews_user"), usenet.check_easynews), ("TorBox", setting("torbox_key"), usenet.check_torbox),
                                ("MDBList", mdblist.available(), mdblist.check), ("Floppy", floppy.available(), floppy.check)):
            if on:
                ok, text = check()
                lines.append("%s %s: %s" % ("✓" if ok else "✗", name, text))
        xbmcgui.Dialog().ok("Lucent", "\n".join(lines) or T("Vul eerst een scraper in.", "Fill in a scraper first."))


def needed():
    return not util.load_json(FLAG_DONE, {}).get("done") and not tmdb.key()


def open_setup():
    ranking_ui.open_screen(Setup, "lucent_setup.xml")


NEW = "__new__"


class Who(dialogs.Base):
    def onInit(self):
        self.row = self.getControl(100)
        self.build()
        self.setFocusId(100)

    def build(self):
        self.row.reset()
        self.ids = []
        people = users.everyone()
        chosen = 0
        for number, user in enumerate(people):
            item = xbmcgui.ListItem(user["name"], offscreen=True)
            item.setProperty("letter", user["name"][:1].upper())
            item.setProperty("color", user["color"])
            self.row.addItem(item)
            self.ids.append(user["id"])
            if user["id"] == users.current_id():
                chosen = number
        extra = xbmcgui.ListItem(T("Nieuw", "New"), offscreen=True)
        extra.setProperty("letter", "+")
        extra.setProperty("color", "glass_strong")
        self.row.addItem(extra)
        self.ids.append(NEW)
        width = 276 * len(self.ids)
        self.row.setPosition(max(96, (1920 - width) // 2), 430)
        self.row.setWidth(min(1728, width))
        self.row.selectItem(chosen)

    def onClick(self, _control):
        key = self.ids[self.row.getSelectedPosition()]
        if key == NEW:
            return self.create()
        users.choose(key)
        return self.close()

    def create(self):
        name = xbmcgui.Dialog().input(T("Naam van het profiel", "Name of the profile"))
        if not name:
            return
        choice = xbmcgui.Dialog().select(T("Waarmee houdt dit profiel bij wat het kijkt?", "What keeps track for this profile?"), ["Trakt", "Simkl", T("Alleen dit apparaat", "Only this device")])
        if choice < 0:
            return
        users.add(name, choice)
        module = {0: trakt, 1: simkl}.get(choice)
        if module:
            module.login()
        self.close()

    def onAction(self, action):
        code = action.getId()
        if code in dialogs.BACK:
            return self.close()
        if code in (117, 101):
            key = self.ids[self.row.getSelectedPosition()]
            if key != NEW:
                self.options(key)
        return None

    def options(self, key):
        labels = [T("Naam wijzigen", "Rename")] + ([T("Verwijderen", "Delete")] if key != users.MAIN else [])
        choice = xbmcgui.Dialog().contextmenu(labels)
        person = next(u for u in users.everyone() if u["id"] == key)
        if choice == 0:
            name = xbmcgui.Dialog().input(T("Naam", "Name"), person["name"])
            if name:
                users.rename(key, name)
        elif choice == 1 and xbmcgui.Dialog().yesno("Lucent", T("%s verwijderen, met voortgang en lijsten op dit apparaat?", "Delete %s, with progress and lists on this device?") % person["name"]):
            users.remove(key)
        self.build()


def ask_who():
    ranking_ui.open_screen(Who, "lucent_who.xml")
    library.publish_status()
    tracker.forget_lists()
    xbmc.executebuiltin("Container.Refresh")
