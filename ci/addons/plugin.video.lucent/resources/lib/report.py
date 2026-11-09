# -*- coding: utf-8 -*-
"""A log file testers can attach to a GitHub issue, with every address, key and password taken out."""
import os
import platform
import re
import time

import xbmc
import xbmcgui
import xbmcvfs

import util

T = util.T
RULES = [(re.compile(r"[a-z][a-z0-9+.-]*://[^\s\"'<>]+", re.I), lambda m: m.group(0) if m.group(0).startswith(("plugin://", "special://")) else "[link]"),
         (re.compile(r"(authorization|api[_-]?key|apikey|token|password|passwd|secret)\s*[=:]\s*(?:bearer\s+|basic\s+)?\S+", re.I), r"\1=[hidden]"),
         (re.compile(r"\b(bearer|basic)\s+[A-Za-z0-9+/_.=-]{6,}", re.I), r"\1 [hidden]"),
         (re.compile(r"\b[A-Za-z0-9+/_-]{40,}={0,2}"), "[hidden]"),
         (re.compile(r"\b[0-9a-fA-F]{32}\b"), "[hidden]"),
         (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[e-mail]"),
         (re.compile(r"(/(?:Users|home)/)[^/\s]+"), r"\1[user]")]
MAX_LINES = 1500


def clean(line):
    for pattern, replacement in RULES:
        line = pattern.sub(replacement, line)
    return line


def build():
    path = xbmcvfs.translatePath("special://logpath/kodi.log")
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[-MAX_LINES:]
    except OSError:
        lines = []
    head = ["Lucent Video %s" % util.ADDON.getAddonInfo("version"), "Kodi %s" % xbmc.getInfoLabel("System.BuildVersion"), "Skin %s" % xbmc.getSkinDir(),
            "System %s %s" % (platform.system(), platform.machine()), "Made %s" % time.strftime("%Y-%m-%d %H:%M"), ""]
    return "\n".join(head) + "".join(clean(line) for line in lines)


def save():
    folder = xbmcgui.Dialog().browse(3, T("Waar wil je het foutrapport bewaren?", "Where do you want to save the report?"), "files")
    if not folder:
        return
    target = os.path.join(folder, "lucent-video-rapport-%s.txt" % time.strftime("%Y%m%d-%H%M"))
    handle = xbmcvfs.File(target, "w")
    handle.write(build())
    handle.close()
    xbmcgui.Dialog().ok("Lucent", T("Het rapport is bewaard. Adressen, sleutels en wachtwoorden zijn eruit gehaald. Voeg het bestand toe aan je melding op GitHub.",
                                    "The report is saved. Addresses, keys and passwords were removed. Attach the file to your issue on GitHub."))
