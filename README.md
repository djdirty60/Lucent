# Nuvio Arc – Kodi skin (NOT FOR USE IN TEST PHASE)

A dark, cinematic Kodi skin inspired by **Nuvio Arc V2** (Cinematic Glass): large backdrops, glass panels, rounded cards, a white glow on the focused item and the Inter font. Built around **Seren** and **Trakt**, with home rows for continue watching, trending titles, your library and your own Trakt lists.

![Home screen](screenshots/home.jpg)

> The images are previews with placeholder artwork, rendered from the skin files. In Kodi you will see the real backdrops, posters and logos.

**Works with:** Kodi 21 (Omega) and Kodi 22 (Piers) · 1080p

---

## Features

### Home screen
- A big hero area with the backdrop, logo (or title), info pills and plot of the focused item.
- Rows, like in Nuvio:
  - **Continue watching · Shows** and **Continue watching · Movies** (Seren + Trakt)
  - **Trending movies** and **Trending shows** (Seren)
  - **Recently added movies** and **Recently added episodes** (your Kodi library, only shown if you have one)
  - **Up to 6 of your Trakt lists** – liked lists or your own lists, picked in the skin settings
- Every row can be switched on or off. Empty rows hide themselves.

### Sidebar
A slim icon rail that opens when you press left: Search, Home, Movies, TV shows, Library, Add-ons, Favourites, Settings and Power. Search, Movies and TV shows open the matching Seren menus directly.

![Sidebar](screenshots/sidebar.jpg)

### Five views for lists and Seren menus

| View | Best for |
| --- | --- |
| **Posters** | Hero info at the top and one row of posters |
| **Poster wall** | A full grid of posters |
| **Episodes** | Episode list with thumbnail, date and plot |
| **Landscape** | Hero info and one row of 16:9 cards |
| **List** | Menus and folders, with artwork and plot on the right |

The skin picks a fitting view automatically. You can change it with the **View** button at the top right.

### Everything else in the same style
Info page with cast, the video player and its menu, seek bar, subtitles search, bookmarks, Kodi settings, add-on settings, add-on info, file manager, keyboard, number pad, notifications, dialogs, power menu and screen calibration.

---

## Screenshots

**Posters**
![Posters](screenshots/posters.jpg)

**Poster wall**
![Poster wall](screenshots/poster-wall.jpg)

**Episodes**
![Episodes](screenshots/episodes.jpg)

**List view (Seren menu)**
![List](screenshots/list.jpg)

**Info page**
![Info page](screenshots/info.jpg)

**Player**
![Player](screenshots/player.jpg)

**Settings**
![Settings](screenshots/settings.jpg)

**Skin settings**
![Skin settings](screenshots/skin-settings.jpg)

**Keyboard**
![Keyboard](screenshots/keyboard.jpg)

---

## Installation

1. Download `skin.nuvioarc-1.0.1.zip` from the [Releases page](../../releases/latest).
   Don't use the green **Code → Download ZIP** button: Kodi needs the folder inside the zip to be called `skin.nuvioarc`, and only the release zip is built that way.
2. Copy the file to your device, for example to the *Download* folder.
3. In Kodi, go to **Settings → System → Add-ons** and switch on **Unknown sources**.
4. Go to **Add-ons → Install from zip file** and select `skin.nuvioarc-1.0.1.zip`.
5. Kodi asks whether you want to use the new skin. Choose **Yes**.
   (Later: **Settings → Interface → Skin → Nuvio Arc**.)

### Choosing your Trakt lists

1. Make sure Seren is installed and connected to Trakt.
2. Go to **Settings → Skin settings**.
3. Choose **Choose Trakt lists for the home screen**.
4. Tick up to 6 lists and confirm. They appear as rows on the home screen.

In the same screen you can switch rows on or off, remove all list rows and hide the clock.

### Back to the default skin

**Settings → Interface → Skin → Estuary.**

---

## Good to know

- **Seren is optional.** Without Seren the Seren rows are hidden and the skin works with your Kodi library only. With Seren, enter a free **Fanart.tv API key** in Seren for more logos.
- **Pairs with the Seren theme** [Nuvio Arc V2 for Seren](https://github.com/djdirty60/Seren-Thema), so Seren's source select, scraping and playing-next windows match the skin.
- **Not styled in this version:** Live TV (PVR), games and weather. Those windows won't open while this skin is active; switch to Estuary temporarily if you need them.
- This is a first release. Feedback and bug reports are welcome – please open an issue and include a photo of the screen or your `kodi.log` if something looks wrong.

---

## Folder structure

```
addon.xml            add-on info (id: skin.nuvioarc)
xml/                 all windows and includes
media/               textures, icons, badges
fonts/               Inter font + licence
colors/              colour palette
language/            English and Dutch strings
scripts/lists.py     helper to pick Trakt lists for the home screen
resources/           icon and fanart
screenshots/         images for this README
```

---

## Credits and licences

- Inspired by the design of [Nuvio Arc](https://github.com/ysosrs123/NuvioTV-Fork). This skin is not affiliated with it.
- Home rows use [Seren](https://github.com/nixgates/plugin.video.seren) by Nixgates. This skin is not affiliated with Seren either.
- Font: [Inter](https://github.com/rsms/inter) by Rasmus Andersson, SIL Open Font License 1.1 (see `fonts/Inter-LICENSE.txt`).
- Icons and badges are original designs. The badges are not official Dolby or DTS logos.
