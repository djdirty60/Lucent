# -*- coding: utf-8 -*-
"""Lucent: the alphabet bar under a poster row - jump to the first title with a letter.

RunScript(special://skin/scripts/letters.py,<list id>,<letter or #>)

The list is sorted by (sort) title, so the first title with a letter is found by halving: about 10 looks for 1000 titles.
Kodi's own ListItem.SortLetter is used, so 'The Batman' counts as B when Kodi ignores 'The' while sorting.
"""
import sys
import unicodedata

import xbmc


def key(letter):
    """0 for digits and signs ('#'), 1..26 for A..Z (accents count as their base letter)."""
    if not letter:
        return 0
    base = unicodedata.normalize("NFKD", letter[0].upper())[0]
    return ord(base) - 64 if "A" <= base <= "Z" else 0


def letter_at(cid, index):
    return xbmc.getInfoLabel(f"Container({cid}).ListItemAbsolute({index}).SortLetter")


def first_index(cid, total, target):
    """The first position whose letter is target or later (binary search on a sorted list)."""
    lo, hi = 0, total
    while lo < hi:
        mid = (lo + hi) // 2
        if key(letter_at(cid, mid)) < target:
            lo = mid + 1
        else:
            hi = mid
    return min(lo, total - 1)


def jump(cid, letter):
    total = int(xbmc.getInfoLabel(f"Container({cid}).NumItems") or 0)
    if total <= 0:
        return
    if xbmc.getCondVisibility(f"Container({cid}).SortDirection(descending)"):
        return                                            # the bar only shows for A-Z; nothing sensible to do
    index = first_index(cid, total, 0 if letter == "#" else key(letter))
    if letter_at(cid, 0) in ("", ".") and index == 0 and total > 1:
        index = 1                                         # skip the '..' item (parent folder) at the top
    xbmc.executebuiltin(f"SetFocus({cid},{index},absolute)")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        jump(int(sys.argv[1]), sys.argv[2])
