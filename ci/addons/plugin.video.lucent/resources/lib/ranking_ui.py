# -*- coding: utf-8 -*-
"""The screens for the order of sources: main screen (groups or one list), profiles, filters, scrapers."""
import json
import os

import xbmcgui
import xbmcvfs

import dialogs
import ranking
import scrapers
import util

T = util.T
UP_DOWN = (3, 4)


def rule_label(rule_id):
    return ranking.RULES[rule_id][0] if rule_id in ranking.RULES else rule_id


def preview_items(profile, count=6):
    rows = []
    for number, source in enumerate(ranking.apply(ranking.SAMPLES, profile)[:count], 1):
        item = xbmcgui.ListItem(source["name"].replace("Demo.", "").split("-GROUP")[0].replace(".", " ").replace("2160p", "4K"), offscreen=True)
        item.setProperty("nr", str(number))
        for slot, flag in enumerate(source["flags"][:5], 1):
            item.setProperty("flag%d" % slot, "lucent/flags/%s.png" % flag)
        rows.append(item)
    return rows


def describe(profile):
    """Up to four short names for the pills on a profile card."""
    if profile.get("tags") or profile.get("as_is"):
        return profile.get("tags") or []
    picks = []
    for group in profile["groups"]:
        if group["id"] not in ("size", "scraper") and group["order"]:
            picks.append(rule_label(group["order"][0]))
    return picks[:4]


def group_summary(group, profile):
    order = group["order"]
    if group["id"] == "scraper":
        return scrapers.names(profile)[0] + "…"
    if group["id"] == "speed":
        return T("Cached eerst", "Cached first") if order[0] == "cached" else T("Niet-cached eerst", "Uncached first")
    if group["id"] == "language":
        return {"nl": T("NL eerst", "Dutch first"), "nlsubs": T("NL-subs eerst", "Dutch subs first"), "multi": T("Meertalig eerst", "Multi first")}[order[0]]
    if group["id"] == "size":
        return T("Groot eerst", "Large first") if order[0] == "largest" else T("Klein eerst", "Small first")
    return ", ".join(rule_label(r) for r in order[:2]) + "…"


class Reorder:
    """OK picks up a row, up and down move it, OK puts it down. Used by the windows below."""
    picked = None

    def pick_or_drop(self, control, size):
        if self.picked is None:
            self.picked = control.getSelectedPosition()
        else:
            self.picked = None
        return size

    def follow(self, control, items):
        """Called after up or down: moves the picked row to where the cursor went."""
        target = control.getSelectedPosition()
        if self.picked is None or target == self.picked or target < 0 or target >= len(items):
            return False
        items.insert(target, items.pop(self.picked))
        self.picked = target
        return True


