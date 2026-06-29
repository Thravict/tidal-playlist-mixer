# Playlist Mixer for TIDAL

Playlist Mixer is a CLI tool for TIDAL to achieve true randomness.
It uses one or more source playlists and rewrites a target playlist with tracks in randomized order.

## Install

1. Install `tidal-playlist-mixer` from PyPI. It is recommended to use [pipx](https://pipx.pypa.io/stable/) instead of pip to avoid dependency conflicts.

```shell
# pipx
pipx install tidal-playlist-mixer

# pip
pip install tidal-playlist-mixer
```

2. Ensure the CLI is installed successfully

```shell
tidal-playlist-mixer version
```

No manual developer app setup is required.

## Usage

1. Login with your TIDAL account. You only need to login once; credentials are persisted in your config directory.

```shell
tidal-playlist-mixer login
```

The command prints a login URL and waits until you authorize the session in your browser.

2. Create a playlist. This playlist will be filled with your tracks in a random order. Create it and setup your privacy, title etc.

After creating the playlist, copy a link to the playlist (share > link). This link is used as a playlist target.

3. Mix playlists

```shell
# Use a playlist as source, and mix all tracks in another playlist
tidal-playlist-mixer mix --source <source-playlist> --playlist <target-playlist>

# A source/playlist can be either a link to a playlist
# https://listen.tidal.com/playlist/<playlist-id>
# https://tidal.com/browse/playlist/<playlist-id>
# trn:playlist:<playlist-id>
# or raw <playlist-id>

# Mix a playlist with multiple sources
tidal-playlist-mixer mix --source <source-playlist> --source <source-playlist> --playlist <target-playlist>

# Focus on the last x days. Focussing means, that tracks that were added in the last x days, are on top of the mixed playlist.
tidal-playlist-mixer mix --source <source-playlist> --playlist <target-playlist> --focus 10
```