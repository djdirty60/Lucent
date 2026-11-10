# -*- coding: utf-8 -*-
"""Format check: what can this box really play?

Lucent plays tiny test clips (made by Lucent itself, in resources/formattest) and asks what you saw or heard: Kodi
cannot see whether your TV shows its Dolby Vision or HDR badge. Profile 7 FEL cannot be made freely, so for that row
you choose a FEL file of your own on this box (it stays on this box).

The results suggest settings: 'Dolby Vision on this device', and formats to hide. Hidden formats are left out
everywhere: autoplay, the next episode and the source list. Kept per device in formats.json."""
import json
import os
import threading
import time

import xbmc
import xbmcgui
import xbmcvfs

import dialogs
import util

T = util.T
FILE = "formats.json"
CLIPS = os.path.join(dialogs.PATH, "resources", "formattest")
START_WAIT = 20          # seconds a clip may take to start (TVs switching to HDR or another refresh rate can be slow)
SECOND_TRY = 8           # after this many seconds without a start: try Kodi's PlayMedia instead
# id, label, file (None = your own file), question kind, tags hidden when it does not work
TESTS = [
    ("dv5", "Dolby Vision profiel 5", "dv5.mp4", "dv", []),
    ("dv7", "Dolby Vision profiel 7 FEL", None, "dv", []),
    ("dv81", "Dolby Vision profiel 8.1", "dv81.mp4", "dv", []),
    ("dv84", "Dolby Vision profiel 8.4 (HLG)", "dv84.mp4", "dv", []),
    ("hdr10", "HDR10", "hdr10.mp4", "hdr", []),
    ("hdr10plus", "HDR10+", "hdr10plus.mp4", "hdr10plus", []),
    ("hlg", "HLG", "hlg.mp4", "hlg", ["hlg"]),
    ("hevc4k", "4K HEVC 10-bit", "hevc4k.mp4", "smooth", ["4k"]),
    ("av1", "AV1", "av1.mp4", "smooth", ["av1"]),
    ("vp9", "VP9", "vp9.webm", "smooth", []),
    ("truehd", "TrueHD 5.1", "truehd.mkv", "sound", ["truehd"]),
    ("dts", "DTS 5.1", "dts.mkv", "sound", ["dts", "dtshd", "dtsma", "dtsx"]),
    ("ddplus", "DD+ 5.1", "ddplus.mkv", "sound", ["ddplus"]),
]
QUESTIONS = {
    "dv": (T("Zag je het Dolby Vision-logo op je tv?", "Did your TV show its Dolby Vision badge?"),
           T("Kijk rechtsboven of in het menu van je tv.", "Look at the top right or in your TV's menu.")),
    "hdr": (T("Zag je het HDR-logo op je tv?", "Did your TV show its HDR badge?"), T("Kijk rechtsboven of in het menu van je tv.", "Look at the top right or in your TV's menu.")),
    "hdr10plus": (T("Zag je HDR10+ op je tv?", "Did your TV show HDR10+?"), T("Toont je tv alleen HDR of HDR10, kies dan Nee.", "If your TV only shows HDR or HDR10, choose No.")),
    "hlg": (T("Zag je HLG of HDR op je tv?", "Did your TV show HLG or HDR?"), T("Kijk rechtsboven of in het menu van je tv.", "Look at the top right or in your TV's menu.")),
    "smooth": (T("Speelde het filmpje vloeiend?", "Did the clip play smoothly?"), T("Haperen, zwart beeld of foutmeldingen: kies Nee.", "Stuttering, a black picture or errors: choose No.")),
    "sound": (T("Hoorde je een pieptoon?", "Did you hear a beep?"), T("Zet het geluid niet te hard.", "Do not turn the volume up too far.")),
}
WORD = {"ok": T("Goed", "Fine"), "no": T("Niet", "No"), "ask": T("Twijfel", "Unsure"), "fail": T("Speelt niet", "Does not play"), "": T("Nog niet getest", "Not tested yet")}


def data():
    path = os.path.join(util.PROFILE, FILE)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save(value):
    os.makedirs(util.PROFILE, exist_ok=True)
    with open(os.path.join(util.PROFILE, FILE + ".tmp"), "w", encoding="utf-8") as handle:
        json.dump(value, handle)
    os.replace(os.path.join(util.PROFILE, FILE + ".tmp"), os.path.join(util.PROFILE, FILE))


