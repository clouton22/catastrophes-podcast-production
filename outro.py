import argparse
import hashlib
import json
import math
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command, capture=False):
    result = subprocess.run(command, text=True, capture_output=capture)
    if result.returncode:
        if capture:
            print(result.stdout)
            print(result.stderr)
        raise SystemExit(f"Command failed: {' '.join(map(str, command))}")
    return result


def resolve(root, value):
    path = Path(value)
    return path if path.is_absolute() else root / path


def main():
    parser = argparse.ArgumentParser(
        description="Append a configurable music outro to a narration WAV master."
    )
    parser.add_argument("config", help="Outro JSON configuration file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = config_path.parent.parent

    narration = resolve(root, config["narration_master"])
    music = resolve(root, config["music_file"])
    output_wav = resolve(root, config["output_wav"])
    output_mp3 = resolve(root, config["output_mp3"])
    provenance = resolve(root, config["provenance_file"])

    gap = float(config.get("gap_seconds", 0.0))
    overlap = float(config.get("overlap_seconds", 0.0))
    overlap_gain = float(config.get("overlap_gain_db", 0.0))
    rise = float(config.get("post_narration_rise_seconds", 0.0))
    fade_in = float(config.get("fade_in_seconds", 0.0))
    play = float(config["play_seconds_before_fade"])
    fade = float(config["fade_seconds"])
    target = float(config["music_target_lufs"])
    true_peak = float(config.get("music_true_peak_dbtp", -1.5))
    gain = float(config.get("music_gain_db", 0.0))

    if min(gap, overlap, rise, fade_in, play, fade) < 0 or play + fade <= 0:
        raise SystemExit("Outro timings must be non-negative and non-empty.")
    if gap > 0 and overlap > 0:
        raise SystemExit("Configure either gap_seconds or overlap_seconds, not both.")
    for path in (narration, music):
        if not path.exists():
            raise SystemExit(f"Missing input: {path}")
    if output_wav.resolve() == narration.resolve():
        raise SystemExit("narration_master and output_wav must be different files.")

    print(f"Narration: {narration}")
    print(f"Music:     {music}")
    if overlap:
        print(f"Overlap:   {overlap:.3f} seconds at {overlap_gain:+.1f} dB")
        print(f"Fade in:   {fade_in:.3f} seconds")
        print(f"Rise:      {rise:.3f} seconds after narration")
    else:
        print(f"Gap:       {gap:.3f} seconds")
    print(f"Music:     {play:.3f} seconds, then {fade:.3f}-second fade")
    print(f"Level:     {target:.1f} LUFS, {gain:+.1f} dB trim")
    print(f"WAV:       {output_wav}")
    print(f"MP3:       {output_mp3}")
    if args.dry_run:
        print("Dry run complete. No files changed.")
        return

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise SystemExit("ffmpeg and ffprobe must be available on PATH.")

    narration_duration = float(run([
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(narration),
    ], capture=True).stdout.strip())
    if overlap > narration_duration:
        raise SystemExit("overlap_seconds exceeds the narration duration.")

    output_wav.parent.mkdir(parents=True, exist_ok=True)
    music_total = play + fade
    music_start = narration_duration + gap - overlap
    delay_ms = round(music_start * 1000)
    overlap_factor = math.pow(10.0, overlap_gain / 20.0)
    if overlap and rise:
        envelope = (
            f"if(lt(t,{overlap}),{overlap_factor},"
            f"if(lt(t,{overlap + rise}),"
            f"{overlap_factor}+(1-{overlap_factor})*(t-{overlap})/{rise},1))"
        )
    elif overlap:
        envelope = f"if(lt(t,{overlap}),{overlap_factor},1)"
    else:
        envelope = "1"

    filter_graph = (
        "[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=mono[n];"
        f"[1:a]atrim=0:{music_total},asetpts=PTS-STARTPTS,"
        "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=mono,"
        f"afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={play}:d={fade},"
        f"loudnorm=I={target}:LRA=7:TP={true_peak},"
        f"volume={gain}dB,volume='{envelope}':eval=frame,"
        f"adelay={delay_ms}:all=1[m];"
        "[n][m]amix=inputs=2:duration=longest:normalize=0:dropout_transition=0,"
        "alimiter=limit=0.944:latency=1,"
        "aformat=sample_fmts=s16:channel_layouts=mono[out]"
    )

    run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(narration), "-i", str(music),
        "-filter_complex", filter_graph, "-map", "[out]",
        "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "1",
        str(output_wav),
    ])
    run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(output_wav), "-vn", "-c:a", "libmp3lame",
        "-b:a", "128k", "-ar", "44100", "-ac", "1",
        str(output_mp3),
    ])
    duration = float(run([
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(output_wav),
    ], capture=True).stdout.strip())

    record = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "processor_file": str(Path(__file__).resolve()),
        "processor_sha256": sha256_file(Path(__file__).resolve()),
        "config_file": str(config_path),
        "config_sha256": sha256_file(config_path),
        "narration_master": str(narration),
        "narration_sha256": sha256_file(narration),
        "music_file": str(music),
        "music_sha256": sha256_file(music),
        "gap_seconds": gap,
        "overlap_seconds": overlap,
        "overlap_gain_db": overlap_gain,
        "post_narration_rise_seconds": rise,
        "fade_in_seconds": fade_in,
        "music_start_seconds": music_start,
        "narration_duration_seconds": narration_duration,
        "play_seconds_before_fade": play,
        "fade_seconds": fade,
        "music_target_lufs": target,
        "music_true_peak_dbtp": true_peak,
        "music_gain_db": gain,
        "output_duration_seconds": duration,
        "output_wav_sha256": sha256_file(output_wav),
        "output_mp3_sha256": sha256_file(output_mp3),
    }
    provenance.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Created {output_wav}")
    print(f"Created {output_mp3}")
    print(f"Provenance: {provenance}")


if __name__ == "__main__":
    main()
