#!/usr/bin/env bash
# split_monawat.sh
#
# For every artist folder, if it contains an album folder named "منوعات",
# move each song into its own album folder named after the song (stem),
# under the same artist:
#
#   /music/<artist>/منوعات/<song>.ext
#   -> /music/<artist>/<song>/<song>.ext
#
# Safe by default (DRY_RUN=1). Set DRY_RUN=0 to actually move files.

set -euo pipefail
IFS=$'\n\t'

MUSIC_ROOT="${1:-/opt/navidrome/music}"
DRY_RUN="${DRY_RUN:-1}"

# Adjust extensions if you have more formats
AUDIO_EXT_RE='.*\.(m4a|mp3|flac|ogg|opus|wav|aac)$'

msg() { printf '%s\n' "$*" >&2; }

[[ -d "$MUSIC_ROOT" ]] || { msg "ERROR: Music root not found: $MUSIC_ROOT"; exit 1; }

msg "Music root: $MUSIC_ROOT"
msg "DRY_RUN: $DRY_RUN (set DRY_RUN=0 to actually move)"
msg ""

# Find all "منوعات" directories that are exactly two levels deep: <artist>/منوعات
# (If you have deeper ones, remove -maxdepth/-mindepth.)
while IFS= read -r -d '' mon_dir; do
  artist_dir="$(dirname "$mon_dir")"
  artist_name="$(basename "$artist_dir")"

  msg "Processing: $artist_name / منوعات"

  # Only move files directly inside منوعات (not subfolders)
  while IFS= read -r -d '' f; do
    base="$(basename "$f")"
    stem="${base%.*}"
    ext="${base##*.}"

    # Destination: /music/<artist>/<stem>/<stem>.<ext>
    dest_album_dir="${artist_dir%/}/$stem"
    dest_file="${dest_album_dir%/}/$stem.$ext"

    # Create album folder
    if [[ "$DRY_RUN" == "1" ]]; then
      msg "  DRY_RUN: mkdir -p -- '$dest_album_dir'"
    else
      mkdir -p -- "$dest_album_dir"
    fi

    # If destination file already exists, don’t overwrite
    if [[ -e "$dest_file" ]]; then
      msg "  SKIP (exists): $dest_file"
      continue
    fi

    # Move
    if [[ "$DRY_RUN" == "1" ]]; then
      msg "  DRY_RUN: mv -- '$f' '$dest_file'"
    else
      mv -- "$f" "$dest_file"
      msg "  MOVED: $base -> $artist_name/$stem/"
    fi

  done < <(find "$mon_dir" -maxdepth 1 -type f -regextype posix-extended -regex ".*/$AUDIO_EXT_RE" -print0)

  # If "منوعات" is empty afterwards, remove it
  if [[ "$DRY_RUN" == "1" ]]; then
    msg "  DRY_RUN: rmdir --ignore-fail-on-non-empty -- '$mon_dir'"
  else
    rmdir --ignore-fail-on-non-empty -- "$mon_dir" || true
  fi

  msg ""
done < <(find "$MUSIC_ROOT" -mindepth 2 -maxdepth 2 -type d -name "منوعات" -print0)

msg "Done."
msg "If DRY_RUN=1, rerun with: DRY_RUN=0 $0 \"$MUSIC_ROOT\""

