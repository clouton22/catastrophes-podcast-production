import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import hashlib
from datetime import datetime, timezone


MODELS = {
    "v3": {
        "model_id": "eleven_v3",
        "max_chars": 5000,
        "preferred_chars": 4500,
        "price_per_1000": 0.10,
    },
    "flash": {
        "model_id": "eleven_flash_v2_5",
        "max_chars": 40000,
        "preferred_chars": 10000,
        "price_per_1000": 0.05,
    },
}

DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_text(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

# ------------------------------------------------------------
# Episode parsing
# ------------------------------------------------------------

def parse_episode(path):
    """
    Parse a production script like:

        @production 01
        @book 01
        @episode 01
        @title The Columbia
        @revision 1.0

        @chunk 01
        text...

        @chunk 02
        text...

    Returns:
        {
            "production": "01",
            "book": "01",
            "episode": "01",
            "title": "The Columbia",
            "chunks": [
                {"number": 1, "text": "..."},
                ...
            ]
        }
    """

    path = Path(path)

    if not path.exists():
        raise SystemExit(f"Episode file not found: {path}")

    raw = path.read_text(encoding="utf-8")

    metadata = {}
    for name in ("production", "book", "episode", "title", "revision"):
        matches = re.findall(rf"(?mi)^@{name}\s+(.+?)\s*$", raw)
        if len(matches) != 1:
            raise SystemExit(
                f"Expected exactly one @{name} header in {path}; found {len(matches)}."
            )
        metadata[name] = matches[0].strip()

    for name in ("production", "book"):
        if not metadata[name].isdigit() or int(metadata[name]) < 1:
            raise SystemExit(f"@{name} must be a positive integer in {path}.")

    if (
        metadata["episode"].lower() != "supplemental"
        and (
            not metadata["episode"].isdigit()
            or int(metadata["episode"]) < 1
        )
    ):
        raise SystemExit(
            f"@episode must be a positive integer or 'supplemental' in {path}."
        )

    if not re.fullmatch(r"\d+\.\d+", metadata["revision"]):
        raise SystemExit(
            f"@revision must use MAJOR.MINOR format, such as 1.0, in {path}."
        )

    chunk_pattern = re.compile(
        r"(?mi)^@chunk\s+(\d+)\s*$"
    )

    matches = list(chunk_pattern.finditer(raw))

    if not matches:
        raise SystemExit(
            "No @chunk markers found.\n"
            "Expected markers like:\n"
            "@chunk 01"
        )

    chunks = []

    for i, match in enumerate(matches):
        number = int(match.group(1))

        start = match.end()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(raw)

        text = raw[start:end]

        # Remove metadata that may appear after the final chunk.
        text = re.sub(
            r"(?mi)^@(production|book|episode|title|revision)\s+.*$",
            "",
            text
        )

        text = text.strip()

        if not text:
            raise SystemExit(
                f"Chunk {number:02d} contains no narration."
            )

        chunks.append({
            "number": number,
            "text": text,
        })

    # Catch accidental duplicate chunk numbers.
    numbers = [c["number"] for c in chunks]

    if len(numbers) != len(set(numbers)):
        raise SystemExit("Duplicate @chunk numbers found.")

    return {
        **metadata,
        "chunks": chunks,
        "source_path": path,
    }


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def safe_filename(text):
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text)
    return text.strip("_").lower()


def estimate_cost(characters, model_config):
    return characters / 1000.0 * model_config["price_per_1000"]


def validate_chunks(episode, model_config):
    has_error = False

    for chunk in episode["chunks"]:
        count = len(chunk["text"])

        if count > model_config["max_chars"]:
            print(
                f"ERROR: Chunk {chunk['number']:02d} "
                f"is {count:,} characters. "
                f"Maximum is {model_config['max_chars']:,}."
            )
            has_error = True

        elif count > model_config["preferred_chars"]:
            print(
                f"WARNING: Chunk {chunk['number']:02d} "
                f"is {count:,} characters."
            )

    if has_error:
        raise SystemExit(
            "\nOne or more chunks are too large. "
            "No API requests were sent."
        )