class Main(dialogs.Base, Reorder):
    """Step 1: the order of the groups. Step 2: the order within the group."""

    def onInit(self):
        self.profile_id = ranking.active_id()
        self.profile = ranking.active()
        self.group_at = 0
        self.groups, self.inner, self.preview = (self.getControl(i) for i in (100, 110, 300))
        self.active_list = None
        self.refresh()
        self.setFocusId(100)

    def persist(self):
        ranking.save(self.profile_id, self.profile)

    def changed(self):
        """Once you change something the profile no longer equals its preset."""
        self.profile.pop("as_is", None)
        self.profile.pop("tags", None)

    def refresh(self):
        self.setProperty("profile", T("Profiel: %s", "Profile: %s") % self.profile["name"])
        self.set_inner_title()
        self.fill_groups()
        self.fill_inner()
        self.preview.reset()
        self.preview.addItems(preview_items(self.profile))

    def set_inner_title(self):
        self.setProperty("inner_title", T("BINNEN %s", "WITHIN %s") % ranking.GROUP_NAMES[self.profile["groups"][self.group_at]["id"]].upper())

    def _row(self, number, label, mini="", picked=False):
        item = xbmcgui.ListItem(label, offscreen=True)
        item.setProperty("nr", str(number))
        item.setProperty("mini", mini)
        item.setProperty("picked", "1" if picked else "")
        return item

    def fill_groups(self):
        at = self.groups.getSelectedPosition()
        self.groups.reset()
        for number, group in enumerate(self.profile["groups"], 1):
            self.groups.addItem(self._row(number, ranking.GROUP_NAMES[group["id"]], group_summary(group, self.profile), self.active_list == 100 and self.picked == number - 1))
        self.groups.selectItem(max(0, at))

    def fill_inner(self):
        at = self.inner.getSelectedPosition()
        self.inner.reset()
        for number, rule in enumerate(self._inner_items(), 1):
            self.inner.addItem(self._row(number, rule_label(rule), picked=self.active_list == 110 and self.picked == number - 1))
        self.inner.selectItem(max(0, at))

    def _inner_items(self):
        group = self.profile["groups"][self.group_at]
        if group["id"] == "scraper":
            self.profile["scrapers"]["order"] = scrapers.names(self.profile)
            return self.profile["scrapers"]["order"]
        return group["order"]

    def onAction(self, action):
        code = action.getId()
        if code in dialogs.BACK:
            if self.picked is not None:
                self.picked, self.active_list = None, None
                return self.refresh()
            self.persist()
            return self.close()
        focus = self.getFocusId()
        if self.picked is not None:
            control = self.groups if self.active_list == 100 else self.inner
            if focus != self.active_list:
                self.setFocusId(self.active_list)
            if code in UP_DOWN:
                data = self.profile["groups"] if self.active_list == 100 else self._inner_items()
                if self.follow(control, data):
                    if self.active_list == 100:
                        self.group_at = self.picked
                    self.persist()
                    self.refresh()
                    control.selectItem(self.picked)
            return None
        if focus == 100 and code in UP_DOWN:
            position = self.groups.getSelectedPosition()
            if 0 <= position != self.group_at:
                self.group_at = position
                self.set_inner_title()
                self.inner.selectItem(0)
                self.fill_inner()
        return None

    def onClick(self, control):
        if control in (100, 110):
            box = self.groups if control == 100 else self.inner
            if self.picked is None:
                self.changed()
                self.picked, self.active_list = box.getSelectedPosition(), control
            else:
                self.picked, self.active_list = None, None
            self.persist()
            return self.refresh()
        if control == 91:
            self.persist()
            open_screen(Profiles, "lucent_profiles.xml")
            self.profile_id, self.profile = ranking.active_id(), ranking.active()
            self.group_at = 0
        elif control in (93, 94):
            self.persist()
            cls, xml = (Filters, "lucent_filters.xml") if control == 93 else (Scrapers, "lucent_scrapers.xml")
            open_screen(cls, xml, profile_id=self.profile_id)
            self.profile = ranking.active()
        elif control == 95:
            self.persist()
            return self.close()
        return self.refresh()


