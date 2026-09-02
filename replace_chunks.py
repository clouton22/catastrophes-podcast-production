import argparse
import re
from pathlib import Path


def chunks(text):
    matches = list(re.finditer(r"(?mi)^@chunk\s+(\d+)\s*$", text))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[int(match.group(1))] = text[match.start():end].rstrip() + "\n"
    return result


def main():
    parser = argparse.ArgumentParser(description="Replace marked chunks in a production script.")
    parser.add_argument("episode_file")
    parser.add_argument("replacement_file")
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()

    episode_path = Path(args.episode_file)
    original = episode_path.read_text(encoding="utf-8")
    replacements = chunks(Path(args.replacement_file).read_text(encoding="utf-8"))
    if not replacements:
        raise SystemExit("Replacement file contains no @chunk markers.")

    updated = re.sub(
        r"(?mi)^@revision[ \t]+\d+\.\d+[ \t]*$",
        f"@revision {args.revision}",
        original,
        count=1,
    )
    for number, replacement in replacements.items():
        pattern = re.compile(
            rf"(?ms)^@chunk\s+0*{number}\s*$.*?(?=^@chunk\s+\d+\s*$|\Z)"
        )
        updated, count = pattern.subn(replacement + "\n", updated, count=1)
        if count != 1:
            raise SystemExit(f"Could not replace chunk {number:02d} exactly once.")

    episode_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
