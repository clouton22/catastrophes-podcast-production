#!/usr/bin/env python3

"""
Build the Catastrophes podcast RSS feed.

Expected directory layout:

    Catastrophes/
        feed.py
        feed_state.json          # private/local bookkeeping

        assembled/
            episode_01_the_columbia.mp3
            episode_01_the_columbia.meta.json
            episode_02_the_warning.mp3
            episode_02_the_warning.meta.json
            ...

        catastrophes-podcast/
            feed.xml
            .nojekyll
            artwork.jpg          # optional
            audio/
                ...

Production numbers are the canonical listening order and filename numbers.
Book and in-universe episode numbers come only from assembled metadata.
RSS uses season 1 and the production number as its episode number.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# Podcast configuration
# ---------------------------------------------------------------------------

PODCAST_TITLE = "Catastrophes"

PODCAST_DESCRIPTION = (
    "A history of the Catastrophes: the Great War, the Fascist War, "
    "the Coalition War, and the World War, and the systems that produced them."
)

PODCAST_LANGUAGE = "en-us"
PODCAST_AUTHOR = "Catastrophes"
PODCAST_EXPLICIT = "false"

GITHUB_USER = "clouton22"
GITHUB_REPO = "catastrophes-podcast"

BASE_URL = (
    f"https://{GITHUB_USER}.github.io/"
    f"{GITHUB_REPO}"
)

FEED_URL = f"{BASE_URL}/feed.xml"

ARTWORK_FILENAME = "artwork.jpg"

RSS_SEASON_NUMBER = 1


# ---------------------------------------------------------------------------
# XML namespaces
# ---------------------------------------------------------------------------

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"

ET.register_namespace("itunes", ITUNES)
ET.register_namespace("atom", ATOM)


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(dt):
    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def parse_iso_utc(value):
    return datetime.fromisoformat(
        value
    ).astimezone(timezone.utc)


def rfc2822(dt):
    return format_datetime(
        dt.astimezone(timezone.utc),
        usegmt=True,
    )


def episode_number_from_filename(path):
    """
    episode_03_roosevelt.mp3
    ->
    3
    """

    match = re.match(
        r"episode_(\d+)_",
        path.stem,
        re.IGNORECASE,
    )

    if not match:
        return None

    return int(match.group(1))


def episode_sort_key(path):
    number = episode_number_from_filename(path)

    if number is None:
        number = 10**9

    return (
        number,
        path.name.lower(),
    )


def stable_guid(path):
    """
    Stable episode identity.

    Deliberately independent of:
    - publication date
    - current year
    - hosting URL

    This allows the audio to move later without podcast
    clients treating it as a new episode.
    """

    return f"catastrophes:{path.stem}"


def feed_display_title(book_number, episode_number, title):
    return (
        f"Book {number_words(book_number)}, "
        f"Episode {number_words(episode_number)}: "
        f"{title}"
    )


def number_words(number):
    """Spell a positive integer in title case for narrator-facing titles."""
    number = int(number)
    if number < 1 or number >= 1_000_000:
        raise ValueError(f"Cannot spell number: {number}")

    ones = [
        "Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
        "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
        "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def under_thousand(value):
        parts = []
        if value >= 100:
            parts.extend((ones[value // 100], "Hundred"))
            value %= 100
        if value >= 20:
            parts.append(tens[value // 10])
            value %= 10
        if value:
            parts.append(ones[value])
        return " ".join(parts)

    if number >= 1000:
        thousands, remainder = divmod(number, 1000)
        result = f"{under_thousand(thousands)} Thousand"
        if remainder:
            result += f" {under_thousand(remainder)}"
        return result
    return under_thousand(number)


# ---------------------------------------------------------------------------
# Duration handling
# ---------------------------------------------------------------------------

def probe_duration_seconds(path):
    """
    Use ffprobe if installed.

    Returns rounded duration in seconds,
    or None if ffprobe is unavailable.
    """

    ffprobe = shutil.which("ffprobe")

    if not ffprobe:
        return None

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

        duration = float(
            result.stdout.strip()
        )

        return max(
            0,
            round(duration),
        )

    except Exception:
        return None


def format_duration(seconds):
    hours, remainder = divmod(
        seconds,
        3600,
    )

    minutes, seconds = divmod(
        remainder,
        60,
    )

    if hours:
        return (
            f"{hours}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    return (
        f"{minutes}:"
        f"{seconds:02d}"
    )


# ---------------------------------------------------------------------------
# Feed state
# ---------------------------------------------------------------------------

def load_state(path):
    """
    Private/local bookkeeping.

    Keeps publication dates and GUIDs stable across rebuilds.

    Example:

    {
      "episodes": {
        "episode_01_the_columbia.mp3": {
          "pub_date": "...",
          "guid": "...",
          "book": 1,
          "episode": 1,
          "title": "The Columbia"
        }
      }
    }
    """

    if not path.exists():
        return {
            "episodes": {}
        }

    try:
        state = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:
        raise SystemExit(
            f"Could not read {path}:\n{exc}"
        )

    state.setdefault(
        "episodes",
        {},
    )

    return state


def save_state(path, state):
    path.write_text(
        json.dumps(
            state,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# XML formatting
# ---------------------------------------------------------------------------

def indent_xml(element, level=0):
    indent = (
        "\n"
        + level * "  "
    )

    child_indent = (
        "\n"
        + (level + 1) * "  "
    )

    if len(element):
        if (
            not element.text
            or not element.text.strip()
        ):
            element.text = child_indent

        for child in element:
            indent_xml(
                child,
                level + 1,
            )

        if (
            not child.tail
            or not child.tail.strip()
        ):
            child.tail = indent

    elif (
        level
        and (
            not element.tail
            or not element.tail.strip()
        )
    ):
        element.tail = indent


# ---------------------------------------------------------------------------
# Directory discovery
# ---------------------------------------------------------------------------

def discover_directories(
    script_dir,
    assembled_override=None,
    repo_override=None,
):
    """
    Default layout:

        Catastrophes/
            feed.py
            feed_state.json
            assembled/
            catastrophes-podcast/
    """

    if assembled_override:
        assembled_dir = Path(
            assembled_override
        ).resolve()

    else:
        assembled_dir = (
            script_dir
            / "assembled"
        )

    if repo_override:
        repo_dir = Path(
            repo_override
        ).resolve()

    else:
        repo_dir = (
            script_dir
            / "catastrophes-podcast"
        )

    if not assembled_dir.exists():
        raise SystemExit(
            "Assembled directory not found:\n"
            f"{assembled_dir}"
        )

    if not repo_dir.exists():
        raise SystemExit(
            "Podcast repository directory not found:\n"
            f"{repo_dir}"
        )

    return (
        assembled_dir,
        repo_dir,
    )


# ---------------------------------------------------------------------------
# Episode discovery
# ---------------------------------------------------------------------------

def discover_episodes(assembled_dir):
    """
    Find finished episode MP3s.

    Each MP3 must have an adjacent .meta.json containing production_episode,
    book_number, in_universe_episode, and title.

        episode_01_the_columbia.mp3
        episode_02_the_warning.mp3
        episode_03_roosevelt.mp3
    """

    episodes = sorted(
        assembled_dir.glob(
            "episode_*.mp3"
        ),
        key=episode_sort_key,
    )

    episodes = [
        episode
        for episode in episodes
        if not episode.stem.endswith(
            "_master"
        )
    ]

    if not episodes:
        raise SystemExit(
            "No episode_*.mp3 files found in:\n"
            f"{assembled_dir}"
        )

    discovered = []
    required = {
        "production_episode", "book_number", "in_universe_episode", "title"
    }
    for audio_path in episodes:
        metadata_path = audio_path.with_suffix(".meta.json")
        if not metadata_path.exists():
            raise SystemExit(f"Missing assembled metadata:\n{metadata_path}")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit(f"Could not read {metadata_path}:\n{exc}")
        missing = sorted(required - metadata.keys())
        if missing:
            raise SystemExit(f"Missing metadata fields in {metadata_path}: {', '.join(missing)}")
        for field in ("production_episode", "book_number", "in_universe_episode"):
            try:
                metadata[field] = int(metadata[field])
            except (TypeError, ValueError):
                raise SystemExit(f"{field} must be an integer in {metadata_path}")
            if metadata[field] < 1:
                raise SystemExit(f"{field} must be positive in {metadata_path}")
        filename_number = episode_number_from_filename(audio_path)
        if filename_number != metadata["production_episode"]:
            raise SystemExit(
                f"Production number mismatch: {audio_path.name} vs {metadata_path.name}"
            )
        discovered.append((audio_path, metadata))

    production_numbers = [item[1]["production_episode"] for item in discovered]
    if len(production_numbers) != len(set(production_numbers)):
        raise SystemExit("Duplicate production_episode values in assembled metadata.")
    expected = list(range(1, len(production_numbers) + 1))
    if sorted(production_numbers) != expected:
        raise SystemExit(
            f"Production episodes must be sequential; found {sorted(production_numbers)}, expected {expected}."
        )
    return sorted(discovered, key=lambda item: item[1]["production_episode"])


# ---------------------------------------------------------------------------
# Feed builder
# ---------------------------------------------------------------------------

def build_feed(
    assembled_dir,
    repo_dir,
    state_path,
    dry_run=False,
    copy_audio=True,
):
    audio_dir = (
        repo_dir
        / "audio"
    )

    feed_path = (
        repo_dir
        / "feed.xml"
    )

    source_episodes = discover_episodes(
        assembled_dir
    )

    state = load_state(
        state_path
    )

    episode_state = state[
        "episodes"
    ]

    episodes = []

    for source, metadata in source_episodes:
        key = source.name

        production_episode = metadata["production_episode"]
        book_number = metadata["book_number"]
        episode_number = metadata["in_universe_episode"]
        title = str(metadata["title"]).strip()
        if not title:
            raise SystemExit(f"title must not be empty in {source.with_suffix('.meta.json')}")

        info = episode_state.get(
            key
        )

        # First discovery of this episode.
        if info is None:
            info = {
                "pub_date":
                    iso_utc(
                        utc_now()
                    ),

                "guid":
                    stable_guid(
                        source
                    ),

                "production_episode": production_episode,
                "book_number": book_number,
                "in_universe_episode": episode_number,
                "title": title,
            }

            episode_state[
                key
            ] = info

        info.update({
            "production_episode": production_episode,
            "book_number": book_number,
            "in_universe_episode": episode_number,
            "title": title,
        })

        destination = (
            audio_dir
            / source.name
        )

        if (
            copy_audio
            and not dry_run
        ):
            audio_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                source,
                destination,
            )

        duration = (
            probe_duration_seconds(
                source
            )
        )

        enclosure_url = (
            f"{BASE_URL}/audio/"
            f"{source.name}"
        )

        episodes.append({
            "source":
                source,

            "destination":
                destination,

            "book":
                book_number,

            "episode":
                episode_number,

            "production_episode":
                production_episode,

            "title":
                title,

            "feed_title":
                feed_display_title(
                    book_number,
                    episode_number,
                    title,
                ),

            "pub_date":
                parse_iso_utc(
                    info["pub_date"]
                ),

            "guid":
                info["guid"],

            "bytes":
                source.stat().st_size,

            "duration":
                duration,

            "url":
                enclosure_url,
        })

    if not episodes:
        raise SystemExit(
            "No usable podcast episodes found."
        )

    # Podcast feeds list newest production episodes first.
    episodes.sort(
        key=lambda item: item["production_episode"],
        reverse=True,
    )

    # -------------------------------------------------------
    # RSS
    # -------------------------------------------------------

    rss = ET.Element(
        "rss",
        {
            "version": "2.0"
        },
    )

    channel = ET.SubElement(
        rss,
        "channel",
    )

    ET.SubElement(
        channel,
        "title",
    ).text = PODCAST_TITLE

    ET.SubElement(
        channel,
        "link",
    ).text = BASE_URL

    ET.SubElement(
        channel,
        "description",
    ).text = PODCAST_DESCRIPTION

    ET.SubElement(
        channel,
        "language",
    ).text = PODCAST_LANGUAGE

    ET.SubElement(
        channel,
        "lastBuildDate",
    ).text = rfc2822(
        utc_now()
    )

    ET.SubElement(
        channel,
        f"{{{ITUNES}}}author",
    ).text = PODCAST_AUTHOR

    ET.SubElement(
        channel,
        f"{{{ITUNES}}}explicit",
    ).text = PODCAST_EXPLICIT

    ET.SubElement(
        channel,
        f"{{{ITUNES}}}type",
    ).text = "episodic"

    ET.SubElement(
        channel,
        f"{{{ATOM}}}link",
        {
            "href":
                FEED_URL,

            "rel":
                "self",

            "type":
                "application/rss+xml",
        },
    )

    ET.SubElement(
        channel,
        f"{{{ITUNES}}}category",
        {
            "text": "History"
        },
    )

    # -------------------------------------------------------
    # Optional artwork
    # -------------------------------------------------------

    artwork_path = (
        repo_dir
        / ARTWORK_FILENAME
    )

    if artwork_path.exists():
        artwork_url = (
            f"{BASE_URL}/"
            f"{ARTWORK_FILENAME}"
        )

        ET.SubElement(
            channel,
            f"{{{ITUNES}}}image",
            {
                "href":
                    artwork_url
            },
        )

        image = ET.SubElement(
            channel,
            "image",
        )

        ET.SubElement(
            image,
            "url",
        ).text = artwork_url

        ET.SubElement(
            image,
            "title",
        ).text = PODCAST_TITLE

        ET.SubElement(
            image,
            "link",
        ).text = BASE_URL

    # -------------------------------------------------------
    # Episode entries
    # -------------------------------------------------------

    for episode in episodes:
        item = ET.SubElement(
            channel,
            "item",
        )

        # Important:
        # The visible title contains the fictional Book/Episode
        # numbering even in clients that ignore iTunes metadata.
        ET.SubElement(
            item,
            "title",
        ).text = (
            episode["feed_title"]
        )

        ET.SubElement(
            item,
            "guid",
            {
                "isPermaLink":
                    "false"
            },
        ).text = (
            episode["guid"]
        )

        ET.SubElement(
            item,
            "pubDate",
        ).text = rfc2822(
            episode["pub_date"]
        )

        ET.SubElement(
            item,
            "enclosure",
            {
                "url":
                    episode["url"],

                "length":
                    str(
                        episode["bytes"]
                    ),

                "type":
                    "audio/mpeg",
            },
        )

        ET.SubElement(
            item,
            f"{{{ITUNES}}}season",
        ).text = str(
            RSS_SEASON_NUMBER
        )

        ET.SubElement(
            item,
            f"{{{ITUNES}}}episode",
        ).text = str(
            episode["production_episode"]
        )

        ET.SubElement(
            item,
            f"{{{ITUNES}}}episodeType",
        ).text = "full"

        ET.SubElement(
            item,
            f"{{{ITUNES}}}explicit",
        ).text = PODCAST_EXPLICIT

        if episode["duration"] is not None:
            ET.SubElement(
                item,
                f"{{{ITUNES}}}duration",
            ).text = format_duration(
                episode["duration"]
            )

        ET.SubElement(
            item,
            "description",
        ).text = (
            f"{episode['feed_title']}"
        )

    indent_xml(
        rss
    )

    xml_bytes = ET.tostring(
        rss,
        encoding="utf-8",
        xml_declaration=True,
    )

    # -------------------------------------------------------
    # Console summary
    # -------------------------------------------------------

    print()
    print(
        f"Assembled: "
        f"{assembled_dir}"
    )

    print(
        f"Repository: "
        f"{repo_dir}"
    )

    print(
        f"State:      "
        f"{state_path}"
    )

    print(
        f"Episodes:   "
        f"{len(episodes)}"
    )

    print(
        f"Feed URL:   "
        f"{FEED_URL}"
    )

    print()

    # Sort numerically for human-readable production summary.
    summary_episodes = sorted(
        episodes,
        key=lambda item: (
            item["production_episode"],
        ),
    )

    for episode in summary_episodes:
        if episode["duration"] is not None:
            duration_text = (
                format_duration(
                    episode["duration"]
                )
            )
        else:
            duration_text = "unknown"

        size_mb = (
            episode["bytes"]
            / 1024
            / 1024
        )

        print(
            f"Production {episode['production_episode']:02d}  "
            f"{episode['feed_title']}  "
            f"{size_mb:.1f} MB  "
            f"{duration_text}"
        )

    # -------------------------------------------------------
    # Dry-run stop
    # -------------------------------------------------------

    if dry_run:
        print()
        print(
            "Dry run only. "
            "No files changed."
        )
        return

    # -------------------------------------------------------
    # Write repository files
    # -------------------------------------------------------

    audio_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        repo_dir
        / ".nojekyll"
    ).touch()

    feed_path.write_bytes(
        xml_bytes
    )

    # State remains OUTSIDE the public repository.
    save_state(
        state_path,
        state,
    )

    print()
    print(
        f"Wrote feed: "
        f"{feed_path}"
    )

    print(
        f"Wrote state: "
        f"{state_path}"
    )

    print(
        f"Audio:      "
        f"{audio_dir}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Build the Catastrophes "
            "GitHub Pages podcast feed."
        )
    )

    parser.add_argument(
        "--assembled-dir",
        help=(
            "Override the assembled "
            "audio directory."
        ),
    )

    parser.add_argument(
        "--repo-dir",
        help=(
            "Override the "
            "catastrophes-podcast "
            "repository directory."
        ),
    )

    parser.add_argument(
        "--no-copy",
        action="store_true",
        help=(
            "Build the RSS feed "
            "without copying MP3s "
            "into the repository."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Show discovered episodes "
            "without changing files."
        ),
    )

    args = parser.parse_args()

    script_dir = (
        Path(__file__)
        .resolve()
        .parent
    )

    assembled_dir, repo_dir = (
        discover_directories(
            script_dir,
            assembled_override=(
                args.assembled_dir
            ),
            repo_override=(
                args.repo_dir
            ),
        )
    )

    # feed_state.json deliberately lives beside feed.py,
    # NOT inside catastrophes-podcast.
    state_path = (
        script_dir
        / "feed_state.json"
    )

    build_feed(
        assembled_dir=assembled_dir,
        repo_dir=repo_dir,
        state_path=state_path,
        dry_run=args.dry_run,
        copy_audio=(
            not args.no_copy
        ),
    )


if __name__ == "__main__":
    main()