class Profiles(dialogs.Base):
    def onInit(self):
        self.panel = self.getControl(200)
        self.setProperty("profile", T("Profiel: %s", "Profile: %s") % ranking.active()["name"])
        self.build()
        self.setFocusId(200)

    def card(self, name, about, tags):
        item = xbmcgui.ListItem(name, about, offscreen=True)
        for number, tag in enumerate(tags[:4], 1):
            item.setProperty("tag%d" % number, tag)
        return item

    def build(self):
        at = self.panel.getSelectedPosition()
        self.panel.reset()
        self.ids = []
        current = ranking.active_id()
        first = 0
        for profile_id, profile in ranking.all_profiles().items():
            self.panel.addItem(self.card(profile["name"], profile.get("about", ""), describe(profile)))
            if profile_id == current:
                first = len(self.ids)
            self.ids.append(profile_id)
        self.panel.addItem(self.card(T("Mijn eigen", "My own"), T("Maak of kopieer een profiel.", "Make or copy a profile."),
                                     [T("+ Nieuw", "+ New"), T("Exporteren", "Export"), T("Inladen", "Load")]))
        self.ids.append("__own__")
        self.panel.selectItem(at if at > 0 else first)

    def onClick(self, _control):
        key = self.ids[self.panel.getSelectedPosition()]
        if key == "__own__":
            choice = xbmcgui.Dialog().contextmenu([T("Nieuw profiel", "New profile"), T("Exporteren als bestand", "Export as file"), T("Inladen uit bestand", "Load from file")])
            if choice == 0:
                return self.create()
            if choice == 1:
                return self.export(ranking.active_id())
            if choice == 2:
                return self.load_file()
            return None
        ranking.set_active(key)
        return self.close()

    def export(self, key):
        folder = xbmcgui.Dialog().browse(3, T("Kies een map", "Choose a folder"), "files")
        if folder:
            handle = xbmcvfs.File(os.path.join(folder, "lucent-profiel-%s.json" % key), "w")
            handle.write(json.dumps(ranking.all_profiles()[key], indent=1))
            handle.close()
            util.notify(T("Profiel bewaard", "Profile saved"))

    def onAction(self, action):
        code = action.getId()
        if code in dialogs.BACK:
            return self.close()
        if code in (117, 101):    # the menu button
            key = self.ids[self.panel.getSelectedPosition()]
            if key != "__own__":
                self.options(key)
        return None

    def create(self):
        name = xbmcgui.Dialog().input(T("Naam van je profiel", "Name of your profile"))
        if name:
            profile = ranking.active()
            profile.update(name=name, about=T("Mijn eigen volgorde.", "My own order."))
            new = ranking.new_id()
            ranking.save(new, profile)
            ranking.set_active(new)
            self.close()

    def options(self, key):
        builtin = key in ranking.presets()
        labels = [T("Kopiëren", "Copy"), T("Naam wijzigen", "Rename"), T("Bewaren als bestand", "Save as file"),
                  T("Terugzetten", "Reset") if builtin else T("Verwijderen", "Delete")]
        choice = xbmcgui.Dialog().contextmenu(labels)
        profile = ranking.all_profiles()[key]
        if choice == 0:
            new = ranking.new_id()
            ranking.save(new, dict(profile, name=profile["name"] + " 2"))
        elif choice == 1:
            name = xbmcgui.Dialog().input(T("Naam", "Name"), profile["name"])
            if name:
                ranking.save(key, dict(profile, name=name))
        elif choice == 2:
            self.export(key)
        elif choice == 3:
            ranking.delete(key)
        self.build()

    def load_file(self):
        path = xbmcgui.Dialog().browse(1, T("Kies een profiel", "Choose a profile"), "files", ".json")
        if not path:
            return
        handle = xbmcvfs.File(path)
        try:
            profile = json.loads(handle.read())
            for needed in ("name", "groups", "filters", "scrapers"):
                profile[needed]
        except (ValueError, KeyError, TypeError):
            util.notify(T("Dit is geen geldig profiel", "This is not a valid profile"))
            return
        finally:
            handle.close()
        new = ranking.new_id()
        ranking.save(new, profile)
        ranking.set_active(new)
        self.close()