def print_episode_summary(episode, model_config):
    print()
    print(f"Production:          {episode['production']}")
    print(f"Book:                {episode['book']}")
    print(f"In-universe episode: {episode['episode']}")
    print(f"Title:               {episode['title']}")
    print(f"Revision:            {episode['revision']}")
    print(f"Model:   {model_config['model_id']}")
    print()

    total_chars = 0
    total_cost = 0

    for chunk in episode["chunks"]:
        chars = len(chunk["text"])
        cost = estimate_cost(chars, model_config)

        total_chars += chars
        total_cost += cost

        print(
            f"Chunk {chunk['number']:02d}: "
            f"{chars:>5,} chars   "
            f"${cost:.3f}"
        )

    print("-" * 36)
    print(
        f"Total:    "
        f"{total_chars:>5,} chars   "
        f"${total_cost:.3f}"
    )
    print()


# ------------------------------------------------------------
# ElevenLabs request
# ------------------------------------------------------------

def generate_audio(
    text,
    model_config,
    api_key,
    voice_id,
    previous_text=None,
    next_text=None,
    seed=None,
):
    body = {
        "text": text,
        "model_id": model_config["model_id"],
        "apply_text_normalization": "auto",
    }

    if model_config["model_id"] != "eleven_v3":
        if previous_text:
            body["previous_text"] = previous_text
        if next_text:
            body["next_text"] = next_text

    if seed is not None:
        body["seed"] = seed

    url = (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        f"{urllib.parse.quote(voice_id)}"
        f"?output_format={DEFAULT_OUTPUT_FORMAT}"
    )

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=180,
        ) as response:
            audio = response.read()

            headers = {
                key.lower(): value
                for key, value in response.headers.items()
            }

        return audio, headers

    except urllib.error.HTTPError as exc:
        print()
        print(f"ElevenLabs returned HTTP {exc.code}.")

        try:
            error_body = exc.read().decode("utf-8")
            print(error_body)
        except Exception:
            pass

        raise

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Network error: {exc.reason}"
        ) from exc


# ------------------------------------------------------------
# Chunk generation
# ------------------------------------------------------------