def hidden():
    """Tags of the formats hidden on this device."""
    return set(data().get("hidden") or [])


# ------------------------------------------------------------------ what the results mean
def advice(results):
    """(dv_support or None, tags to hide, lines to show)."""
    state = {key: (results.get(key) or {}).get("state", "") for key, *_rest in TESTS}
    good = lambda key: state[key] == "ok"            # noqa: E731
    bad = lambda key: state[key] in ("no", "fail")   # noqa: E731
    lines, hide, dv = [], [], None
    if good("dv7"):
        dv = 0
        lines.append(T("Dolby Vision: alles, ook FEL", "Dolby Vision: everything, FEL too"))
    elif good("dv81") or good("dv5"):
        if bad("dv7"):
            dv = 1
            lines.append(T("Dolby Vision: wel, maar geen P7 / FEL", "Dolby Vision: yes, but no P7 / FEL"))
        else:
            lines.append(T("Dolby Vision: wel. FEL is nog niet getest", "Dolby Vision: yes. FEL is not tested yet"))
    elif bad("dv81") or bad("dv5"):
        dv = 2
        lines.append(T("Dolby Vision: niet. Bronnen met Dolby Vision overslaan", "Dolby Vision: no. Skip sources with Dolby Vision"))
    if good("dv81") and bad("dv5"):
        lines.append(T("Profiel 5 speelt niet goed (zulke bronnen zijn zeldzaam)", "Profile 5 does not play well (such sources are rare)"))
    if bad("hdr10"):
        lines.append(T("HDR10: je tv toont geen HDR. Kijk bij de instellingen van je kastje", "HDR10: your TV shows no HDR. Check your box's settings"))
    if bad("hdr10plus"):
        lines.append(T("HDR10+: speelt als gewone HDR10, niets verbergen", "HDR10+: plays as plain HDR10, nothing hidden"))
    for key, label, _file, _kind, tags in TESTS:
        if bad(key) and tags:
            hide += tags
            lines.append(T("%s verbergen", "Hide %s") % label)
        elif bad(key) and key == "vp9":
            lines.append(T("VP9 speelt niet (zulke bronnen zijn zeldzaam)", "VP9 does not play (such sources are rare)"))
        elif state[key] == "ask":
            lines.append(T("%s: nog eens testen", "%s: test again") % label)
    if not lines:
        lines.append(T("Alles wat getest is, speelt goed. Er hoeft niets te veranderen.", "Everything tested plays fine. Nothing needs to change."))
    return dv, sorted(set(hide)), lines


def apply(results):
    dv, hide, _lines = advice(results)
    stored = data()
    stored["hidden"] = hide
    save(stored)
    if dv is not None:
        util.ADDON.setSetting("dv_support", str(dv))
    util.notify(T("Lucent past zich aan je kastje aan", "Lucent now suits your box"))


# ------------------------------------------------------------------ playing one clip
def _own_fel(ask=True):
    path = util.setting("formattest_fel")
    if path or not ask:
        return path
    picked = xbmcgui.Dialog().browse(1, T("Kies een eigen FEL-testbestand", "Choose a FEL test file of your own"), "video")
    if picked:
        util.ADDON.setSetting("formattest_fel", picked)
    return picked or ""


def _special(path):
    """special://home/... for a file in Kodi's home folder: some Android boxes play that more reliably than the long
    /storage/... or /data/... path."""
    home = xbmcvfs.translatePath("special://home/")
    if home and path.startswith(home):
        return "special://home/" + path[len(home):].replace(os.sep, "/")
    return path


def clip_path(test, ask=True):
    return _special(os.path.join(CLIPS, test[2])) if test[2] else _own_fel(ask)


class Watch(xbmc.Player):
    """Listens to the player, so a start is seen even when the clip already ended or is paused for the TV to switch."""

    def __init__(self):
        xbmc.Player.__init__(self)
        self.reset()

    def reset(self):
        self.started = False
        self.error = False
        self.ended = False

    def onAVStarted(self):
        self.started = True

    def onPlayBackError(self):
        self.error = True

    def onPlayBackEnded(self):
        self.ended = True

    def onPlayBackStopped(self):
        self.ended = True


