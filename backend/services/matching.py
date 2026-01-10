from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from backend.models.media import AggregatedMovieData, AggregatedSeriesData


@dataclass(slots=True, frozen=True)
class MatchedItem:
    """A media item matched across backends."""

    # External IDs used for matching
    imdb_id: str | None
    tmdb_id: str | None
    tvdb_id: str | None

    # Data from each backend (None if not present)
    jellyfin_data: AggregatedMovieData | AggregatedSeriesData | None
    plex_data: AggregatedMovieData | AggregatedSeriesData | None

    # Matching metadata
    match_type: Literal["both", "jellyfin_only", "plex_only"]
    matched_on: str | None  # Which ID was used for matching (imdb, tmdb, tvdb)


def create_external_id_key(
    item: AggregatedMovieData | AggregatedSeriesData,
) -> tuple[str | None, str | None, str | None]:
    """Create a tuple of external IDs for matching."""
    if item.external_ids:
        return (item.external_ids.imdb, item.external_ids.tmdb, item.external_ids.tvdb)
    return (None, None, None)


def match_items(
    jellyfin_items: Sequence[AggregatedMovieData | AggregatedSeriesData],
    plex_items: Sequence[AggregatedMovieData | AggregatedSeriesData],
) -> list[MatchedItem]:
    """Match media items across Jellyfin and Plex using external IDs.

    Args:
        jellyfin_items: List of movies or series from Jellyfin
        plex_items: List of movies or series from Plex

    Returns:
        List of matched items, including items only in one backend
    """
    # Build lookup dictionaries for each ID type
    jf_by_imdb: dict[str, AggregatedMovieData | AggregatedSeriesData] = {}
    jf_by_tmdb: dict[str, AggregatedMovieData | AggregatedSeriesData] = {}
    jf_by_tvdb: dict[str, AggregatedMovieData | AggregatedSeriesData] = {}

    plex_by_imdb: dict[str, AggregatedMovieData | AggregatedSeriesData] = {}
    plex_by_tmdb: dict[str, AggregatedMovieData | AggregatedSeriesData] = {}
    plex_by_tvdb: dict[str, AggregatedMovieData | AggregatedSeriesData] = {}

    # Index Jellyfin items
    for item in jellyfin_items:
        if item.external_ids:
            if item.external_ids.imdb:
                jf_by_imdb[item.external_ids.imdb] = item
            if item.external_ids.tmdb:
                jf_by_tmdb[item.external_ids.tmdb] = item
            if item.external_ids.tvdb:
                jf_by_tvdb[item.external_ids.tvdb] = item

    # Index Plex items
    for item in plex_items:
        if item.external_ids:
            if item.external_ids.imdb:
                plex_by_imdb[item.external_ids.imdb] = item
            if item.external_ids.tmdb:
                plex_by_tmdb[item.external_ids.tmdb] = item
            if item.external_ids.tvdb:
                plex_by_tvdb[item.external_ids.tvdb] = item

    # Match items
    matched_items: list[MatchedItem] = []
    matched_jf_ids = set()
    matched_plex_ids = set()

    # Match on IMDB ID (most reliable)
    for imdb_id, jf_item in jf_by_imdb.items():
        if imdb_id in plex_by_imdb:
            plex_item = plex_by_imdb[imdb_id]
            matched_items.append(
                MatchedItem(
                    imdb_id=imdb_id,
                    tmdb_id=jf_item.external_ids.tmdb if jf_item.external_ids else None,
                    tvdb_id=jf_item.external_ids.tvdb if jf_item.external_ids else None,
                    jellyfin_data=jf_item,
                    plex_data=plex_item,
                    match_type="both",
                    matched_on="imdb",
                )
            )
            matched_jf_ids.add(jf_item.id)
            matched_plex_ids.add(plex_item.id)

    # Match on TMDB ID for unmatched items
    for tmdb_id, jf_item in jf_by_tmdb.items():
        if jf_item.id not in matched_jf_ids and tmdb_id in plex_by_tmdb:
            plex_item = plex_by_tmdb[tmdb_id]
            if plex_item.id not in matched_plex_ids:
                matched_items.append(
                    MatchedItem(
                        imdb_id=jf_item.external_ids.imdb
                        if jf_item.external_ids
                        else None,
                        tmdb_id=tmdb_id,
                        tvdb_id=jf_item.external_ids.tvdb
                        if jf_item.external_ids
                        else None,
                        jellyfin_data=jf_item,
                        plex_data=plex_item,
                        match_type="both",
                        matched_on="tmdb",
                    )
                )
                matched_jf_ids.add(jf_item.id)
                matched_plex_ids.add(plex_item.id)

    # Match on TVDB ID for unmatched items (mainly series)
    for tvdb_id, jf_item in jf_by_tvdb.items():
        if jf_item.id not in matched_jf_ids and tvdb_id in plex_by_tvdb:
            plex_item = plex_by_tvdb[tvdb_id]
            if plex_item.id not in matched_plex_ids:
                matched_items.append(
                    MatchedItem(
                        imdb_id=jf_item.external_ids.imdb
                        if jf_item.external_ids
                        else None,
                        tmdb_id=jf_item.external_ids.tmdb
                        if jf_item.external_ids
                        else None,
                        tvdb_id=tvdb_id,
                        jellyfin_data=jf_item,
                        plex_data=plex_item,
                        match_type="both",
                        matched_on="tvdb",
                    )
                )
                matched_jf_ids.add(jf_item.id)
                matched_plex_ids.add(plex_item.id)

    # Add Jellyfin-only items
    for jf_item in jellyfin_items:
        if jf_item.id not in matched_jf_ids:
            imdb_id, tmdb_id, tvdb_id = create_external_id_key(jf_item)
            matched_items.append(
                MatchedItem(
                    imdb_id=imdb_id,
                    tmdb_id=tmdb_id,
                    tvdb_id=tvdb_id,
                    jellyfin_data=jf_item,
                    plex_data=None,
                    match_type="jellyfin_only",
                    matched_on=None,
                )
            )

    # Add Plex-only items
    for plex_item in plex_items:
        if plex_item.id not in matched_plex_ids:
            imdb_id, tmdb_id, tvdb_id = create_external_id_key(plex_item)
            matched_items.append(
                MatchedItem(
                    imdb_id=imdb_id,
                    tmdb_id=tmdb_id,
                    tvdb_id=tvdb_id,
                    jellyfin_data=None,
                    plex_data=plex_item,
                    match_type="plex_only",
                    matched_on=None,
                )
            )

    return matched_items


def get_match_statistics(matched_items: list[MatchedItem]) -> dict:
    """Get statistics about matched items."""
    stats = {
        "total": len(matched_items),
        "matched_both": sum(1 for item in matched_items if item.match_type == "both"),
        "jellyfin_only": sum(
            1 for item in matched_items if item.match_type == "jellyfin_only"
        ),
        "plex_only": sum(1 for item in matched_items if item.match_type == "plex_only"),
        "matched_on_imdb": sum(
            1 for item in matched_items if item.matched_on == "imdb"
        ),
        "matched_on_tmdb": sum(
            1 for item in matched_items if item.matched_on == "tmdb"
        ),
        "matched_on_tvdb": sum(
            1 for item in matched_items if item.matched_on == "tvdb"
        ),
    }
    return stats
