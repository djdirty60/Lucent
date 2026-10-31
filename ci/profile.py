"""Writes the Kodi profile for a CI run: skin settings (tabs and rows), GUI settings, and enables our add-ons."""
import glob
import os
import sqlite3
import sys

home = os.path.expanduser("~/.kodi")
stage = sys.argv[1]
W = "plugin://plugin.video.fakeseren/?list="
tabs = {
    1: ("Home", "", [("Snel A", W + "fast"), ("Traag B", W + "slow"), ("Snel X", W + "fast4"), ("Lege bibliotheek", "videodb://movies/titles/"), ("Lucent bib", "plugin://script.lucent.library/?action=lib&kind=movies&list=recent")]),
    3: ("Streaming", "", [("Streamingdiensten", "plugin://script.lucent.library/?action=providers"),
                          ("Netflix nieuw", "plugin://script.lucent.library/?action=tmdb&list=prov_8_newmovie")]),
    2: ("Films", "", [("Snel C", W + "fast2"), ("Traag D", W + "slow2"), ("Wisselvallig E", W + "flaky"),
                      ("Heel traag F", W + "slower"), ("Snel G", W + "fast3"), ("Altijd leeg H", W + "empty")]),
}
if stage == "skin":
    s = {"lucent.setup.done": "1", "nuvio.migrated": "1", "nuvio.menu.version": "1", "lucent.addonw4": "1",
         "lucent.lite.checked": "1", "lucent.subs.switched": "2", "nuvio.homepos": "0"}
    for t, (label, action, rows) in tabs.items():
        s[f"nuvio.tab{t}.label"] = label
        s[f"nuvio.tab{t}.icon"] = "icons/movies.png"
        s[f"nuvio.tab{t}.action"] = action
        for w, (lab, path) in enumerate(rows, 1):
            s[f"nuvio.tab{t}.w{w}.label"] = lab
            s[f"nuvio.tab{t}.w{w}.path"] = path
            s[f"nuvio.tab{t}.w{w}.style"] = "land" if (t, w) in ((2, 5), (3, 1), (1, 2)) else "poster"
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
    ids = ["skin.lucent", "script.lucent.library", "service.subtitles.lucent", "plugin.video.fakeseren", "service.lucent.cidriver",
           "resource.language.nl_nl"]
    for i in ids:
        con.execute("UPDATE installed SET enabled=1, disabledReason=0 WHERE addonID=?", (i,))
    con.commit()
    print({r[0]: r[1] for r in con.execute("SELECT addonID, enabled FROM installed WHERE addonID IN (%s)" % ",".join("?" * len(ids)), ids)})
