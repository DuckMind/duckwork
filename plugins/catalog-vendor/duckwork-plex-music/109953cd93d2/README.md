# Plex Music — mini-Plexamp for Duckwork

A statusbar music player for your Plex music library, inside the Duckwork
desktop app. Playing / Browse / Playlists tabs, likes synced back to the
server, custom playlists, shuffle + repeat, sleep timer, queue editing,
and OS media keys. No Plexamp, no Plex Pass — the plugin *is* the player,
streaming direct from your own server.

## What you need

- **Plex Media Server** with a music library, reachable from your machine.
  That's it. Nothing else to install.
- Your Plex **token** (paste once — it stays in plugin storage):
  - *Server owners:* click **Get token…**, paste
    `%LOCALAPPDATA%\Plex Media Server` into the file picker's address bar,
    open `.LocalAdminToken`, paste the contents.
  - *Everyone else:* in Plex Web, open any track's **View XML** and copy the
    `X-Plex-Token` value from the URL.

## Setup

1. Open the **Plex Music** chip in the statusbar — the panel opens straight
   into settings on first run.
2. Server is prefilled (`http://127.0.0.1:32400`) — change it only if your
   server lives elsewhere.
3. Paste your token (or use **Get token…**), **Save & test**. Done.

## The tabs

- **Playing** — art, heart, Add to…, scrub bar, transport (shuffle, repeat
  off/all/one), queue with per-track × and Clear, sleep timer
  (Off → 15 → 30 → 60 → 90).
- **Browse** — search across artists/albums/tracks, A–Z jump, like from
  any row.
- **Playlists** — Shuffle Random Playlist, ＋ New playlist (seeds from the
  current song — Plex needs a first track), per-playlist rename (✎) and
  delete (× twice). Smart playlists like Liked Songs are server-managed:
  shown, never editable here.

## Good to know

- The heart is binary: tap writes rating 10 (feeds Plex's Liked Songs),
  tap again clears. Finer scores set in Plexamp still work — they just show
  as unliked here until tapped.
- Smart-playlist counts come from live totals, so the numbers are always
  right even though Plex's own stored counts lag.
- Keyboard, headphone, and Windows media-overlay keys all work, with
  title/artist/art in the overlay.

## Install

1. Copy the `plex-music` folder into your Duckwork desktop plugins directory
   (`%LOCALAPPDATA%\duckwork\desktop-plugins\` on Windows).
2. In the Duckwork desktop app: Settings → Plugins → turn on **Plex Music**,
   then reload (Ctrl/⌘K → Reload window). The chip appears bottom-right.

## Version

1.1.0 — catalog build (self-updater removed per store rule 3;
updates come through the plugin shop).
1.0.0 — initial public release.
