import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


# ------------------------------------------------------------
# Episode parsing
# ------------------------------------------------------------

def parse_episode(path):
    path = Path(path)

    if not path.exists():
        raise SystemExit(f"Episode file not found: {path}")

    raw = path.read_text(encoding="utf-8")

    metadata = {}
    for name in ("production", "book", "episode", "title"):
        matches = re.findall(rf"(?mi)^@{name}\s+(.+?)\s*$", raw)
        if len(matches) != 1:
            raise SystemExit(
                f"Expected exactly one @{name} header in {path}; found {len(matches)}."
            )
        metadata[name] = matches[0].strip()

    for name in ("production", "book", "episode"):
        if not metadata[name].isdigit() or int(metadata[name]) < 1:
            raise SystemExit(f"@{name} must be a positive integer in {path}.")

    chunk_pattern = re.compile(
        r"(?mi)^@chunk\s+(\d+)\s*$"
    )

    matches = list(chunk_pattern.finditer(raw))

    if not matches:
        raise SystemExit("No @chunk markers found.")

    chunks = []

    for i, match in enumerate(matches):
        number = int(match.group(1))
        start = match.end()

        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(raw)
        )

        text = raw[start:end].strip()

        chunks.append({
            "number": number,
            "text": text,
        })

    return {
        **metadata,
        "chunks": chunks,
        "source_path": path,
        "source_text": raw,
    }


# ------------------------------------------------------------
# Utility
# ------------------------------------------------------------

def safe_filename(text):
    return re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        str(text)
    ).strip("_").lower()


def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            block = f.read(1024 * 1024)

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def require_program(name):
    path = shutil.which(name)

    if not path:
        raise SystemExit(
            f"{name} was not found on PATH.\n"
            f"Install FFmpeg and make sure both "
            f"ffmpeg.exe and ffprobe.exe are available."
        )

    return path


def run(command, capture=False):
    result = subprocess.run(
        command,
        text=True,
        capture_output=capture,
    )

    if result.returncode != 0:
        if capture:
            print(result.stdout)
            print(result.stderr)

        raise SystemExit(
            f"Command failed:\n{' '.join(command)}"
        )

    return result


# ------------------------------------------------------------
# Audio information
# ------------------------------------------------------------

def probe_duration(ffprobe, path):
    result = run(
        [
            ffprobe,
            "-v", "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture=True,
    )

    return float(result.stdout.strip())


def format_time(seconds):
    total_ms = round(seconds * 1000)

    hours = total_ms // 3_600_000
    total_ms %= 3_600_000

    minutes = total_ms // 60_000
    total_ms %= 60_000

    secs = total_ms // 1000
    millis = total_ms % 1000

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}."
        f"{millis:03d}"
    )


# ------------------------------------------------------------
# Generated chunk discovery
# ------------------------------------------------------------

def find_chunk_audio(
    episode,
    generated_dir,
):
    episode_number = safe_filename(
        episode["production"]
    )

    title = safe_filename(
        episode["title"]
    )

    results = []

    for chunk in episode["chunks"]:
        filename = (
            f"episode_{episode_number}_"
            f"{chunk['number']:02d}_"
            f"{title}.mp3"
        )

        path = generated_dir / filename

        if not path.exists():
            raise SystemExit(
                f"Missing generated audio:\n{path}"
            )

        meta_path = path.with_suffix(
            ".meta.json"
        )

        metadata = None

        if meta_path.exists():
            try:
                metadata = json.loads(
                    meta_path.read_text(
                        encoding="utf-8"
                    )
                )
            except Exception:
                print(
                    f"WARNING: Could not read "
                    f"{meta_path.name}"
                )

        results.append({
            "number": chunk["number"],
            "text": chunk["text"],
            "path": path,
            "metadata_path": (
                meta_path
                if meta_path.exists()
                else None
            ),
            "metadata": metadata,
        })

    return results