def generate_chunk(
    episode,
    chunk_index,
    model_config,
    output_dir,
    api_key,
    voice_id,
    seed=None,
    overwrite=False,
):
    chunks = episode["chunks"]
    chunk = chunks[chunk_index]

    previous_text = None
    next_text = None

    if chunk_index > 0:
        previous_text = chunks[chunk_index - 1]["text"]

    if chunk_index + 1 < len(chunks):
        next_text = chunks[chunk_index + 1]["text"]

    episode_number = safe_filename(str(episode["production"]))
    title = safe_filename(episode["title"])

    filename = (
        f"episode_{episode_number}_"
        f"{chunk['number']:02d}_"
        f"{title}.mp3"
    )

    output_path = output_dir / filename

    if output_path.exists() and not overwrite:
        print(
            f"SKIP chunk {chunk['number']:02d}: "
            f"{output_path.name} already exists."
        )
        return

    chars = len(chunk["text"])
    cost = estimate_cost(chars, model_config)

    print()
    print(
        f"Generating chunk {chunk['number']:02d} "
        f"({chars:,} chars, approx ${cost:.3f})..."
    )

    audio, response_headers = generate_audio(
        text=chunk["text"],
        model_config=model_config,
        api_key=api_key,
        voice_id=voice_id,
        previous_text=previous_text,
        next_text=next_text,
        seed=seed,
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_bytes(audio)
    
    metadata = {
        "production_episode": int(episode["production"]),
        "book_number": int(episode["book"]),
        "in_universe_episode": (
            int(episode["episode"])
            if episode["episode"].isdigit()
            else episode["episode"].lower()
        ),
        "title": episode["title"],
        "production_revision": episode["revision"],
        "chunk": chunk["number"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "ElevenLabs",
        "voice_id": voice_id,
        "model_id": model_config["model_id"],
        "output_format": DEFAULT_OUTPUT_FORMAT,
        "character_count": chars,
        "estimated_api_cost_usd": round(cost, 6),
        "seed": seed,
        "source_episode_file": str(episode["source_path"]),
        "source_text_sha256": sha256_text(chunk["text"]),
        "audio_sha256": sha256_bytes(audio),
        "request_id": (
            response_headers.get("request-id")
            or response_headers.get("x-request-id")
        ),
    }

    metadata_path = output_path.with_suffix(".meta.json")

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print(f"Metadata:   {metadata_path}")

    print(f"Saved: {output_path}")
    print(
        f"Size:  {len(audio) / 1024 / 1024:.2f} MB"
    )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate ElevenLabs TTS from a "
            "chunked Catastrophes production script."
        )
    )

    parser.add_argument(
        "episode_file",
        help="Full episode production text file",
    )

    parser.add_argument(
        "--model",
        choices=MODELS.keys(),
        default="v3",
        help="TTS model. Default: v3",
    )

    action = parser.add_mutually_exclusive_group()

    action.add_argument(
        "--chunk",
        type=int,
        help="Generate only this chunk number",
    )

    action.add_argument(
        "--all",
        action="store_true",
        help="Generate every chunk",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="Show parsed chunks and estimated costs",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only. Do not call ElevenLabs.",
    )

    parser.add_argument(
        "--output-dir",
        default="generated",
        help="Directory for generated MP3 files",
    )

    parser.add_argument(
        "--seed",
        type=int,
        help="Optional generation seed",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing MP3 files",
    )

    args = parser.parse_args()

    model_config = MODELS[args.model]

    episode = parse_episode(args.episode_file)

    validate_chunks(
        episode,
        model_config
    )

    print_episode_summary(
        episode,
        model_config
    )

    if args.list or args.dry_run:
        if args.dry_run:
            print(
                "Dry run complete. "
                "No API requests sent."
            )
        return

    if not args.all and args.chunk is None:
        raise SystemExit(
            "Specify either --chunk NUMBER or --all.\n"
            "Use --list to inspect the episode first."
        )

    api_key = os.environ.get(
        "ELEVENLABS_API_KEY"
    )

    voice_id = os.environ.get(
        "ELEVENLABS_VOICE_ID"
    )

    if not api_key:
        raise SystemExit(
            "ELEVENLABS_API_KEY is not set."
        )

    if not voice_id:
        raise SystemExit(
            "ELEVENLABS_VOICE_ID is not set."
        )

    output_dir = Path(args.output_dir)

    if args.chunk is not None:
        matching = [
            i
            for i, chunk in enumerate(
                episode["chunks"]
            )
            if chunk["number"] == args.chunk
        ]

        if not matching:
            available = ", ".join(
                str(c["number"])
                for c in episode["chunks"]
            )

            raise SystemExit(
                f"Chunk {args.chunk} not found.\n"
                f"Available chunks: {available}"
            )

        generate_chunk(
            episode=episode,
            chunk_index=matching[0],
            model_config=model_config,
            output_dir=output_dir,
            api_key=api_key,
            voice_id=voice_id,
            seed=args.seed,
            overwrite=args.overwrite,
        )

    else:
        for i in range(len(episode["chunks"])):
            try:
                generate_chunk(
                    episode=episode,
                    chunk_index=i,
                    model_config=model_config,
                    output_dir=output_dir,
                    api_key=api_key,
                    voice_id=voice_id,
                    seed=args.seed,
                    overwrite=args.overwrite,
                )

            except Exception:
                print()
                print(
                    "Generation stopped because "
                    "a chunk failed."
                )
                print(
                    "Already-generated files "
                    "have been kept."
                )
                sys.exit(1)

        print()
        print("Episode generation complete.")


if __name__ == "__main__":
    main()
