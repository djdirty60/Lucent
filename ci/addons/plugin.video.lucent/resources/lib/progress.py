# -*- coding: utf-8 -*-
"""A small card at the top right with a ring and 'x of y', for work that runs by itself (the library getting your
watched marks). It has nothing to focus, so the remote keeps working on the screen behind it."""
import xbmc

import dialogs
import util

T = util.T


# action id -> Kodi action name: a key pressed while the card shows closes it and goes on to the screen behind
PASS_ON = {1: "Left", 2: "Right", 3: "Up", 4: "Down", 5: "PageUp", 6: "PageDown", 7: "Select", 9: "ParentDir",
           10: "PreviousMenu", 11: "Info", 92: "Back", 117: "ContextMenu", 122: "PageUp", 123: "PageDown"}


class Card(dialogs.Base):
    closed = False

    def onAction(self, action):
        name = PASS_ON.get(action.getId())
        if not name or self.closed:
            return
        self.closed = True
        self.close()
        xbmc.executebuiltin("Action(%s)" % name)


class Progress:
    def __init__(self, title, unit=None):
        self.title, self.unit = title, unit or T("titels", "titles")
        self.card = None

    def show(self, done, total):
        if self.card is not None and self.card.closed:       # you pressed a key: shown again when you are idle
            self.hide()
        if self.card is None:
            self.card = Card("lucent_progress.xml", dialogs.PATH, "Default", "1080i")
            self.update(done, total)
            self.card.show()
        else:
            self.update(done, total)

    def update(self, done, total):
        percent = int(100 * done / total) if total else 100
        self.card.fill({"ptitle": self.title, "percent": "%d%%" % percent, "ring": "%03d" % (percent // 5 * 5),
                        "pline": T("%d van %d %s", "%d of %d %s") % (done, total, self.unit)})

    def hide(self):
        if self.card is not None:
            if not self.card.closed:
                self.card.closed = True
                self.card.close()
            del self.card
            self.card = None
