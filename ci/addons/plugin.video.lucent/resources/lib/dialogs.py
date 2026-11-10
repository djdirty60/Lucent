# -*- coding: utf-8 -*-
"""The add-on's own screens. Layouts are in resources/skins/Default/1080i and use the Lucent skin's colours and fonts."""
import os
import threading

import xbmc
import xbmcgui
import xbmcvfs

import util

T = util.T
PATH = xbmcvfs.translatePath(util.ADDON.getAddonInfo("path"))
BACK = (9, 10, 92)
LEFT_RIGHT = (1, 2)
ORDER = ["4K", "1440p", "1080p", "720p", "SD"]


def _open(cls, xml, **kwargs):
    return cls(xml, PATH, "Default", "1080i", **kwargs)


class Base(xbmcgui.WindowXMLDialog):
    props = {}

    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args)
        self.result = None
        self.args = kwargs

    def fill(self, props):
        for key, value in props.items():
            self.setProperty(key, str(value if value is not None else ""))

    def onAction(self, action):
        if action.getId() in BACK:
            self.close()


def pills(meta):
    out = []
    if meta["kind"] == "episode":
        out.append("S%d · E%d" % (int(meta["season"]), int(meta["episode"])))
    if meta.get("year"):
        out.append(str(meta["year"]))
    if meta.get("rating"):
        out.append("★ %.1f" % float(meta["rating"]))
    if meta.get("runtime"):
        out.append("%d min" % int(meta["runtime"]))
    return out


def head_props(meta):
    show = meta.get("show") if meta["kind"] == "episode" else ""
    props = {"title": show or meta["title"], "logo": meta.get("logo"), "fanart": meta.get("fanart"), "plot": meta.get("plot"),
             "subtitle": meta["title"] if show else (meta.get("tagline") or "")}
    for number, text in enumerate(pills(meta)[:4], 1):
        props["pill%d" % number] = text
    return props


class Sources(Base):
    """Choose a quality on top, then the source. self.result is the chosen source."""

    def onInit(self):
        self.meta, self.sources = self.args["meta"], self.args["sources"]
        self.show_all = self.args.get("show_uncached", False)
        self.fill(head_props(self.meta))
        self.has_uncached = any(not s["cached"] for s in self.sources) and any(s["cached"] for s in self.sources)
        self.setProperty("has_uncached", "1" if self.has_uncached else "")
        self.tabs, self.rows = self.getControl(100), self.getControl(200)
        self.tab = None
        self.build_tabs()
        self.setFocusId(200)

    def visible(self):
        return [s for s in self.sources if self.show_all or s["cached"] or not self.has_uncached]

    def build_tabs(self):
        self.setProperty("uncached_label", T("Alleen gecachet", "Cached only") if self.show_all else T("Niet gecachet", "Uncached"))
        shown = self.visible()
        names = sorted({s["resolution"] for s in shown}, key=lambda r: ORDER.index(r) if r in ORDER else 9)
        self.names = names
        self.tabs.reset()
        for name in names:
            count = sum(1 for s in shown if s["resolution"] == name)
            self.tabs.addItem(xbmcgui.ListItem("%s  %d" % (name, count), offscreen=True))
        self.show_tab(names[0] if names else None)

    def show_tab(self, name):
        if name == self.tab and self.rows.size():
            return
        self.tab = name
        self.rows.reset()
        self.current = [s for s in self.visible() if s["resolution"] == name]
        for source in self.current:
            item = xbmcgui.ListItem(source["name"], offscreen=True)
            item.setProperty("res", source["resolution"])
            item.setProperty("meta", source["meta"] + (T(" · Kan dit apparaat niet", " · Not for this device") if source.get("cannot") else ""))
            if source["cached"]:
                item.setProperty("cached", "1")
            if source is self.sources[0]:
                item.setProperty("rec", T("★ AANBEVOLEN", "★ RECOMMENDED"))
            for number, flag in enumerate(source["flags"][:8], 1):
                item.setProperty("flag%d" % number, "lucent/flags/%s.png" % flag)
            self.rows.addItem(item)

    def onAction(self, action):
        if action.getId() in BACK:
            return self.close()
        if action.getId() in LEFT_RIGHT and self.getFocusId() == 100:
            position = self.tabs.getSelectedPosition()
            if 0 <= position < len(self.names):
                self.show_tab(self.names[position])
        return None

    def onClick(self, control):
        if control == 200:
            self.result = self.current[self.rows.getSelectedPosition()]
            self.close()
        elif control == 100:
            self.show_tab(self.names[self.tabs.getSelectedPosition()])
            self.setFocusId(200)
        elif control == 301:
            self.show_all = not self.show_all
            self.tab = None
            self.build_tabs()
            self.setFocusId(200)
        elif control == 302:
            self.close()
        elif control == 303:
            self.explain()

    def explain(self):
        position = self.rows.getSelectedPosition()
        if not 0 <= position < len(self.current):
            return
        source = self.current[position]
        dialog = _open(Why, "lucent_why.xml", source=source)
        dialog.doModal()
        del dialog


