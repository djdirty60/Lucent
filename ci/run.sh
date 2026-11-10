#!/bin/bash
# One CI run: VARIANT=old|new  RUN=1..3
set -x
VARIANT=$1; RUN=$2
ROOT=$(pwd)
K=~/.kodi
rm -rf $K /tmp/ci; mkdir -p $K/addons /tmp/ci/out
echo "$VARIANT-$RUN" > /tmp/ci/tag
# the skin = this repository, without the repo folders and CI files
mkdir -p $K/addons/skin.lucent
rsync -a --exclude .git --exclude repo --exclude ci --exclude .github --exclude screenshots --exclude "*.zip" ./ $K/addons/skin.lucent/
# CI has no Trakt: every title gets Trakt id 4242
sed -i 's/^def trakt_id_for(kind, tmdb_id):/def trakt_id_for(kind, tmdb_id):\n    return 4242/' $K/addons/skin.lucent/scripts/info.py
# dependencies the Home screen does not need (YouTube, studio images) are taken out of the test copy
python3 - <<'PY'
import os,re
p=os.path.expanduser("~/.kodi/addons/skin.lucent/addon.xml")
s=open(p).read()
s=re.sub(r'\s*<import addon="(plugin.video.youtube|resource.images.studios.white|resource.images.studios.coloured)"[^>]*/>','',s)
s=s.replace('<import addon="xbmc.gui" version="5.17.0"/>','<import addon="xbmc.gui" version="5.15.0"/>')
open(p,"w").write(s)
PY
cp -r ci/addons/script.lucent.library ci/addons/service.subtitles.lucent $K/addons/
cp -r ci/addons/repository.seren-nixgate $K/addons/
cp -r ci/addons/repository.tidb.repo ci/addons/plugin.video.tidb $K/addons/
if [ "$VARIANT" = old ]; then rm -rf $K/addons/script.lucent.library; cp -r ci/old/library $K/addons/script.lucent.library; fi
# one library film as Lucent Library writes it
mkdir -p "$K/userdata/addon_data/script.lucent.library/movies/Test Film (2020)"
echo 'plugin://plugin.video.seren/?action=getSources&action_args=%7B%22mediatype%22%3A+%22movie%22%2C+%22trakt_id%22%3A+4242%7D&forceresumecheck=true' > "$K/userdata/addon_data/script.lucent.library/movies/Test Film (2020)/Test Film (2020).strm"
cp -r ci/fakerealseren $K/addons/plugin.video.seren
mkdir -p /tmp/ci/serentheme && cp -r ci/serentheme/resources /tmp/ci/serentheme/ && mkdir -p $K/addons/plugin.video.seren/resources/language && cp -r ci/serentheme/resources/language/* $K/addons/plugin.video.seren/resources/language/
cp -r ci/packs/* $K/addons/
sed -i 's#^TMDB = .*#TMDB = "http://127.0.0.1:8765/3/"#; s#^IMG = .*#IMG = "http://127.0.0.1:8765/t/p/"#' $K/addons/script.lucent.library/tmdbwidgets.py
# since 1.39.0 the skin no longer uses Lucent Library: the new variant runs without it, like a fresh install
if [ "$VARIANT" = new ]; then rm -rf $K/addons/script.lucent.library; fi
sed -i 's#^TMDB = .*#TMDB = "http://127.0.0.1:8765/3/"#; s#^TMDB_IMG = .*#TMDB_IMG = "http://127.0.0.1:8765/t/p/"#' $K/addons/skin.lucent/scripts/info.py
sed -i 's#https://www.omdbapi.com/?#http://127.0.0.1:8765/omdb/?#' $K/addons/skin.lucent/scripts/omdb.py
sed -i 's#https://api.mdblist.com/#http://127.0.0.1:8765/mdblist/#' $K/addons/skin.lucent/scripts/omdb.py
python3 ci/faketmdb.py > /tmp/ci/faketmdb.txt 2>&1 &
# Solis Dashboard with a stand-in Homey (the example of the Solis handover)
cp -r ci/addons/script.solis.dashboard $K/addons/
cp -r ci/addons/plugin.video.fakefen $K/addons/
cp -r ci/addons/plugin.video.lucent $K/addons/
# a short clip as stand-in trailer (the real add-on ships its format-test clips, the CI copy does not)
mkdir -p $K/addons/plugin.video.lucent/resources/formattest
ffmpeg -v error -y -f lavfi -i testsrc=size=1280x720:rate=25 -f lavfi -i sine=f=440 -t 40 -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac $K/addons/plugin.video.lucent/resources/formattest/hevc4k.mp4
mkdir -p $K/userdata/addon_data/script.solis.dashboard
printf '<settings version="2">\n    <setting id="host">127.0.0.1</setting>\n    <setting id="port">8791</setting>\n    <setting id="notify_enabled">false</setting>\n</settings>\n' > $K/userdata/addon_data/script.solis.dashboard/settings.xml
python3 ci/fakesolis.py > /tmp/ci/fakesolis.txt 2>&1 &
cp -r ci/fakeseren $K/addons/plugin.video.fakeseren
cp -r ci/driver $K/addons/service.lucent.cidriver
mkdir -p /tmp/ci && cp ci/data/yt744_player_client.py /tmp/ci/
for n in 1 2 3; do mkdir -p "/tmp/ci/music/CI Artist $n/CI Album $n"; ffmpeg -loglevel error -y -f lavfi -i "sine=frequency=$((300*n)):duration=3" -metadata title="Song $n" -metadata artist="CI Artist $n" -metadata album="CI Album $n" -metadata date=202$n "/tmp/ci/music/CI Artist $n/CI Album $n/01.mp3"; ffmpeg -loglevel error -y -f lavfi -i "color=c=0x$((n*3))06090:s=300x300" -frames:v 1 "/tmp/ci/music/CI Artist $n/CI Album $n/folder.jpg"; done
ffmpeg -loglevel error -y -f lavfi -i "gradients=s=1920x1080:c0=0xfff4e6:c1=0xd8c4a8:x0=300:y0=200:x1=1700:y1=900" -frames:v 1 /tmp/ci/bright.jpg
printf '1\n00:00:01,000 --> 00:01:50,000\nHallo dit is Nederlands\n' > /tmp/ci/nl.srt
printf '1\n00:00:01,000 --> 00:01:50,000\nUkrainian forced\n' > /tmp/ci/uk.srt
ffmpeg -v error -f lavfi -i testsrc=size=1280x720:rate=25 -i /tmp/ci/uk.srt -i /tmp/ci/nl.srt -t 120 -map 0 -map 1 -map 2 -c:v libx264 -preset ultrafast -g 25 -pix_fmt yuv420p -c:s srt -metadata:s:s:0 language=ukr -metadata:s:s:0 title="Forced" -disposition:s:0 default+forced -metadata:s:s:1 language=dut -metadata:s:s:1 title="Volledig" /tmp/ci/test.mkv
ffmpeg -v error -f lavfi -i testsrc=size=1280x720:rate=25 -f lavfi -i sine=f=300 -f lavfi -i sine=f=500 -f lavfi -i "sine=f=700" -t 60 -map 0 -map 1 -map 2 -map 3 -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac -ac:a:2 6 -metadata:s:a:0 language=rus -disposition:a:0 default -metadata:s:a:1 language=eng -metadata:s:a:1 title="Director commentary" -disposition:a:1 0 -metadata:s:a:2 language=eng -metadata:s:a:2 title="English 5.1" -disposition:a:2 0 /tmp/ci/audio.mkv
printf '1\n00:00:01,000 --> 00:01:50,000\nEnglish subtitle\n' > /tmp/ci/en.srt
for a in eng rus; do ffmpeg -v error -f lavfi -i testsrc=size=1280x720:rate=25 -f lavfi -i sine=f=400 -i /tmp/ci/en.srt -t 60 -map 0 -map 1 -map 2 -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac -c:s srt -metadata:s:a:0 language=$a -metadata:s:s:0 language=eng -disposition:s:0 default /tmp/ci/same-$a.mkv; done
ffmpeg -v error -f lavfi -i testsrc=size=1280x720:rate=25 -f lavfi -i sine=f=400 -i /tmp/ci/en.srt -t 60 -map 0 -map 1 -map 2 -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac -c:s srt -metadata:s:a:0 language=eng -metadata:s:s:0 language=eng -disposition:s:0 0 /tmp/ci/nodef-eng.mkv
# live TV: IPTV Simple with six channels (the test video) and a guide around the current time
python3 ci/pvr.py
# 1st start (Estuary): Kodi registers the add-ons, then stops
mkdir -p $K/userdata
timeout 60 xvfb-run -a -s "-screen 0 1920x1080x24" kodi --standalone >/tmp/ci/first.txt 2>&1
python3 ci/profile.py enable
python3 ci/profile.py skin
# 2nd start with Lucent: the driver does the test and quits
timeout 1200 xvfb-run -a -s "-screen 0 1920x1080x24" kodi --standalone >/tmp/ci/second.txt 2>&1
mkdir -p ci-results
cp /tmp/ci/out/* ci-results/ 2>/dev/null
grep -iE "lucent|cidriver|fakeseren|error|CDirectoryProvider|exception|traceback" $K/temp/kodi.log | tail -800 > ci-results/$VARIANT-$RUN.log
cp /tmp/ci/first.txt ci-results/$VARIANT-$RUN-first.txt; cp /tmp/ci/second.txt ci-results/$VARIANT-$RUN-second.txt
tail -300 $K/temp/kodi.log > ci-results/$VARIANT-$RUN-tail.log 2>/dev/null
ls -la ci-results