def start_clip(player, path, label, monitor=None):
    """Starts a clip in the video window. Returns '' when it started, otherwise the reason (for the log)."""
    monitor = monitor or xbmc.Monitor()
    player.reset()
    player.play(path, xbmcgui.ListItem(label, path=path), windowed=True)
    tried_builtin = False
    for tick in range(START_WAIT * 10):
        if monitor.waitForAbort(0.1):
            return "Kodi is closing"
        if player.started or player.isPlayingVideo():
            return ""
        if player.error:
            break
        if not tried_builtin and tick >= SECOND_TRY * 10:
            tried_builtin = True
            util.log("formattest: %s not started after %ds, trying PlayMedia" % (label, SECOND_TRY))
            xbmc.executebuiltin('PlayMedia("%s",1)' % path)
    if player.error:
        return "playback error"
    return "no start after %ds (playing=%s, ended=%s)" % (START_WAIT, player.isPlaying(), player.ended)


def all_failed(results):
    """True when every clip that was tried did not even start: then it is the box or Kodi, not the formats."""
    tried = [entry.get("state") for key, entry in (results or {}).items() if entry.get("state")]
    return bool(tried) and all(state == "fail" for state in tried)


class Test(dialogs.Base):
    """A: the clip big on the left, the list on the right, the question below."""

    def onInit(self):
        self.results = dict(data().get("results") or {})
        self.queue = list(self.args["queue"])
        self.total = len(self.queue)
        self.fill({"ftitle": T("Formaattest", "Format check"), "b_yes": T("Ja", "Yes"), "b_no": T("Nee", "No"),
                   "b_unsure": T("Weet ik niet", "Not sure"), "b_again": T("Nog eens tonen", "Show it again"),
                   "waiting": T("Even wachten, het filmpje start...", "One moment, the clip is starting...")})
        self.done = []
        self.fails, self.starts = 0, 0
        self.current = None
        self.player = Watch()
        self.rows()
        self.next()

    def rows(self):
        row = self.getControl(100)
        at = max(0, row.getSelectedPosition())
        row.reset()
        for test in TESTS:
            state = (self.results.get(test[0]) or {}).get("state", "")
            running = self.current is not None and test[0] == self.current[0]
            waiting = test in self.queue
            item = xbmcgui.ListItem(test[1], offscreen=True)
            item.setProperty("state", "run" if running else state if not waiting else "wait")
            item.setLabel2(T("Speelt", "Playing") if running else T("Wacht", "Waiting") if waiting else WORD.get(state, ""))
            row.addItem(item)
        row.selectItem(at)

    def next(self):
        self.current = None
        self.stop_clip()
        if not self.queue:
            self.close()
            return
        self.current = self.queue.pop(0)
        path = clip_path(self.current)
        self.rows()
        if not path:
            self.results[self.current[0]] = {"state": "", "at": time.time()}
            return self.next()
        question, hint = QUESTIONS[self.current[3]]
        self.done.append(self.current[0])
        self.fill({"kicker": T("VRAAG %d VAN %d", "QUESTION %d OF %d") % (len(self.done), self.total), "question": question, "hint": hint,
                   "badge": self.current[1], "asking": ""})
        threading.Thread(target=self.play, args=(path,), daemon=True).start()
        return None

    def play(self, path):
        monitor = xbmc.Monitor()
        test = self.current
        reason = start_clip(self.player, path, test[1], monitor)
        if self.current is not test:
            return None
        if reason:
            util.log("formattest: %s did not start (%s)" % (test[0], reason))
            self.results[test[0]] = {"state": "fail", "at": time.time(), "kodi": ""}
            self.fails += 1
            if self.fails >= 3 and not self.starts:     # nothing starts at all: no use waiting for every clip
                util.log("formattest: the first %d clips did not start, stopping" % self.fails)
                self.queue = []
            self.fill({"asking": ""})
            return self.next()
        util.log("formattest: %s started" % test[0])
        self.starts += 1
        self.kodi_saw = xbmc.getInfoLabel("VideoPlayer.HdrType")
        monitor.waitForAbort(1.5)                  # give the TV time to switch
        self.fill({"asking": "1"})
        self.setFocusId(10)
        while self.current is test and not monitor.abortRequested():       # the clip keeps playing until you answer
            if not self.player.isPlaying() and self.current is test:
                self.player.play(path, xbmcgui.ListItem(test[1], path=path), windowed=True)
            if monitor.waitForAbort(0.3):
                break
        return None

    def stop_clip(self):
        if self.player.isPlaying():
            self.player.stop()
            for _ in range(30):
                if not self.player.isPlaying() or xbmc.Monitor().waitForAbort(0.1):
                    break

    def onClick(self, control):
        if not self.current or control not in (10, 11, 12, 13):
            return
        if control == 13:
            self.fill({"asking": ""})
            self.queue.insert(0, self.current)
            self.done.pop()
            return self.next()
        self.results[self.current[0]] = {"state": {10: "ok", 11: "no", 12: "ask"}[control], "at": time.time(), "kodi": getattr(self, "kodi_saw", "")}
        self.fill({"asking": ""})
        self.next()

    def onAction(self, action):
        if action.getId() in dialogs.BACK:
            self.queue = []
            self.stop_clip()
            self.close()

    def close(self):
        self.stop_clip()
        stored = data()
        stored["results"] = self.results
        stored["at"] = time.time()
        save(stored)
        dialogs.Base.close(self)


