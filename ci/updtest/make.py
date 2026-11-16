"""2.1.33 (updater test): two small test add-ons 1.0.0 in the Kodi profile, a test repository add-on, and a repository
on the test server (/tmp/ci/repo) with version 1.0.1 of both, which has a new text (#30001).
plugin.citest gets the test repository as origin (Kodi updates it itself); plugin.citest2 has no origin (a zip)."""
import hashlib
import os
import shutil
import sys
import zipfile

K = os.path.expanduser("~/.kodi/addons")
REPO = "/tmp/ci/repo"


def addon(aid, version, new_text):
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<addon id="{aid}" name="CI {aid}" version="{version}" provider-name="ci">\n'
           '  <requires><import addon="xbmc.python" version="3.0.0"/></requires>\n'
           f'  <extension point="xbmc.python.script" library="default.py"/>\n'
           '  <extension point="xbmc.addon.metadata"><summary lang="en_GB">ci</summary><platform>all</platform></extension>\n</addon>\n')
    po = 'msgid ""\nmsgstr ""\n\nmsgctxt "#30000"\nmsgid "Old text"\nmsgstr ""\n'
    if new_text:
        po += '\nmsgctxt "#30001"\nmsgid "New text"\nmsgstr ""\n'
    return {"addon.xml": xml, "default.py": "", "resources/language/resource.language.en_gb/strings.po": po}


def write(folder, files):
    for name, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(folder, name)) or folder, exist_ok=True)
        with open(os.path.join(folder, name), "w") as fh:
            fh.write(text)


os.makedirs(REPO, exist_ok=True)
xmls = []
for aid in ("plugin.citest", "plugin.citest2", "plugin.citest3"):
    write(os.path.join(K, aid), addon(aid, "1.0.0", False))
    new = addon(aid, "1.0.1", True)
    os.makedirs(os.path.join(REPO, aid), exist_ok=True)
    with zipfile.ZipFile(os.path.join(REPO, aid, f"{aid}-1.0.1.zip"), "w") as z:
        for name, text in new.items():
            z.writestr(f"{aid}/{name}", text)
    xmls.append(new["addon.xml"].split("\n", 1)[1])
repo_xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<addon id="repository.citest" name="CI repository" version="1.0.0" provider-name="ci">\n'
            '  <extension point="xbmc.addon.repository" name="CI repository"><dir>'
            '<info compressed="false">http://127.0.0.1:8765/repo/addons.xml</info><checksum>http://127.0.0.1:8765/repo/addons.xml.md5</checksum>'
            '<datadir zip="true">http://127.0.0.1:8765/repo/</datadir></dir></extension>\n'
            '  <extension point="xbmc.addon.metadata"><summary lang="en_GB">ci</summary><platform>all</platform></extension>\n</addon>\n')
write(os.path.join(K, "repository.citest"), {"addon.xml": repo_xml})
# the repository offers 1.0.1 only once the test asks for it (/tmp/ci/repo/ready): Kodi must not update at its start
for name, entries in (("addons_new.xml", xmls), ("addons.xml", [x.replace('version="1.0.1"', 'version="1.0.0"') for x in xmls])):
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n' + "".join(entries) + repo_xml.split("\n", 1)[1] + "</addons>\n"
    with open(os.path.join(REPO, name), "w") as fh:
        fh.write(body)
    with open(os.path.join(REPO, name + ".md5"), "w") as fh:
        fh.write(hashlib.md5(body.encode()).hexdigest())
print("updtest ready")