# ------------------------------------------------------------
# FFmpeg concat list
# ------------------------------------------------------------

def escape_ffconcat_path(path):
    # FFmpeg concat files use forward slashes
    # nicely even on Windows.
    value = str(path.resolve()).replace(
        "\\", "/"
    )

    value = value.replace("'", "'\\''")

    return f"file '{value}'"


def make_concat_file(chunks, path):
    lines = ["ffconcat version 1.0"]

    for chunk in chunks:
        lines.append(
            escape_ffconcat_path(chunk["path"])
        )

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="ascii",
    )


# ------------------------------------------------------------
# Post-production report
# ------------------------------------------------------------

def write_report(
    episode,
    chunks,
    wav_path,
    mp3_path,
    output_path,
    target_lufs,
):
    now = datetime.now(
        timezone.utc
    ).isoformat()

    total_duration = sum(
        c["duration"]
        for c in chunks
    )

    models = sorted({
        c["metadata"].get("model_id")
        for c in chunks
        if c["metadata"]
        and c["metadata"].get("model_id")
    })

    voices = sorted({
        c["metadata"].get("voice_id")
        for c in chunks
        if c["metadata"]
        and c["metadata"].get("voice_id")
    })

    estimated_cost = sum(
        (
            c["metadata"].get(
                "estimated_api_cost_usd", 0
            )
            if c["metadata"]
            else 0
        )
        for c in chunks
    )

    lines = [
        f"# Post-Production Notes",
        "",
        f"## Episode",
        "",
        f"**Production episode:** {episode['production']}",
        f"**Book:** {episode['book']}",
        f"**In-universe episode:** {episode['episode']}",
        f"**Title:** {episode['title']}",
        f"**Assembled UTC:** {now}",
        f"**Duration:** {format_time(total_duration)}",
        "",
        "## Production provenance",
        "",
        (
            "**Script:** ChatGPT-assisted alternate-history "
            "script, reviewed and edited by the project creator."
        ),
        (
            "**Narration provider:** ElevenLabs "
            "(paid/API-generated audio)."
        ),
        (
            "**Narrator voice:** Victoria."
        ),
        (
            "**Voice ID(s):** "
            + (
                ", ".join(voices)
                if voices
                else "Not recorded in chunk metadata."
            )
        ),
        (
            "**Model(s):** "
            + (
                ", ".join(models)
                if models
                else "Not recorded in chunk metadata."
            )
        ),
        (
            f"**Estimated ElevenLabs generation cost:** "
            f"${estimated_cost:.3f}"
        ),
        (
            f"**Editing master:** `{wav_path.name}`"
        ),
        (
            f"**Listening/export copy:** `{mp3_path.name}`"
        ),
        (
            f"**Loudness target:** {target_lufs} LUFS, mono"
        ),
        "",
        (
            "**Source episode SHA-256:** "
            f"`{sha256_text(episode['source_text'])}`"
        ),
        (
            "**WAV master SHA-256:** "
            f"`{sha256_file(wav_path)}`"
        ),
        (
            "**MP3 export SHA-256:** "
            f"`{sha256_file(mp3_path)}`"
        ),
        "",
        (
            "Chunk timestamps below refer to the WAV editing "
            "master and are intended for locating fixes in Audacity."
        ),
        "",
        "## Chunk timeline",
        "",
        "| Chunk | Start | End | Duration | File | Model |",
        "| ---: | ---: | ---: | ---: | --- | --- |",
    ]

    for chunk in chunks:
        model = ""

        if chunk["metadata"]:
            model = chunk["metadata"].get(
                "model_id", ""
            )

        lines.append(
            f"| {chunk['number']:02d} "
            f"| {format_time(chunk['start'])} "
            f"| {format_time(chunk['end'])} "
            f"| {format_time(chunk['duration'])} "
            f"| `{chunk['path'].name}` "
            f"| {model or 'unknown'} |"
        )

    lines += [
        "",
        "## Chunk provenance",
        "",
    ]

    for chunk in chunks:
        lines.append(
            f"### Chunk {chunk['number']:02d}"
        )
        lines.append("")

        lines.append(
            f"- Audio: `{chunk['path'].name}`"
        )

        lines.append(
            f"- Audio SHA-256: "
            f"`{sha256_file(chunk['path'])}`"
        )

        lines.append(
            f"- Source text SHA-256: "
            f"`{sha256_text(chunk['text'])}`"
        )

        if chunk["metadata"]:
            meta = chunk["metadata"]

            lines.append(
                f"- Generated UTC: "
                f"{meta.get('generated_utc', 'unknown')}"
            )

            lines.append(
                f"- Model: "
                f"{meta.get('model_id', 'unknown')}"
            )

            lines.append(
                f"- Voice ID: "
                f"{meta.get('voice_id', 'unknown')}"
            )

            lines.append(
                f"- Character count: "
                f"{meta.get('character_count', 'unknown')}"
            )

            lines.append(
                f"- Estimated API cost: "
                f"${meta.get('estimated_api_cost_usd', 0):.3f}"
            )

            if meta.get("request_id"):
                lines.append(
                    f"- ElevenLabs request ID: "
                    f"`{meta['request_id']}`"
                )

        else:
            lines.append(
                "- Generation metadata: unavailable "
                "(audio predates sidecar metadata)."
            )

        lines.append("")

    lines += [
        "## Manual post-production changes",
        "",
        (
            "Record any Audacity edits here so that the final "
            "master remains reproducible."
        ),
        "",
        "| Time | Change | Source/license |",
        "| --- | --- | --- |",
        "|  |  |  |",
        "",
        "Examples:",
        "",
        "- regenerated narration",
        "- mouse click / chair / paper Foley",
        "- trimmed pause",
        "- repaired chunk transition",
        "- music or other licensed material",
        "",
        "## Publication notes",
        "",
        (
            "Before commercial publication, re-check the current "
            "licenses/terms for all AI narration, music, Foley, "
            "images, quotations, and other incorporated material."
        ),
        (
            "Keep source/license details for any Foley or music "
            "added during post-production."
        ),
    ]

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ------------------------------------------------------------
# Main assembly
# ------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Assemble generated Catastrophes chunks "
            "into a WAV master and MP3 export."
        )
    )

    parser.add_argument(
        "episode_file",
        help="Annotated episode text file",
    )

    parser.add_argument(
        "--generated-dir",
        default="generated",
        help="Directory containing generated chunks",
    )

    parser.add_argument(
        "--output-dir",
        default="assembled",
        help="Directory for assembled episode",
    )

    parser.add_argument(
        "--lufs",
        type=float,
        default=-19.0,
        help="Integrated loudness target. Default: -19 LUFS",
    )

    parser.add_argument(
        "--true-peak",
        type=float,
        default=-1.5,
        help="Maximum true peak. Default: -1.5 dBTP",
    )

    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Do not apply loudness normalization",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite assembled outputs",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and show output paths without assembling audio",
    )
    
    parser.add_argument(
        "--through",
        type=int,
        help="Assemble only chunks 1 through this chunk number",
    )
    

    args = parser.parse_args()

    episode = parse_episode(
        args.episode_file
    )

    generated_dir = Path(
        args.generated_dir
    )

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )
    
    if args.through is not None:
        episode["chunks"] = [
            chunk
            for chunk in episode["chunks"]
            if chunk["number"] <= args.through
        ]

        if not episode["chunks"]:
            raise SystemExit(
                f"No chunks found through chunk {args.through}."
            )

    chunks = find_chunk_audio(
        episode,
        generated_dir,
    )

    episode_number = safe_filename(
        episode["production"]
    )

    title = safe_filename(
        episode["title"]
    )

    base = (
        f"episode_{episode_number}_{title}"
    )

    wav_path = output_dir / (
        f"{base}_master.wav"
    )

    mp3_path = output_dir / (
        f"{base}.mp3"
    )

    report_path = output_dir / (
        f"{base}_POST_PRODUCTION.md"
    )

    metadata_path = output_dir / (
        f"{base}.meta.json"
    )

    if args.dry_run:
        print(f"Validated {len(chunks)} chunks for production episode {episode['production']}.")
        print(f"WAV:      {wav_path}")
        print(f"MP3:      {mp3_path}")
        print(f"Metadata: {metadata_path}")
        print("Dry run complete. No files changed.")
        return

    ffmpeg = require_program("ffmpeg")
    ffprobe = require_program("ffprobe")

    # Probe durations and calculate timeline.
    cursor = 0.0

    for chunk in chunks:
        duration = probe_duration(
            ffprobe,
            chunk["path"],
        )

        chunk["duration"] = duration
        chunk["start"] = cursor
        chunk["end"] = cursor + duration

        cursor += duration

    if (
        not args.overwrite
        and (
            wav_path.exists()
            or mp3_path.exists()
        )
    ):
        raise SystemExit(
            "Assembled output already exists. "
            "Use --overwrite to replace it."
        )

    with tempfile.TemporaryDirectory() as temp:
        temp_dir = Path(temp)

        concat_path = temp_dir / (
            "chunks.ffconcat"
        )

        make_concat_file(
            chunks,
            concat_path,
        )

        raw_wav = temp_dir / (
            "raw_master.wav"
        )

        print()
        print(
            f"Assembling {len(chunks)} chunks..."
        )

        # Decode all chunk MP3s into one lossless WAV.
        run([
            ffmpeg,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_path),
            "-vn",
            "-ac", "1",
            "-ar", "44100",
            "-c:a", "pcm_s16le",
            str(raw_wav),
        ])

        if args.no_normalize:
            shutil.copyfile(
                raw_wav,
                wav_path,
            )

        else:
            print(
                f"Normalizing to "
                f"{args.lufs} LUFS..."
            )

            # Single-pass EBU R128 normalization.
            # Good for production masters; can later
            # be replaced by two-pass if desired.
            run([
                ffmpeg,
                "-y",
                "-i", str(raw_wav),
                "-af",
                (
                    f"loudnorm="
                    f"I={args.lufs}:"
                    f"LRA=7:"
                    f"TP={args.true_peak}"
                ),
                "-ac", "1",
                "-ar", "44100",
                "-c:a", "pcm_s16le",
                str(wav_path),
            ])

        print("Creating MP3 copy...")

        run([
            ffmpeg,
            "-y",
            "-i", str(wav_path),
            "-vn",
            "-ac", "1",
            "-ar", "44100",
            "-b:a", "128k",
            str(mp3_path),
        ])

    write_report(
        episode=episode,
        chunks=chunks,
        wav_path=wav_path,
        mp3_path=mp3_path,
        output_path=report_path,
        target_lufs=(
            "unchanged"
            if args.no_normalize
            else args.lufs
        ),
    )

    assembled_metadata = {
        "production_episode": int(episode["production"]),
        "book_number": int(episode["book"]),
        "in_universe_episode": int(episode["episode"]),
        "title": episode["title"],
    }
    metadata_path.write_text(
        json.dumps(assembled_metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("Assembly complete.")
    print(f"WAV:    {wav_path}")
    print(f"MP3:    {mp3_path}")
    print(f"Notes:  {report_path}")
    print(f"Metadata: {metadata_path}")
    print()
    print("Chunk timeline:")

    for chunk in chunks:
        print(
            f"  {chunk['number']:02d}: "
            f"{format_time(chunk['start'])} "
            f"-> "
            f"{format_time(chunk['end'])}"
        )


if __name__ == "__main__":
    main()
