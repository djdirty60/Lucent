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
if [ "$VARIANT" = old ]; then
  cp ci/old/Includes_Home.xml $K/addons/skin.lucent/xml/Includes_Home.xml
  cp ci/old/helper.py $K/addons/skin.lucent/scripts/helper.py
fi
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
cp -r ci/fakeseren $K/addons/plugin.video.fakeseren
cp -r ci/driver $K/addons/service.lucent.cidriver
# 1st start (Estuary): Kodi registers the add-ons, then stops
mkdir -p $K/userdata
timeout 60 xvfb-run -a -s "-screen 0 1920x1080x24" kodi --standalone >/tmp/ci/first.txt 2>&1
python3 ci/profile.py enable
python3 ci/profile.py skin
# 2nd start with Lucent: the driver does the test and quits
timeout 420 xvfb-run -a -s "-screen 0 1920x1080x24" kodi --standalone >/tmp/ci/second.txt 2>&1
mkdir -p ci-results
cp /tmp/ci/out/* ci-results/ 2>/dev/null
grep -iE "lucent|cidriver|fakeseren|error|CDirectoryProvider|exception|traceback" $K/temp/kodi.log | tail -800 > ci-results/$VARIANT-$RUN.log
ls -la ci-results
