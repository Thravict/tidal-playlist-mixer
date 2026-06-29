"""
Playlist Mixer
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random
from os import path, environ
from pathlib import Path
import importlib.metadata
import truststore

import click
from tidalapi.exceptions import ObjectNotFound

from tidal_playlist_mixer.config import Config, UserConfig
from tidal_playlist_mixer.mixer import PlaylistMixer, parse_tidal_playlist_id
from tidal_playlist_mixer.tidal import TidalAuth


@click.group()
@click.option(
    "--timezone",
    help=f"Timezone to use. (env: {Config.TMEZONE_ENV})",
    envvar=Config.TMEZONE_ENV,
    default="UTC",
)
@click.option(
    "--config-dir",
    help=f"Config directory. Defaults to $XDG_CONFIG_HOME/playlist-mixer or ~/.config/playlist-mixer (env: {Config.CONFIG_DIR_ENV})",
    envvar=Config.CONFIG_DIR_ENV,
)
@click.option(
    "--cache-dir",
    help=f"Cache directory. Defaults to $XDG_CACHE_HOME/playlist-mixer or ~/.cache/playlist-mixer (env: {Config.CACHE_DIR_ENV})",
    envvar=Config.CACHE_DIR_ENV,
)
def cli(
    timezone: str = None,
    config_dir: str = None,
    cache_dir: str = None,
):
    """
    Playlist Mixer for TIDAL.
    """

    truststore.inject_into_ssl()

    user_home = Path.home()

    # Determine and ensure config directory
    if config_dir is None:
        xdg_config_home = environ.get("XDG_CONFIG_HOME", None)
        if xdg_config_home is not None:
            config_dir = path.join(xdg_config_home, "playlist-mixer")

    if config_dir is None:
        config_dir = path.join(user_home, ".config/playlist-mixer")

    Config.config_dir = path.abspath(config_dir)
    Path(Config.config_dir).mkdir(parents=True, exist_ok=True)

    # Determine and ensure cache directory
    if cache_dir is None:
        xdg_cache_home = environ.get("XDG_CACHE_HOME", None)
        if xdg_cache_home is not None:
            cache_dir = path.join(xdg_cache_home, "playlist-mixer")

    if cache_dir is None:
        cache_dir = path.join(user_home, ".cache/playlist-mixer")

    Config.cache_dir = path.abspath(cache_dir)
    Path(Config.cache_dir).mkdir(parents=True, exist_ok=True)

    # Determine timezone
    Config.timezone = ZoneInfo(timezone)


@cli.command(name="mix")
@click.option("-p", "--playlist", help="Output playlist id", required=True)
@click.option(
    "-s", "--source", "sources", help="Source playlist uri", multiple=True, required=True
)
@click.option("-f", "--focus", "focus", help="Focus days", type=int, default=0)
def cli_mix(
    playlist,
    sources: list[str],
    focus: int,
):
    """Command: Mix playlist"""
    try:
        session = TidalAuth.get_session()
    except RuntimeError as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
        return

    click.echo("Mixing playlist..")
    if focus > 0:
        click.echo(f"Focus: {focus} days")

    pm = PlaylistMixer(session)

    click.echo(f"Fetching {len(sources)} sources..")
    for source in sources:
        try:
            source_playlist = pm.get_playlist(source)
        except (ObjectNotFound, ValueError) as e:
            click.echo(click.style(f"Error: {e}", fg="red"))
            return
        click.echo(
            f"Fetched Playlist: {source_playlist.name} ({source_playlist.id}) with {source_playlist.num_tracks} tracks"
        )

    now = datetime.now(tz=Config.timezone)
    focus_threshold = now - timedelta(days=focus)

    track_pool1 = []
    track_pool2 = []

    for source in sources:
        track_pool1 += pm.get_playlist_tracks(
            source, added_after=focus_threshold, date_inclusive=True
        )
        track_pool2 += pm.get_playlist_tracks(
            source, added_before=focus_threshold, date_inclusive=False
        )

    random.shuffle(track_pool1)
    random.shuffle(track_pool2)

    click.echo(f"Track pool 1: {len(track_pool1)}")
    click.echo(f"Track pool 2: {len(track_pool2)}")

    target_playlist_id = parse_tidal_playlist_id(playlist)
    try:
        managed_playlist = pm.get_playlist(target_playlist_id)
    except (ObjectNotFound, ValueError) as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
        return

    if not hasattr(managed_playlist, "edit"):
        click.echo(
            click.style(
                "Error: Target playlist is not writable. Ensure you own the playlist.",
                fg="red",
            )
        )
        return

    track_ids = [str(track.id) for track in track_pool1 + track_pool2]

    try:
        managed_playlist = pm.clear_playlist(managed_playlist.id)
        managed_playlist = pm.add_tracks(managed_playlist, track_ids)
    except RuntimeError as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
        return

    dts = now.strftime("%Y-%m-%d %H:%M:%S")
    managed_playlist.edit(title=f"Mixed {dts}")

    click.echo(f"Playlist mixed successfully: {managed_playlist.listen_url}")


@cli.command(name="login")
def cli_login():
    """Command: Login to TIDAL"""
    try:
        session = TidalAuth.login(fn_print=click.echo)
    except Exception as e:
        click.echo(click.style("Failed to login to TIDAL:", fg="red"))
        click.echo(click.style(str(e), fg="red"))
        return

    user_config = TidalAuth.user_config_from_session(session)
    UserConfig.store_user_config(user_config)

    click.echo(f"Logged in successfully as user {user_config.user_id}")


@cli.command(name="logout")
def cli_logout():
    """Command: Logout from TIDAL"""

    UserConfig.delete_user_config()
    click.echo("Logged out successfully")


@cli.command(name="version")
def cli_version():
    """Command: Show version"""

    version = importlib.metadata.version("tidal-playlist-mixer")

    click.echo(f"Playlist Mixer {version}")


def main():
    """Main entrypoint"""

    cli(
        max_content_width=160,
    )


if __name__ == "__main__":
    main()
