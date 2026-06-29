"""
Playlist mixing logic for TIDAL.
"""

from datetime import datetime, timezone
import time
from urllib.parse import urlparse

from requests.exceptions import HTTPError


def parse_tidal_playlist_id(value: str) -> str:
    """
    Parse a TIDAL playlist UUID from raw UUID, TRN, or TIDAL playlist URLs.
    """
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Playlist reference must not be empty")

    if cleaned.startswith("trn:playlist:"):
        return cleaned.split(":")[-1]

    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        parsed = urlparse(cleaned)
        parts = [part for part in parsed.path.split("/") if part]
        if "playlist" in parts:
            idx = parts.index("playlist")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        raise ValueError(f"Unable to parse playlist id from URL: {value}")

    return cleaned


def track_added_at(track) -> datetime | None:
    """
    Return the best-effort "added at" timestamp for a TIDAL track object.
    """
    for attr in ("user_date_added", "date_added", "added_at"):
        value = getattr(track, attr, None)
        if value is not None:
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value
    return None


def comparable_datetime(value: datetime) -> datetime:
    """
    Normalize datetime to a comparable naive UTC representation.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class PlaylistMixer:
    """
    Class for managing and mixing playlists.
    """

    def __init__(self, session):
        self.session = session
        self.playlist_cache = {}

    def get_playlist(self, playlist_id: str):
        """
        Get playlist by id, using cache if available.
        """
        parsed_id = parse_tidal_playlist_id(playlist_id)
        if parsed_id in self.playlist_cache:
            return self.playlist_cache[parsed_id]

        playlist = self.session.playlist(parsed_id)
        self.playlist_cache[parsed_id] = playlist
        return playlist

    def get_playlist_tracks(
        self,
        playlist_id: str,
        added_before: datetime = None,
        added_after: datetime = None,
        date_inclusive: bool = False,
    ) -> list:
        """
        Get tracks from a playlist, optionally filtered by date-added.
        """
        playlist = self.get_playlist(playlist_id)

        if added_before and added_after and added_before < added_after:
            raise ValueError("added_before must be greater than added_after")

        added_before_cmp = comparable_datetime(added_before) if added_before else None
        added_after_cmp = comparable_datetime(added_after) if added_after else None

        if hasattr(playlist, "tracks_paginated"):
            tracks = playlist.tracks_paginated()
        else:
            tracks = playlist.tracks()

        if not added_before and not added_after:
            return list(tracks)

        result = []
        for track in tracks:
            added_at = track_added_at(track)
            if added_at is None:
                continue
            added_at_cmp = comparable_datetime(added_at)

            if added_after_cmp and (
                (date_inclusive and added_at_cmp < added_after_cmp)
                or (not date_inclusive and added_at_cmp <= added_after_cmp)
            ):
                continue
            if added_before_cmp and (
                (date_inclusive and added_at_cmp > added_before_cmp)
                or (not date_inclusive and added_at_cmp >= added_before_cmp)
            ):
                continue
            result.append(track)

        return result

    def clear_playlist(self, playlist_id: str, chunk_size: int = 50):
        """
        Clear all tracks from a playlist.

        tidalapi's UserPlaylist.clear() refreshes its ETag from the playlist
        metadata endpoint, which TIDAL rejects with HTTP 412 for item deletions.
        Refreshing the ETag via tracks() before each delete avoids this.
        """
        playlist = self.get_playlist(playlist_id)
        if not hasattr(playlist, "remove_by_indices"):
            raise RuntimeError(
                "Playlist is not writable. Ensure target playlist is owned by your account"
            )

        parsed_id = parse_tidal_playlist_id(playlist_id)
        try:
            while playlist.tracks(limit=chunk_size):
                count = min(playlist.num_tracks, chunk_size)
                for attempt in range(15):
                    try:
                        playlist.tracks(limit=chunk_size)
                        start = playlist.num_tracks - count
                        if not playlist.remove_by_indices(range(start, playlist.num_tracks)):
                            raise RuntimeError("Failed to clear playlist")
                        break
                    except HTTPError as exc:
                        status = exc.response.status_code if exc.response else None
                        if status == 412 and attempt < 14:
                            time.sleep(min(2 + attempt, 10))
                            playlist = self.session.playlist(parsed_id)
                            self.playlist_cache[parsed_id] = playlist
                            count = min(playlist.num_tracks, chunk_size)
                            continue
                        raise
        except HTTPError as exc:
            raise RuntimeError(f"Failed to clear playlist: {exc}") from exc

        return playlist

    def add_tracks(self, playlist, track_ids: list, chunk_size: int = 100):
        """
        Add tracks in chunks, refreshing playlist state on ETag conflicts.
        """
        parsed_id = parse_tidal_playlist_id(playlist.id)
        for i in range(0, len(track_ids), chunk_size):
            chunk = track_ids[i : i + chunk_size]
            for attempt in range(15):
                try:
                    playlist.tracks(limit=1)
                    playlist.add(chunk, allow_duplicates=True)
                    break
                except HTTPError as exc:
                    status = exc.response.status_code if exc.response else None
                    if status == 412 and attempt < 14:
                        time.sleep(min(2 + attempt, 10))
                        playlist = self.session.playlist(parsed_id)
                        self.playlist_cache[parsed_id] = playlist
                        continue
                    raise RuntimeError(f"Failed to add tracks: {exc}") from exc
        return playlist