class Options(dialogs.Base):
    """Lists next to a preview. Subclasses fill them."""
    boxes = (100, 110)

    def onInit(self):
        self.profile_id = self.args["profile_id"]
        self.profile = ranking.active()
        self.lists = {i: self.getControl(i) for i in self.boxes}
        self.preview = self.getControl(300)
        self.setProperty("profile", T("Profiel: %s", "Profile: %s") % self.profile["name"])
        self.refresh()
        self.setFocusId(self.boxes[0])

    def persist(self):
        ranking.save(self.profile_id, self.profile)

    def row(self, label, value="", check=None, number="", state=""):
        item = xbmcgui.ListItem(label, offscreen=True)
        item.setProperty("value", str(value))
        item.setProperty("nr", str(number))
        item.setProperty("st", state)
        item.setProperty("stname", ranking.STATE_NAMES.get(state, ""))
        if check is not None:
            item.setProperty("check", "1" if check else "0")
        return item

    def refresh(self):
        for box, rows in zip(self.boxes, self.all_rows()):
            control = self.lists[box]
            at = control.getSelectedPosition()
            control.reset()
            control.addItems(rows)
            control.selectItem(max(0, at))
        self.preview.reset()
        self.preview.addItems(preview_items(self.profile, 4))
        self.after_refresh()

    def after_refresh(self):
        pass

    def number(self, heading, current):
        typed = xbmcgui.Dialog().numeric(0, heading, str(current or ""))
        return int(typed) if typed.isdigit() else 0


def range_text(pair):
    low, high = pair or [0, 0]
    if not low and not high:
        return T("Geen grens", "No limit")
    return "%s – %s GB" % (low or 0, high or "∞")


HIDE_LABELS = {"cam": "CAM / TS / Screener", "hardcoded": "Hardcoded subs"}


class Filters(Options):
    boxes = (100, 110, 120)

    def all_rows(self):
        f = self.profile["filters"]
        hidden = f["hide"]
        left = [self.row(HIDE_LABELS.get(r, rule_label(r)), check=r in hidden) for r in ranking.HIDE_CHOICES]
        none = T("Geen", "None")
        limits = [self.row(T("Grootte film", "Movie size"), range_text(f["size_movie"])), self.row(T("Grootte aflevering", "Episode size"), range_text(f["size_episode"])),
                  self.row(T("Minimale kwaliteit", "Minimum quality"), rule_label(f["min_res"]) if f["min_res"] else none),
                  self.row(T("Maximaal per kwaliteit", "Maximum per quality"), T("%d bronnen", "%d sources") % f["max_per_res"] if f["max_per_res"] else none)]
        groups = [self.row(T("Voorkeur", "Preferred"), ", ".join(f["prefer_groups"]) or none), self.row(T("Verbergen", "Hide"), ", ".join(f["hide_groups"]) or none)]
        return left, limits, groups

    def onClick(self, control):
        f = self.profile["filters"]
        if control == 100:
            rule = ranking.HIDE_CHOICES[self.lists[100].getSelectedPosition()]
            f["hide"] = [r for r in f["hide"] if r != rule] if rule in f["hide"] else f["hide"] + [rule]
        elif control == 110:
            at = self.lists[110].getSelectedPosition()
            if at in (0, 1):
                key = "size_movie" if at == 0 else "size_episode"
                f[key] = [self.number(T("Minimaal (GB), 0 = geen", "Minimum (GB), 0 = none"), f[key][0]), self.number(T("Maximaal (GB), 0 = geen", "Maximum (GB), 0 = none"), f[key][1])]
            elif at == 2:
                ladder = ["", "720p", "1080p", "4k"]
                choice = xbmcgui.Dialog().select(T("Minimale kwaliteit", "Minimum quality"), [T("Geen", "None"), "720p", "1080p", "4K"])
                if choice >= 0:
                    f["min_res"] = ladder[choice]
            else:
                f["max_per_res"] = self.number(T("Maximaal aantal per kwaliteit, 0 = geen", "Maximum per quality, 0 = none"), f["max_per_res"])
        else:
            key = "prefer_groups" if self.lists[120].getSelectedPosition() == 0 else "hide_groups"
            text = xbmcgui.Dialog().input(T("Namen, gescheiden door komma's", "Names, separated by commas"), ", ".join(f[key]))
            f[key] = [g.strip() for g in text.split(",") if g.strip()]
        self.profile.pop("as_is", None)
        self.profile.pop("tags", None)
        self.persist()
        self.refresh()


