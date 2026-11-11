<p align="center"><img src="resources/fanart.jpg" alt="Lucent" width="720"></p>

# Lucent – Kodi skin (Beta 4)

> **Beta 4:** the fourth public beta. Everything is in place, but expect small bugs – please report them on the [issues page](https://github.com/djdirty60/Lucent/issues/new/choose).

**Lucent** is a dark, cinematic Kodi skin in a glass style: large backdrops, glass panels, rounded cards, a white glow on the focused item and the Inter font.

Lucent works with **every video add-on**. Any folder of any add-on (Emby, Jellyfin, YouTube, an IPTV add-on, Fen Light and its clones, TMDb Helper …) or of your Kodi library can become a row on Home. A video add-on that works together with Lucent fills Home by itself and drives the buttons on the info page.

![Home screen](screenshots/home.jpg)

> The images are previews with placeholder artwork, rendered from the skin files. In Kodi you will see the real backdrops, posters and logos.

**Works with:** Kodi 21 (Omega) and Kodi 22 (Piers) · 1080p

---

## New since Beta 4

- **Trailers on posters** (*Settings → Watching → Trailer on focus*) – stay on a poster for 1, 2, 3, 5 or 8 seconds and its trailer plays in a soft-edged window, or the poster unfolds into a wide card with the trailer inside. The trailer is looked up while you wait, stops as soon as you move on, and tries the next trailer of the same title when YouTube gives no picture. Back makes it full screen.
- **Unfolding cards** – the focused poster opens into a wide card with its backdrop and info, and the posters next to it slide along.
- **Home picture** – the backdrop at the top right fades softly into the background at the bottom and on the left.
- **Info page** – *More* opens every option of your video add-on for a title in one menu (choose a source, trailer, cast, similar, rate …). *Library and lists* opens one window with ticks that shows where the title is.
- **Library and lists, Mark as watched, Calendar** work with the Trakt login of your video add-on, also for titles of other add-ons.
- **Subtitles and skip intro** are handled by the video add-on; without one, the subtitle button in the player opens Kodi's own subtitle screen.
- **Go to playlist** in the side menu of a list when something is queued (like Estuary).
- **Watched tick** in a colour of your choice; the watched percentage also works for add-ons that only pass on their progress (Fen Light, Red Light …).
- **Cleaned up** – the old Lucent Library add-on and everything built for it are gone; the menus, settings and the setup assistant only show what works with the add-ons you have.

<details>
<summary><b>New in Beta 4</b></summary>

- **Works without a special add-on** – a standard menu with your Kodi library, and any add-on or library folder can be added to Home as a row (long press OK → *Add to Home as widget*).
- **Scores everywhere** – with your own free key: IMDb, Rotten Tomatoes and Metacritic from **OMDb**, plus Letterboxd, the Rotten Tomatoes audience score and the Metacritic user score from **MDBList**. On the info page and, without opening it, in the lists (*Settings → Lucent → Scores*).
- **Media flags in the lists** – the same flags as the player (4K, Dolby Vision, HEVC, Atmos, 7.1 …) and the languages of sound and subtitles.
- **Readable text on light pictures**, **remember view per kind**, **percentage watched**, **episodes in landscape rows**, **clean picture when paused**, a *Covers* view for music, and sorting rows on *Last watched* or *Most watched*.

</details>

---

## Features

### Home screen
- A big hero area with the backdrop, logo (or title), info pills and plot of the focused item.
- Rows are **widgets** that you choose yourself (see *Customising the menu and widgets* below). Empty rows hide themselves.
- Out of the box Home starts with your Kodi library (*Continue watching*, *Recently added* …). When a video add-on that works with Lucent is installed, its rows (continue watching, trending, your watchlist and lists, streaming services …) are put on Home for you.
- **Trailers on posters** and **unfolding cards** (see above).

### Sidebar
A slim icon rail that opens when you press left. Out of the box it has Search, Home, Movies, TV shows, Add-ons, Favourites, Settings and Power, but **every tab can be changed**: its name, icon, what it opens when you click it, and its own widgets. Calendar, TV, Sport, Add-ons, Settings and Power show a screen of their own when you have not given them widgets.

![Sidebar](screenshots/sidebar.jpg)

### Five views for lists and add-on menus

| View | Best for |
| --- | --- |
| **Posters** | Hero info at the top and one row of posters |
| **Poster wall** | A full grid of posters |
| **Episodes** | Episode list with thumbnail, date and plot |
| **Landscape** | Hero info and one row of 16:9 cards |
| **List** | Menus and folders, with artwork and plot on the right |

The skin picks a fitting view automatically; change it with the **View** button at the top right. A view you pick for episodes (or films, series, seasons, albums) is remembered for every folder of that kind.

### Info page
Everything on one page. At the top: logo, buttons, director, scores, plot, genres, release date and details. Scroll down for tabs **Cast and crew | Similar titles | Trailers**, the **collection** the film belongs to and the **production companies** with their logos.

- **Play** goes through your video add-on.
- **More** – every option your video add-on has for the title, in one menu.
- **Library and lists** – one window with ticks: your watchlist, collection and your own Trakt lists.
- **Mark as watched** – on Trakt, through your video add-on.
- **Click a cast member, the director or a studio** for their page (photo, biography, films, logo); **click a title** on any of those pages to open its own info page. **Back walks the whole way back.**
- **Trailer** plays the trailer and brings you back to the page afterwards.
- **Options** (titles in the Kodi library): edit title, sort title, art, remove from library.

Cast, collections and studios need a free **TMDB API key**: Lucent uses the one of your video add-on, or enter your own in **Skin settings → Integrations → TMDB API key** (free at [themoviedb.org](https://www.themoviedb.org/settings/api)).

### Calendar
A **Calendar** tab (Week, List and Month) for the series and films of your Trakt collection. Switch the bell on for a title (in the calendar or on its info page) and a pop-up tells you when a new episode is out (*Watch now / Later*) or when a film is released digitally. Uses the Trakt login of your video add-on.

### Sport (needs IPTV channels)
A **Sport** tab with games from almost 200 competitions (football worldwide, NBA, NFL, NHL, MLB, rugby, Formula 1, IndyCar, NASCAR, golf, tennis, UFC and more), fetched from ESPN. It only appears when Kodi has TV channels.

- **My sport** – a big card for your team's next game in both club colours; when the game is on it becomes a live scoreboard with the minute bar and the scorers.
- **All games**, **Tables** (W/D/L, coloured zones, a panel for the club you are on), **Club pages** (logo, colours, stadium photo), **Follow** (teams, countries, competitions, drivers and players) and a **Game page** (your channels, statistics, timeline, table; Formula 1 has its own page).
- **Reminders, automatic switching and recording**, and **goal notifications** for the teams you follow.
- **In the TV player** – a scoreboard top centre and *Statistics*, *Also live*, *Table*, *Guide* and *Record* in the player menu.

### TV guide and live TV
A **TV** tab with your IPTV channels: the playing channel in the header, the groups as a row of buttons, channel logos and a timeline with a line at the current time. The live TV player has its own compact info bar and a menu with channel up/down, pause, record, subtitles, audio and recent channels.
- **Xtream login** – enter your provider's server, user name and password (setup assistant → Live TV, or Settings → Live TV); Lucent checks the login and sets up IPTV Simple Client.
- **Hide channels** – choose the groups you want, or type a few words (`NL, BE, SPORT`). *Show everything again* puts the original list back.
- **Star button** in the live menu to add the channel to Kodi's favourites, and **replay** that continues where you stopped.

### Player
- A clean bar and player menu, a **sleep timer** (stop after this episode or after 15–90 minutes) and a picture without bar when paused (after 3, 5 or 10 seconds).
- **Player info** (player menu → *Statistics*): *Overview* (badges, resolution, HDR, bitrate, buffer, your box), *Video* (resolution, HDR brightness, colour space, bitrate graph) and *Audio* (sound chain, output, a room with the speakers in use).
- **Volume** card at the bottom; with passthrough a note says to set the volume on your amplifier.

### Streaming services
The *Streaming services* row opens a pop-up per service: the title under the cursor as a big landscape picture with *Watch*, *Trailer* and *My list*, and New, Popular and Top lists for films and series. Which services you see is set in *Settings → Lucent → Streaming services*.

### Setup assistant
The first time Lucent opens, a short assistant walks through **Films and series** (your video add-on), the TMDb key, live TV, picture and sound, subtitles and skip intro, the library, the tabs, the look and a backup – each step shows how it stands and has buttons to set it up. Open it again via *Settings → Lucent → Setup assistant*.

### Settings
Lucent's settings are grouped in categories: **Lucent** (look, menu, streaming services, kids mode, setup assistant), **Watching** (playback, trailers, subtitles and skip intro), **Live TV**, **System**, **Add-ons**, **Files and profiles** and **Help and info** (what's new, updates, self-test, safe log). Kodi pages you rarely need are under *System → More Kodi settings*.

### Also
- **Kids mode** – a PIN and a choice of side-menu items; the settings ask for the PIN.
- **Backup and restore** – one zip with Lucent's settings and menu, Kodi's favourites and sources and the settings of your video add-ons and IPTV Simple; optionally every week into a folder you choose. The backup holds your logins – keep it to yourself.
- **Light mode** – for boxes with little memory (on by itself with 2 GB or less): only six rows on Home, no colour glow and no snow.
- **Self-test and safe log** – the self-test checks your video add-on, subtitles, IPTV Simple and the channels and says in plain words what is missing; the safe log blanks out logins, tokens and your provider's address.
- **Alphabet bar** under A–Z poster rows, **Solis Dashboard** tab (with that add-on), **update pop-up** (*Update now*, *Later*, *Skip this version*).
- **Everything else in the same style** – PVR windows, the video player, settings, add-on windows, file manager, keyboard, dialogs, power menu and more.

---

## Screenshots

**Posters**
![Posters](screenshots/posters.jpg)

**Poster wall**
![Poster wall](screenshots/poster-wall.jpg)

**Episodes**
![Episodes](screenshots/episodes.jpg)

**List view (add-on menu)**
![List](screenshots/list.jpg)

**Showcase**
![Showcase](screenshots/showcase.jpg)

**Info page**
![Info page](screenshots/info.jpg)
![Info page, scrolled down](screenshots/info-more.jpg)
![Person page](screenshots/person.jpg)

**Player**
![Player](screenshots/player.jpg)

**Player info** – Overview, Video and Audio
![Player info](screenshots/player-info.jpg)
![Player info – Video](screenshots/player-info-video.jpg)
![Player info – Audio](screenshots/player-info-audio.jpg)

**Streaming service pop-up**
![Streaming service](screenshots/streaming-service.jpg)

**Sport in the TV player**
![Sport in the TV player](screenshots/sport-player.jpg)

**TV player and TV guide** (test channels in a real Kodi)
![TV player](screenshots/tv-player.jpg)
![TV guide](screenshots/tv-guide.jpg)

**Settings**
![Settings](screenshots/settings.jpg)

**Skin settings**
![Skin settings](screenshots/skin-settings.jpg)

**Keyboard**
![Keyboard](screenshots/keyboard.jpg)

**Calendar**
![Calendar](screenshots/calendar.jpg)

**Tabs with their own screen** – Calendar, TV, Sport, Settings and Power on Home
![Calendar tab](screenshots/tab-calendar.jpg)
![TV tab](screenshots/tab-tv.jpg)
![Sport tab](screenshots/tab-sport.jpg)
![Settings tab](screenshots/tab-settings.jpg)
![Power tab](screenshots/tab-power.jpg)

**File browser with thumbnails** (when an add-on asks for a picture)
![File browser](screenshots/file-browser.jpg)

**Sport** – My sport, All games, Tables, Club page, Follow and Game page
![My sport](screenshots/sport-mysport.jpg)
![All games](screenshots/sport-allgames.jpg)
![Tables](screenshots/sport-tables.jpg)
![Club page](screenshots/sport-club.jpg)
![Follow](screenshots/sport-follow.jpg)
![Follow – add](screenshots/sport-follow-add.jpg)
![Game page](screenshots/sport-game.jpg)

> All screenshots are taken in a real Kodi. The titles, pictures and clubs are placeholders; the Sport screenshots use real ESPN data.

---

## Installation

1. Download [`repository.lucent.zip`](https://github.com/djdirty60/Lucent/raw/main/repository.lucent.zip) and copy it to your device, for example to the *Download* folder.
2. In Kodi, go to **Settings → System → Add-ons** and switch on **Unknown sources**.
3. Go to **Add-ons → Install from zip file** and choose `repository.lucent.zip`.
4. Go to **Add-ons → Install from repository → Lucent Repository → Look and feel → Skin → Lucent** and choose **Install**.
5. Kodi asks whether you want to use the new skin. Choose **Yes**.
   (Later: **Settings → Interface → Skin → Lucent**.)

Kodi also installs the YouTube add-on (for trailers), Lucent Subtitles and the white and coloured studio logo packs. Then the setup assistant opens and helps you pick a video add-on.

### Automatic updates

Because the skin is installed from the **Lucent Repository**, Kodi keeps it up to date by itself (Kodi's default: **Settings → System → Add-ons → Updates → Install updates automatically**).

### Which video add-on?

- **Any add-on:** long-press OK (or the menu button) on a folder in any add-on – or in your library – and choose **Add to Home as widget**. Pick the tab, the name and posters or landscape, and the row is there. The info page, flags, scores and views work for every add-on.
- **A video add-on that works together with Lucent:** its rows fill Home by themselves, and *Play*, *More*, *Library and lists*, *Mark as watched*, the calendar, trailers, subtitles and skip intro use it – also for titles that come from other add-ons.

### Customising the menu and widgets

1. Go to **Settings → Lucent → Menu and widgets**.
2. Choose a tab to change it:
   - **Widgets on this tab** – add, rename, move or remove widgets. A widget can be a row of your video add-on, something from your **Kodi library**, **any folder of any video add-on** (*Browse an add-on…*), your favourites, add-ons, a playlist, or a path you type yourself. Every widget can be shown as **posters** or **landscape** cards (up to 10 per tab).
   - **Name**, **Icon** and **When clicked** (show the widgets of this tab, open a Kodi screen, a folder of an add-on, an add-on, a favourite or a Kodi command).
   - **Move up / Move down**, **Make this the start tab**, **Remove this tab**.
3. **+ Add a tab** adds a new tab (up to 12). **Restore the default menu** puts everything back.

A tab without widgets shows the widgets of the start tab.

### Skin settings

**Settings → Lucent → Skin settings** has categories on the left and options on the right: **Appearance** (colour themes, AMOLED black, scale, font, clock, screensaver), **Layout** (menu and widgets, what OK does, poster labels, watched titles, the details page) and **Content & discovery, Playback, Integrations, Tracking, Profiles, Advanced, About** (shortcuts to the matching settings of your video add-on and of Kodi; Integrations also has your TMDB key, Lucent Subtitles and the update pop-up).

**Rating logos:** *Skin settings → Rating logos → Fetch* copies the logos of the `logos` folder of this page to your box; the lists and the info page then show IMDb, TMDB, Trakt, Rotten Tomatoes (fresh or rotten), the RT audience (full or spilt popcorn), Metacritic and Letterboxd with their logo instead of a coloured dot and name. You can also put your own `imdb.png`, `tmdb.png`, `trakt.png`, `rt.png`, `rt_rotten.png`, `rta.png`, `rta_spilt.png`, `mc.png`, `mcu.png` and `lb.png` in `userdata/addon_data/skin.lucent/logos/`. The logos are trademarks of their owners; Lucent is not affiliated with or endorsed by them.

### Back to the default skin

**Settings → System → Skin → Estuary** (in Kodi's own skin: Settings → Interface → Skin).

---

## Good to know

- **Remote:** the Home button of the remote goes to the Home screen from almost every window. In lists with a scroll bar press Right to get on the bar, then Up/Down scroll a page at a time.
- **Screen size:** Kodi scales the skin to any resolution (720p, 1080p, 4K). If you see black edges or the picture is cut off, use **Skin settings → Calibrate the picture**.
- **Not styled:** games and weather. Recordings and timers of live TV still need Estuary.
- Feedback and bug reports are welcome – please open an issue and include a photo of the screen or your safe log if something looks wrong.

---

## Folder structure

```
addon.xml            add-on info (id: skin.lucent)
xml/                 all windows and includes
media/               textures, icons, badges
fonts/               Inter font + licence
colors/              colour palette
language/            English and Dutch strings
scripts/menu.py      editor for the side menu and the widgets
scripts/info.py      info page: collection, studios, person / studio pages, opening titles, Trakt lists and watched
scripts/trailers.py  trailers on posters
scripts/agenda*.py   Calendar tab
scripts/sport*.py    Sport tab (ESPN games, tables, F1 page, reminders)
scripts/tv.py        TV tab and guide, live.py = live TV player
scripts/setup.py     setup assistant
scripts/updater.py   update pop-up
resources/           icon, fanart, what's new
repo/                Kodi repository (addons.xml + zips) for automatic updates
repository.lucent.zip  the repository add-on to install once
screenshots/         images for this README
```

---

## Credits and licences

- Inspired by the design of [Nuvio Arc](https://github.com/ysosrs123/NuvioTV-Fork). This skin is not affiliated with it.
- Sport data comes from ESPN; stadium photos from [TheSportsDB](https://www.thesportsdb.com); channel logos from [tv-logos](https://github.com/tv-logo/tv-logos) (CC BY-SA / BY-NC-SA, the logos belong to their owners).
- Font: [Inter](https://github.com/rsms/inter) by Rasmus Andersson, SIL Open Font License 1.1 (see `fonts/Inter-LICENSE.txt`).
- Icons and badges are original designs. The badges are not official Dolby or DTS logos.

## Trakt

Lucent uses Trakt but is not endorsed or certified by Trakt.

Privacy: see [PRIVACY.md](PRIVACY.md).