def run_tests(queue):
    import ranking_ui
    ranking_ui.open_screen(Test, "lucent_fmttest.xml", queue=queue)


# ------------------------------------------------------------------ the results (B: list with the advice beside it)
class Result(dialogs.Base):
    def onInit(self):
        self.show()

    def show(self):
        results = data().get("results") or {}
        self.results = results
        row = self.getControl(100)
        at = max(0, row.getSelectedPosition())
        row.reset()
        for key, label, _file, _kind, _tags in TESTS:
            entry = results.get(key) or {}
            state = entry.get("state", "")
            item = xbmcgui.ListItem(label, offscreen=True)
            text = WORD.get(state, "")
            if key == "dv7" and not util.setting("formattest_fel"):
                text = T("Kies eerst een eigen FEL-bestand", "Choose a FEL file of your own first")
            elif state == "no" and entry.get("kodi") == "dolbyvision":
                text = T("Kodi zag Dolby Vision, je tv niet", "Kodi saw Dolby Vision, your TV did not")
            item.setLabel2(text)
            item.setProperty("state", state)
            row.addItem(item)
        row.selectItem(at)
        self.setFocusId(100)
        _dv, _hide, lines = advice(results)
        failed = all_failed(results)
        if failed:
            lines = [T("De filmpjes starten niet op dit apparaat. Dat zegt niets over de formaten, dus Lucent verandert niets.",
                       "The clips do not start on this device. That says nothing about the formats, so Lucent changes nothing."),
                     T("Maak een foutrapport (Instellingen en hulp) en stuur het op, dan kijken we waarom.",
                       "Make an error report (Settings and help) and send it, then we can see why.")]
        self.fill({"noapply": "1" if failed else "","rtitle": T("Wat je kastje kan", "What your box can do"), "advhead": T("VOORSTEL", "SUGGESTION"),
                   "advtitle": T("Zo past Lucent zich aan", "This is how Lucent adapts"), "advice": "[CR]".join(lines[:8]),
                   "b_apply": T("Toepassen", "Apply"), "b_all": T("Alles opnieuw testen", "Test everything again"), "b_done": T("Klaar", "Done"),
                   "hint": T("Druk op een uitslag om alleen die opnieuw te testen.", "Press a result to test just that one again.")})

    def onClick(self, control):
        if control == 100:
            test = TESTS[self.getControl(100).getSelectedPosition()]
            if test[0] == "dv7" and xbmcgui.Dialog().yesno("Lucent", T("Een ander FEL-bestand kiezen?", "Choose another FEL file?")):
                util.ADDON.setSetting("formattest_fel", "")
            run_tests([test])
            self.show()
        elif control == 20:
            if all_failed(self.results):
                return
            apply(self.results)
            self.close()
        elif control == 21:
            run_tests(list(TESTS))
            self.show()
        elif control == 22:
            self.close()


def open_check():
    """Settings > Play > Format check. Without results yet the test starts right away."""
    import ranking_ui
    if not data().get("results"):
        if not xbmcgui.Dialog().yesno(T("Formaattest", "Format check"), T(
                "Lucent speelt nu een paar korte testfilmpjes en vraagt wat je zag of hoorde. Dat duurt ongeveer vijf minuten. Beginnen?",
                "Lucent now plays a few short test clips and asks what you saw or heard. It takes about five minutes. Start?")):
            return
        run_tests(list(TESTS))
    ranking_ui.open_screen(Result, "lucent_fmtresult.xml")
