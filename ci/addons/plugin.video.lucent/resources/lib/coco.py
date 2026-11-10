# -*- coding: utf-8 -*-
"""CocoScrapers (script.module.cocoscrapers) as a scraper. It finds torrents; a debrid service plays them (see debrid.py).

Only used when CocoScrapers is installed and at least one debrid service has a key. CocoScrapers' own settings decide
which of its providers are on.
"""
from concurrent.futures import ThreadPoolExecutor, wait
import os
import sys
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon

import debrid
import usenet
import util

ADDON = "script.module.cocoscrapers"
WAIT = 25


def installed():
    return xbmc.getCondVisibility("System.HasAddon(%s)" % ADDON)


def _add_paths(addon_id, done):
    """Kodi only gives an add-on the modules it asks for itself, so add CocoScrapers and what it needs (requests ...)."""
    if addon_id in done or not xbmc.getCondVisibility("System.HasAddon(%s)" % addon_id):
        return
    done.add(addon_id)
    root = xbmcaddon.Addon(addon_id).getAddonInfo("path")
    try:
        manifest = ET.parse(os.path.join(root, "addon.xml")).getroot()
    except (ET.ParseError, OSError):
        return
    for extension in manifest.iter("extension"):
        if extension.get("point") == "xbmc.python.module":
            path = os.path.join(root, extension.get("library") or "lib")
            if path not in sys.path:
                sys.path.append(path)
    for need in manifest.iter("import"):
        if not need.get("addon", "").startswith("xbmc."):
            _add_paths(need.get("addon"), done)


def _providers():
    _add_paths(ADDON, set())
    from cocoscrapers import sources              # noqa: E402 - only there when installed
    return sources(specified_folders=["torrents"])


def _data(meta):
    titles = usenet.titles_for(meta)
    if meta["kind"] == "movie":
        return {"imdb": meta.get("imdb") or "", "title": titles[0], "aliases": titles[1:], "year": str(meta.get("year") or "")}
    return {"imdb": meta.get("imdb") or "", "tvshowtitle": titles[0], "title": meta.get("title") or "", "aliases": titles[1:],
            "year": str(meta.get("year") or ""), "season": str(meta["season"]), "episode": str(meta["episode"]),
            "premiered": meta.get("premiered") or "", "tvdb": meta.get("tvdb") or ""}


def _size_bytes(value):
    try:
        return float(value or 0) * 1024 ** 3                # CocoScrapers gives gigabytes
    except (TypeError, ValueError):
        return 0


def fetch(meta):
    """Returns None when CocoScrapers or a debrid service is missing, else a list of sources."""
    if not installed() or not debrid.active() or not meta.get("imdb"):
        return None
    try:
        providers = _providers()
    except Exception as error:                              # a broken CocoScrapers must never stop Lucent
        util.log("CocoScrapers could not start: %s" % type(error).__name__)
        return None
    data = _data(meta)
    episode = meta["kind"] != "movie"

    def run(entry):
        name, provider = entry
        try:
            scraper = provider()
            if episode and not getattr(scraper, "hasEpisodes", True) or not episode and not getattr(scraper, "hasMovies", True):
                return []
            return scraper.sources(data, []) or []
        except Exception as error:
            util.log("CocoScrapers %s: %s" % (name, type(error).__name__))
            return []

    pool = ThreadPoolExecutor(max_workers=max(1, min(10, len(providers))))
    jobs = [pool.submit(run, entry) for entry in providers]
    wait(jobs, timeout=WAIT)
    pool.shutdown(wait=False)
    found = [row for job in jobs if job.done() and not job.exception() for row in job.result() if row.get("hash")]
    by_hash = {}
    for row in found:
        by_hash.setdefault(row["hash"].lower(), row)
    owners = debrid.assign(list(by_hash))
    out = []
    for value, row in by_hash.items():
        service = owners.get(value)
        if not service:
            continue
        name = row.get("name") or ""
        source = usenet._source(name, _size_bytes(row.get("size")), "%s · %s" % (debrid.label(service), str(row.get("provider") or "").upper()),
                                resolve={"scraper": "CocoScrapers", "service": service, "hash": value, "name": name,
                                         "season": meta.get("season"), "episode": meta.get("episode")})
        out.append(source)
    util.log("CocoScrapers: %d torrents, %d playable" % (len(by_hash), len(out)))
    return out


def link(job):
    return debrid.link(job)
