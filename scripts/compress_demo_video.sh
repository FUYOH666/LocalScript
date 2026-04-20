#!/usr/bin/env bash
set -euo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required but not found on PATH." >&2
  exit 1
fi

if [[ $# -lt 2 ]]; then
  echo "Usage: bash scripts/compress_demo_video.sh <input.mov|input.mp4> <output.mp4> [target_mb]" >&2
  exit 1
fi

INPUT="$1"
OUTPUT="$2"
TARGET_MB="${3:-90}"

if [[ ! -f "$INPUT" ]]; then
  echo "Input file not found: $INPUT" >&2
  exit 1
fi

if [[ "${OUTPUT##*.}" != "mp4" ]]; then
  echo "Output file must end with .mp4" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$INPUT")"
if [[ -z "$DURATION" ]]; then
  echo "Could not determine video duration." >&2
  exit 1
fi

# Leave room for container overhead and audio.
AUDIO_KBIT=128
TOTAL_KBIT=$(( TARGET_MB * 8192 ))
VIDEO_KBIT="$(python3 - <<PY
duration = float("$DURATION")
total_kbit = int("$TOTAL_KBIT")
audio_kbit = int("$AUDIO_KBIT")
video = max(600, int(total_kbit / duration - audio_kbit))
print(video)
PY
)"

PASSLOG="$TMP_DIR/ffmpeg2pass"

ffmpeg -y -i "$INPUT" \
  -vf "scale='min(1280,iw)':-2,fps=30" \
  -c:v libx264 -preset medium -b:v "${VIDEO_KBIT}k" -pass 1 \
  -passlogfile "$PASSLOG" \
  -an -f mp4 /dev/null

ffmpeg -y -i "$INPUT" \
  -vf "scale='min(1280,iw)':-2,fps=30" \
  -c:v libx264 -preset medium -b:v "${VIDEO_KBIT}k" -pass 2 \
  -passlogfile "$PASSLOG" \
  -c:a aac -b:a "${AUDIO_KBIT}k" -movflags +faststart \
  "$OUTPUT"

SIZE_MB="$(python3 - <<PY
from pathlib import Path
size = Path("$OUTPUT").stat().st_size / (1024 * 1024)
print(f"{size:.1f}")
PY
)"

echo "Created: $OUTPUT"
echo "Approx size: ${SIZE_MB} MB"
