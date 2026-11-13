"""Writes the Kodi profile for a CI run: skin settings (tabs and rows), GUI settings, and enables our add-ons."""
import glob
import os
import sqlite3
import sys

home = os.path.expanduser("~/.kodi")
stage = sys.argv[1]
W = "plugin://plugin.video.fakeseren/?list="
tabs = {
    1: ("Home", "", [("Namen A", W + "names"), ("Traag B", W + "slow"), ("Snel X", W + "fast4"), ("Veel", W + "many"), ("Lucent bib", "plugin://script.lucent.library/?action=lib&kind=movies&list=recent"), ("TMDb films", "plugin://script.lucent.library/?action=tmdb&list=prov_8_newmovie")]),
    3: ("Streaming", "", [("Streamingdiensten", "plugin://script.lucent.library/?action=providers"),
                          ("Netflix nieuw", "plugin://script.lucent.library/?action=tmdb&list=prov_8_newmovie"), ("Diensten", W + "svc")]),
    2: ("Films", "", [("Snel C", W + "fast2"), ("Traag D", W + "slow2"), ("Wisselvallig E", W + "flaky"),
                      ("Heel traag F", W + "slower"), ("Snel G", W + "fast3"), ("Altijd leeg H", W + "empty")]),
    # issue #9 (13 Nov): the sort of a row from an add-on and of a genre row (two rows per tab: lower rows load later)
    4: ("Sort labels", "", [("Labels bron", W + "labels"), ("Labels A-Z", W + "labels")]),
    5: ("Sort genres", "", [("Genres bron", "videodb://movies/genres/"), ("Genres A-Z", "videodb://movies/genres/")]),
    6: ("Diensten", "", [("Streamingdiensten", W + "svc")]),
}
SORT = {(4, 2): "title", (5, 2): "title"}
if stage == "skin":
    s = {"lucent.setup.done": "1", "nuvio.migrated": "1", "nuvio.menu.version": "1", "lucent.addonw4": "1",
         "lucent.lite.checked": "1", "lucent.lite.built": "1", "lucent.subs.switched": "2", "nuvio.homepos": "0"}
    for t, (label, action, rows) in tabs.items():
        s[f"nuvio.tab{t}.label"] = label
        s[f"nuvio.tab{t}.icon"] = "icons/movies.png"
        s[f"nuvio.tab{t}.action"] = action
        for w, (lab, path) in enumerate(rows, 1):
            s[f"nuvio.tab{t}.w{w}.label"] = lab
            s[f"nuvio.tab{t}.w{w}.path"] = path
            if (t, w) in SORT:
                s[f"nuvio.tab{t}.w{w}.sort"] = SORT[(t, w)]
            s[f"nuvio.tab{t}.w{w}.style"] = "land" if (t, w) in ((2, 5), (3, 1), (1, 2), (3, 3), (6, 1)) else "poster"
            if t == 1:
                s[f"nuvio.home.w{w}.label"] = lab
                s[f"nuvio.home.w{w}.path"] = path
                s[f"nuvio.home.w{w}.style"] = "poster"
    bools = ["lucent.fy.off", "nuvio.update.off", "lucent.goals.off", "nuvio.autosubs"]
    d = os.path.join(home, "userdata/addon_data/skin.lucent")
    os.makedirs(d, exist_ok=True)
    esc = lambda v: v.replace("&", "&amp;").replace("<", "&lt;")  # noqa: E731
    lines = ['<settings version="1">'] + [f'    <setting id="{k}" type="string">{esc(v)}</setting>' for k, v in s.items()] + \
            [f'    <setting id="{k}" type="bool">true</setting>' for k in bools] + ["</settings>"]
    open(os.path.join(d, "settings.xml"), "w").write("\n".join(lines) + "\n")
    open(os.path.join(d, "tmdb_key.txt"), "w").write("CIKEY")
    g = """<settings version="2">
    <setting id="lookandfeel.skin">skin.lucent</setting>
    <setting id="debug.showloginfo">false</setting>
    <setting id="debug.extralogging">false</setting>
    <setting id="general.addonupdates">2</setting>
    <setting id="addons.unknownsources">true</setting>
    <setting id="screensaver.mode"></setting>
</settings>
"""
    open(os.path.join(home, "userdata/guisettings.xml"), "w").write(g)
    open(os.path.join(home, "userdata/advancedsettings.xml"), "w").write(
        "<advancedsettings><loglevel>1</loglevel></advancedsettings>\n")
