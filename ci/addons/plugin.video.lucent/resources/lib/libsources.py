# -*- coding: utf-8 -*-
"""Adds Lucent Video's library folders to Kodi by itself, so nobody has to add them by hand.

Kodi has no command for adding a video source. So, like other add-ons do:
  1. the folder is written into sources.xml (a copy of the old file is kept), so it shows under Videos > Files
     after the next start of Kodi;
  2. the folder gets its content type ("Films" / "Series", with Kodi's standard The Movie Database scrapers and their
     default settings) in Kodi's own video database,
     so it can be scanned right away, without a restart.
A shared MySQL database is never touched; then only sources.xml is written.
"""
import glob
import os
import shutil
import sqlite3
import time
import xml.etree.ElementTree as ET

import xbmc
import xbmcvfs

import util

SOURCES = xbmcvfs.translatePath("special://profile/sources.xml")
DATABASE = xbmcvfs.translatePath("special://database/")
ADVANCED = xbmcvfs.translatePath("special://profile/advancedsettings.xml")
SCRAPERS = {"movies": "metadata.themoviedb.org.python", "tvshows": "metadata.tvshows.themoviedb.org.python"}


def _empty_sources():
    root = ET.Element("sources")
    for kind in ("programs", "video", "music", "pictures", "files", "games"):
        part = ET.SubElement(root, kind)
        ET.SubElement(part, "default", {"pathversion": "1"})
    return root


def add_to_sources(name, path):
    """True when sources.xml was changed. Never removes or alters anything that was there."""
    try:
        root = ET.parse(SOURCES).getroot() if os.path.exists(SOURCES) else _empty_sources()
    except (ET.ParseError, OSError):
        util.log("sources.xml cannot be read, left alone")
        return False
    video = root.find("video")
    if video is None:
        video = ET.SubElement(root, "video")
        ET.SubElement(video, "default", {"pathversion": "1"})
    for source in video.findall("source"):
        for item in source.findall("path"):
            if (item.text or "").rstrip("/") == path.rstrip("/"):
                return False
    source = ET.SubElement(video, "source")
    ET.SubElement(source, "name").text = name
    ET.SubElement(source, "path", {"pathversion": "1"}).text = path
    ET.SubElement(source, "allowsharing").text = "true"
    if os.path.exists(SOURCES) and not os.path.exists(SOURCES + ".lucent-backup"):
        shutil.copyfile(SOURCES, SOURCES + ".lucent-backup")
    ET.indent(root) if hasattr(ET, "indent") else None
    tmp = SOURCES + ".tmp"
    ET.ElementTree(root).write(tmp, encoding="utf-8", xml_declaration=True)
    os.replace(tmp, SOURCES)
    return True


def _shared_database():
    try:
        with open(ADVANCED, encoding="utf-8", errors="replace") as handle:
            text = handle.read().lower()
    except OSError:
        return False
    return "<videodatabase>" in text and "mysql" in text


def _video_database():
    files = glob.glob(os.path.join(DATABASE, "MyVideos*.db"))
    number = lambda path: int("".join(ch for ch in os.path.basename(path) if ch.isdigit()) or 0)
    return max(files, key=number) if files else ""


def set_content(path, content):
    """Give the folder its content type in Kodi's video database. True when it is set (or already was)."""
    if _shared_database():
        return False
    database = _video_database()
    if not database:
        return False
    scraper = SCRAPERS[content]
    if not xbmc.getCondVisibility("System.HasAddon(%s)" % scraper):
        util.log("library folder type not set: %s is not installed" % scraper)
        return False
    movies = content == "movies"
    values = {"strPath": path, "strContent": content, "strScraper": scraper,
              "scanRecursive": 2147483647 if movies else 0, "useFolderNames": 0,
              "strSettings": "", "noUpdate": 0, "exclude": 0,
              "dateAdded": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        connection = sqlite3.connect(database, timeout=20)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(path)")}
            values = {key: value for key, value in values.items() if key in columns}
            found = connection.execute("SELECT idPath, strContent, strScraper FROM path WHERE strPath=?", (path,)).fetchone()
            if found and found[1] == content and found[2]:
                return True     # already set, by us or by the user: keep their choice
            if found:
                sets = ", ".join("%s=?" % key for key in values if key != "strPath")
                connection.execute("UPDATE path SET %s WHERE idPath=?" % sets,
                                   [value for key, value in values.items() if key != "strPath"] + [found[0]])
            else:
                keys = list(values)
                connection.execute("INSERT INTO path (%s) VALUES (%s)" % (", ".join(keys), ", ".join("?" * len(keys))),
                                   [values[key] for key in keys])
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error as error:
        util.log("library folder type not set: %s" % type(error).__name__)
        return False
    return True


def ensure(path, name, content):
    """Returns (scannable, sources_changed)."""
    changed = add_to_sources(name, path)
    return set_content(path, content), changed
