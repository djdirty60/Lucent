"""Six test channels for IPTV Simple and an XMLTV guide around the current time."""
import datetime
import os

K = os.path.expanduser("~/.kodi")
CH = [("npo1", "NPO 1"), ("npo2", "NPO 2"), ("espn1", "ESPN 1"), ("rtl4", "RTL 4"), ("sbs6", "SBS6"), ("ziggo", "Ziggo Sport")]
SHOWS = ["Het Weer & Het Nieuws", "Op1", "Boer zoekt Vrouw", "RTL Late Night", "Nieuws", "Make Up Your Mind", "Ajax - PSV",
         "Studio Sport", "Hart van Nederland", "Formule 1: voorbeschouwing", "Nieuwsuur", "De Avondshow"]
art = os.path.abspath("ci/fakeseren/art")
m3u = ["#EXTM3U"]
for n, (cid, name) in enumerate(CH, 1):
    m3u.append(f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-chno="{n}" tvg-logo="{art}/c{(n - 1) % 6}.png" group-title="Favorieten",{name}')
    m3u.append("/tmp/ci/test.mkv")
os.makedirs("/tmp/ci", exist_ok=True)
open("/tmp/ci/ch.m3u", "w").write("\n".join(m3u) + "\n")
now = datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0)
start0 = now.replace(minute=0) - datetime.timedelta(hours=1)
fmt = lambda t: t.strftime("%Y%m%d%H%M%S +0000")  # noqa: E731
x = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]
for cid, name in CH:
    x.append(f'<channel id="{cid}"><display-name>{name}</display-name></channel>')
for n, (cid, name) in enumerate(CH):
    t = start0 + datetime.timedelta(minutes=10 * n)
    k = n * 2
    while t < now + datetime.timedelta(hours=8):
        length = datetime.timedelta(minutes=(30, 55, 45, 60, 25)[k % 5])
        title = SHOWS[k % len(SHOWS)].replace("&", "&amp;")
        x.append(f'<programme start="{fmt(t)}" stop="{fmt(t + length)}" channel="{cid}"><title>{title}</title>'
                 f'<desc>Een verzonnen beschrijving voor de test.</desc><category>Nieuws</category></programme>')
        t += length
        k += 1
x.append("</tv>")
open("/tmp/ci/epg.xml", "w").write("\n".join(x) + "\n")
d = os.path.join(K, "userdata/addon_data/pvr.iptvsimple")
os.makedirs(d, exist_ok=True)
sett = {"kodi_addon_instance_name": "CI", "kodi_addon_instance_enabled": "true", "m3uPathType": "0", "m3uPath": "/tmp/ci/ch.m3u",
        "epgPathType": "0", "epgPath": "/tmp/ci/epg.xml", "m3uCache": "false", "epgCache": "false", "logoPathType": "0"}
xml = '<settings version="2">\n' + "".join(f'    <setting id="{k}">{v}</setting>\n' for k, v in sett.items()) + "</settings>\n"
open(os.path.join(d, "instance-settings-1.xml"), "w").write(xml)
open(os.path.join(d, "settings.xml"), "w").write(xml)
print("pvr ok")