class Why(Base):
    def onInit(self):
        source = self.args["source"]
        self.setProperty("name", source["name"])
        import ranking
        self.setProperty("profile", T("Profiel: %s", "Profile: %s") % ranking.active()["name"])
        rows = self.getControl(100)
        lines = source.get("why") or []
        self.setProperty("empty", "" if lines else T("Je profiel kijkt niet naar kenmerken van deze bron.", "Your profile does not look at properties of this source."))
        for what, rule in lines:
            item = xbmcgui.ListItem(what, rule, offscreen=True)
            rows.addItem(item)
        self.setFocusId(100)

    def onClick(self, _control):
        self.close()


def choose_source(meta, sources, show_uncached):
    dialog = _open(Sources, "lucent_sources.xml", meta=meta, sources=sources, show_uncached=show_uncached)
    dialog.doModal()
    result = dialog.result
    del dialog
    return result


class Busy(Base):
    """'Finding sources'. Back cancels."""
    cancelled = False

    def onInit(self):
        self.fill(self.args["props"])
        self.bar = self.getControl(50)
        self.ready = True

    def percent(self, value):
        try:
            self.bar.setPercent(value)
        except (RuntimeError, AttributeError):
            pass

    def onAction(self, action):
        if action.getId() in BACK:
            self.cancelled = True
            self.close()

    def done(self, sources):
        counts = {}
        for source in sources:
            counts[source["resolution"]] = counts.get(source["resolution"], 0) + 1
        names = sorted(counts, key=lambda r: ORDER.index(r) if r in ORDER else 9)
        props = {"count": len(sources), "best": names[0] if names else ""}
        for number, name in enumerate(names[:4], 1):
            props["res%d" % number] = "%s  %d" % (name, counts[name])
        props["ready"] = T("%d direct speelbaar", "%d ready to play") % sum(1 for s in sources if s["cached"])
        self.fill(props)
        self.percent(100)


def busy_dialog(meta):
    props = head_props(meta) if meta else {}
    if meta and meta["kind"] == "episode":
        props["subtitle"] = "S%d · E%d   %s" % (int(meta["season"]), int(meta["episode"]), meta["title"])
    dialog = _open(Busy, "lucent_busy.xml", props=props)
    dialog.show()
    return dialog


def recap(meta):
    """'Previous time': the story of the episode before this one (also across seasons); for a film or a first
    episode, what this one is about."""
    import tmdb
    if meta.get("kind") == "episode":
        season, episode = int(meta["season"]), int(meta["episode"])
        try:
            if episode > 1:
                rows = tmdb.season(meta["tmdb"], season).get("episodes") or []
                before = next((r for r in rows if r.get("episode_number") == episode - 1), None)
            elif season > 1:
                rows = tmdb.season(meta["tmdb"], season - 1).get("episodes") or []
                before = rows[-1] if rows else None
            else:
                before = None
        except Exception:          # no recap is never a reason not to resume
            before = None
        if before and before.get("overview"):
            return (T("Vorige keer: S%d · E%d  %s", "Previous time: S%d · E%d  %s")
                    % (before["season_number"], before["episode_number"], before.get("name") or ""), before["overview"])
    return T("Waar het over gaat", "What it is about"), meta.get("plot") or ""


