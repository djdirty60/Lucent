# -*- coding: utf-8 -*-
"""Lucent: the alphabet bar under a poster row - jump to the first title with a letter.

RunScript(special://skin/scripts/letters.py,<list id>,<letter or #>)

The list is sorted by (sort) title, so the first title with a letter is found by halving: about 10 looks for 1000 titles.
'The Batman' counts as B when Kodi ignores 'The' while sorting.
"""
import json
import sys
import unicodedata

import xbmc


def key(letter):
    """0 for digits and signs ('#'), 1..26 for A..Z (accents count as their base letter)."""
    if not letter:
        return 0
    base = unicodedata.normalize("NFKD", letter[0].upper())[0]
    return ord(base) - 64 if "A" <= base <= "Z" else 0


ARTICLES = []


def articles():
    """'The ' and the like, when Kodi ignores them while sorting (Settings > Media > General)."""
    if not ARTICLES:
        query = {"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "filelists.ignorethewhensorting"}}
        try:
            on = json.loads(xbmc.executeJSONRPC(json.dumps(query))).get("result", {}).get("value", True)
        except ValueError:
            on = True
        ARTICLES.append(("the ", "the.", "the_") if on else ())
    return ARTICLES[0]


def letter_at(cid, index):
    """The first letter of the title at a position. Kodi only fills SortLetter for the item under the cursor, so for the
    others it is taken from the title itself (without 'The ' when Kodi ignores it)."""
    base = f"Container({cid}).ListItemAbsolute({index})."
    letter = xbmc.getInfoLabel(base + "SortLetter")
    if letter:
        return letter
    text = (xbmc.getInfoLabel(base + "Label") or xbmc.getInfoLabel(base + "Title")).strip()
    low = text.lower()
    for article in articles():
        if low.startswith(article):
            text = text[len(article):].lstrip()
            break
    return text[:1]


def is_parent(cid, index):
    return xbmc.getInfoLabel(f"Container({cid}).ListItemAbsolute({index}).Label") == ".."


def jump(cid, letter):
    total = int(xbmc.getInfoLabel(f"Container({cid}).NumItems") or 0)
    if total <= 0:
        return
    if xbmc.getCondVisibility(f"Container({cid}).SortDirection(descending)"):
        return                                            # the bar only shows for A-Z; nothing sensible to do
    start = 1 if total > 1 and is_parent(cid, 0) else 0   # skip the '..' item (parent folder) at the top
    target = 0 if letter == "#" else key(letter)
    index = start + first_index_from(cid, start, total, target)
    found = key(letter_at(cid, index))
    before = key(letter_at(cid, index - 1)) if index > start else -1
    how = "halving"
    if found != target or before >= target:               # not the letter, or not sorted the way it looks: walk the list once
        index, how = start + first_by_walking_from(cid, start, total, target), "walking"
    xbmc.log(f"[skin.lucent] letters: {letter} -> {index} of {total} ({how}, '{letter_at(cid, index)}')", xbmc.LOGINFO)
    xbmc.executebuiltin(f"SetFocus({cid},{index},absolute)")


def first_index_from(cid, start, total, target):
    lo, hi = start, total
    while lo < hi:
        mid = (lo + hi) // 2
        if key(letter_at(cid, mid)) < target:
            lo = mid + 1
        else:
            hi = mid
    return min(lo, total - 1) - start


def first_by_walking_from(cid, start, total, target):
    best = None
    for index in range(start, total):
        value = key(letter_at(cid, index))
        if value == target:
            return index - start
        if value > target and best is None:
            best = index
    return (best if best is not None else total - 1) - start


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        jump(int(sys.argv[1]), sys.argv[2])