elif stage == "enable":
    dbs = sorted(glob.glob(os.path.join(home, "userdata/Database/Addons*.db")))
    con = sqlite3.connect(dbs[-1])
    ids = ["skin.lucent", "script.lucent.library", "service.subtitles.lucent", "plugin.video.fakeseren", "plugin.video.youtube", "plugin.video.seren", "resource.images.studios.white", "resource.images.studios.coloured", "service.lucent.cidriver",
           "resource.language.nl_nl", "repository.seren-nixgate", "repository.tidb.repo", "plugin.video.tidb", "pvr.iptvsimple", "plugin.video.fakefen", "plugin.video.lucent"]
    for i in ids:
        con.execute("UPDATE installed SET enabled=1, disabledReason=0 WHERE addonID=?", (i,))
    con.commit()
    print({r[0]: r[1] for r in con.execute("SELECT addonID, enabled FROM installed WHERE addonID IN (%s)" % ",".join("?" * len(ids)), ids)})
    # a small video library: one film and one series with one episode, both stopped halfway
    vdbs = sorted(glob.glob(os.path.join(home, "userdata/Database/MyVideos*.db")))
    if vdbs:
        v = sqlite3.connect(vdbs[-1])
        try:
            v.execute("INSERT INTO path (idPath, strPath, strContent, strScraper) VALUES (901, '/tmp/ci/lib/movies/', 'movies', 'metadata.local')")
            v.execute("INSERT INTO path (idPath, strPath, strContent, strScraper) VALUES (902, '/tmp/ci/lib/shows/Show/', '', '')")
            v.execute("INSERT INTO files (idFile, idPath, strFilename, lastPlayed, dateAdded) VALUES (901, 901, 'film.mkv', '2026-10-30 20:00:00', '2026-10-30 10:00:00')")
            v.execute("INSERT INTO files (idFile, idPath, strFilename, lastPlayed, dateAdded) VALUES (902, 902, 's01e01.mkv', '2026-10-31 20:00:00', '2026-10-31 10:00:00')")
            v.execute("INSERT INTO movie (idMovie, idFile, c00, premiered) VALUES (901, 901, 'Lib Film', '2020-01-01')")
            try:                                     # Kodi 21: a film only shows with its (default) video version
                v.execute("INSERT INTO videoversion (idFile, idMedia, media_type, itemType, idType) VALUES (901, 901, 'movie', 0, 40400)")
            except Exception as error:  # noqa: BLE001 - Kodi 20 has no video versions
                print("videoversion:", error)
            v.execute("INSERT INTO tvshow (idShow, c00) VALUES (901, 'Lib Show')")
            v.execute("INSERT INTO tvshowlinkpath (idShow, idPath) VALUES (901, 902)")
            v.execute("INSERT INTO seasons (idSeason, idShow, season) VALUES (901, 901, 1)")
            v.execute("INSERT INTO episode (idEpisode, idFile, c00, c12, c13, idShow, idSeason) VALUES (901, 902, 'Pilot', '1', '1', 901, 901)")
            # 2.0.1 continue row: a next episode of the same series (left out: that series has an episode in progress) and
            # a second series with episode 1 watched and episode 2 not yet (that one is the 'next episode')
            v.execute("INSERT INTO files (idFile, idPath, strFilename, dateAdded) VALUES (903, 902, 's01e02.mkv', '2026-10-31 10:00:00')")
            v.execute("INSERT INTO episode (idEpisode, idFile, c00, c12, c13, idShow, idSeason) VALUES (902, 903, 'Second', '1', '2', 901, 901)")
            v.execute("INSERT INTO path (idPath, strPath, strContent, strScraper) VALUES (903, '/tmp/ci/lib/shows/Two/', '', '')")
            v.execute("INSERT INTO files (idFile, idPath, strFilename, playCount, lastPlayed, dateAdded) VALUES (904, 903, 's01e01.mkv', 1, '2026-11-01 21:00:00', '2026-10-31 10:00:00')")
            v.execute("INSERT INTO files (idFile, idPath, strFilename, dateAdded) VALUES (905, 903, 's01e02.mkv', '2026-10-31 10:00:00')")
            v.execute("INSERT INTO tvshow (idShow, c00) VALUES (902, 'Show Two')")
            v.execute("INSERT INTO tvshowlinkpath (idShow, idPath) VALUES (902, 903)")
            v.execute("INSERT INTO seasons (idSeason, idShow, season) VALUES (902, 902, 1)")
            v.execute("INSERT INTO episode (idEpisode, idFile, c00, c12, c13, idShow, idSeason) VALUES (903, 904, 'One', '1', '1', 902, 902)")
            v.execute("INSERT INTO episode (idEpisode, idFile, c00, c12, c13, idShow, idSeason) VALUES (904, 905, 'Two', '1', '2', 902, 902)")
            # 1.34.18 media flags (issue #9): stream details like Kodi stores them after a scan
            try:
                cols = [r[1] for r in v.execute("PRAGMA table_info(streamdetails)")]
                for fid, w, h, vc, hdr, ac, ch, al in ((901, 3840, 2160, "hevc", "dolbyvision", "truehd_atmos", 8, "eng"),
                                                       (902, 1920, 1080, "h264", "", "eac3", 6, "eng")):
                    v.execute("INSERT INTO streamdetails (idFile, iStreamType, strVideoCodec, iVideoWidth, iVideoHeight"
                              + (", strHdrType" if "strHdrType" in cols else "") + ") VALUES (?, 0, ?, ?, ?" + (", ?" if "strHdrType" in cols else "") + ")",
                              (fid, vc, w, h, hdr) if "strHdrType" in cols else (fid, vc, w, h))
                    v.execute("INSERT INTO streamdetails (idFile, iStreamType, strAudioCodec, iAudioChannels, strAudioLanguage) VALUES (?, 1, ?, ?, ?)",
                              (fid, ac, ch, al))
                    v.execute("INSERT INTO streamdetails (idFile, iStreamType, strSubtitleLanguage) VALUES (?, 2, 'dut')", (fid,))
                print("streamdetails ok", "hdr column" if "strHdrType" in cols else "no hdr column")
            except Exception as error:  # noqa: BLE001
                print("streamdetails failed", error)
            for f in (901, 902):
                v.execute("INSERT INTO bookmark (idFile, timeInSeconds, totalTimeInSeconds, thumbNailImage, player, playerState, type) VALUES (?, 600, 3000, '', 'VideoPlayer', '', 1)", (f,))
            v.commit()
            print("video library: 1 film, 1 series")
        except Exception as error:  # noqa: BLE001
            print("video library:", error)