class Resume(Base):
    def onInit(self):
        meta = self.args["meta"]
        head, text = recap(meta)
        self.fill({"title": meta.get("show") or meta["title"], "fanart": meta.get("thumb") or meta.get("fanart"),
                   "stopped": T("Gestopt bij %s", "Stopped at %s") % self.args["clock"], "recap_head": head, "recap": text})
        self.getControl(50).setPercent(self.args["percent"])

    def onClick(self, control):
        self.result = control
        self.close()


def ask_resume(meta, clock, percent):
    """True = resume, False = from the start, None = cancelled."""
    dialog = _open(Resume, "lucent_resume.xml", meta=meta, clock=clock, percent=percent)
    dialog.doModal()
    result = {10: True, 11: False}.get(dialog.result)
    del dialog
    return result


class Timed(Base):
    """Runs next to the video: the service keeps it up to date and closes it."""

    def start(self):
        self.closed = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        self.doModal()
        self.closed = True

    def finish(self):
        try:
            self.close()
        except RuntimeError:
            pass


class NextUp(Timed):
    def onInit(self):
        self.fill(self.args["props"])

    def countdown(self, seconds):
        self.setProperty("kicker", T("VOLGENDE AFLEVERING · %d s", "NEXT EPISODE · %d s") % max(0, int(seconds)))

    def onClick(self, control):
        self.result = {10: "now", 11: "stop", 12: "close"}.get(control)
        self.close()

    def onAction(self, action):
        if action.getId() in BACK:
            self.result = "close"
            self.close()


class Still(Timed):
    def onInit(self):
        self.fill(self.args["props"])

    def countdown(self, seconds):
        pass

    def onClick(self, control):
        self.result = {10: "continue", 11: "stop"}.get(control)
        self.close()


def next_dialog(following):
    info = "S%d · E%d" % (int(following["season"]), int(following["episode"]))
    if following.get("rating"):
        info += "   ★ %.1f" % float(following["rating"])
    if following.get("runtime"):
        info += " · %d min" % int(following["runtime"])
    dialog = _open(NextUp, "lucent_next.xml", props={"thumb": following.get("thumb"), "info": info, "title": following["title"],
                                                     "plot": following.get("plot")})
    dialog.start()
    return dialog


def still_dialog(show, count):
    dialog = _open(Still, "lucent_still.xml", props={"line": T("Je hebt %d afleveringen van %s achter elkaar gekeken.",
                                                                 "You watched %d episodes of %s in a row.") % (count, show)})
    dialog.start()
    return dialog


class TraktLink(Base):
    def onInit(self):
        self.fill(self.args["props"])

    def onClick(self, _control):
        self.close()


def link_dialog(service, url, code, qr_url=None):
    """The screen with the code and QR for linking an account. Returns (dialog, path of the QR picture)."""
    import segno
    os.makedirs(util.CACHE, exist_ok=True)
    picture = os.path.join(util.CACHE, "link_qr_%s_%s.png" % (service, code.replace(" ", "")))
    segno.make(qr_url or url, error="m").save(picture, kind="png", scale=12, border=2, dark="#0B1119", light="#FFFFFF")
    host = url.split("//")[-1]
    props = {"qr": picture, "code": code, "heading": T("%s koppelen", "Link %s") % service,
             "line": T("Scan de code of ga naar %s", "Scan the code or go to %s") % host}
    return _open(TraktLink, "lucent_trakt.xml", props=props), picture


def wait(seconds):
    xbmc.Monitor().waitForAbort(seconds)