class Scrapers(Options, Reorder):
    boxes = (100, 110)

    def names(self):
        self.profile["scrapers"]["order"] = scrapers.names(self.profile)
        return self.profile["scrapers"]["order"]

    def all_rows(self):
        left = []
        for number, name in enumerate(self.names(), 1):
            per = self.profile["scrapers"]["per"].get(name, {})
            bits = []
            if per.get("fallback"):
                bits.append(T("Alleen als er niets anders is", "Only if nothing else"))
            if per.get("max"):
                bits.append(T("Maximaal %d bronnen", "Maximum %d sources") % per["max"])
            bits.append(T("Eigen sortering overnemen: %s", "Keep own order: %s") % (T("aan", "on") if per.get("own") else T("uit", "off")))
            item = self.row(name, " · ".join(bits), number=number, state="off" if per.get("off") else "pref")
            item.setProperty("picked", "1" if self.picked == number - 1 else "")
            left.append(item)
        s = self.profile["scrapers"]
        general = [self.row(T("Zelfde bestand bij meerdere scrapers", "Same file from several scrapers"), T("Eén keer tonen", "Show once") if s.get("dedupe", True) else T("Allemaal tonen", "Show all")),
                   self.row(T("Wachttijd per scraper", "Time per scraper"), T("%d seconden", "%d seconds") % int(s.get("wait") or 30))]
        return left, general

    def after_refresh(self):
        height = 76 * max(1, self.lists[100].size())
        self.lists[100].setHeight(height)
        self.getControl(501).setPosition(96, 190 + height + 28)
        self.lists[110].setPosition(96, 190 + height + 78)

    def onAction(self, action):
        code = action.getId()
        if code in dialogs.BACK:
            self.picked = None
            self.persist()
            return self.close()
        if self.picked is not None and code in UP_DOWN and self.follow(self.lists[100], self.names()):
            self.persist()
            self.refresh()
            self.lists[100].selectItem(self.picked)
        return None

    def onClick(self, control):
        s = self.profile["scrapers"]
        if control == 100:
            box = self.lists[100]
            name = self.names()[box.getSelectedPosition()]
            if self.picked is not None:
                self.picked = None
                self.persist()
                return self.refresh()
            per = s["per"].setdefault(name, {})
            labels = [T("Verplaatsen", "Move"), (T("Aanzetten", "Switch on") if per.get("off") else T("Uitzetten", "Switch off")),
                      (T("Altijd gebruiken", "Always use") if per.get("fallback") else T("Alleen als er niets anders is", "Only if nothing else")),
                      T("Maximaal aantal bronnen", "Maximum sources"),
                      (T("Eigen sortering overnemen: uit", "Keep own order: off") if per.get("own") else T("Eigen sortering overnemen: aan", "Keep own order: on"))]
            choice = xbmcgui.Dialog().contextmenu(labels)
            if choice == 0:
                self.picked = box.getSelectedPosition()
                self.refresh()
                return box.selectItem(self.picked)
            if choice == 1:
                per["off"] = not per.get("off")
            elif choice == 2:
                per["fallback"] = not per.get("fallback")
            elif choice == 3:
                per["max"] = self.number(T("Maximaal, 0 = geen", "Maximum, 0 = none"), per.get("max"))
            elif choice == 4:
                per["own"] = not per.get("own")
        elif self.lists[110].getSelectedPosition() == 0:
            s["dedupe"] = not s.get("dedupe", True)
        else:
            s["wait"] = self.number(T("Seconden per scraper", "Seconds per scraper"), s.get("wait") or 30) or 30
        self.persist()
        return self.refresh()


def open_screen(cls, xml, **kwargs):
    window = cls(xml, dialogs.PATH, "Default", "1080i", **kwargs)
    window.doModal()
    del window


def open_main():
    open_screen(Main, "lucent_rank.xml")
