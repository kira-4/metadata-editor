#!/usr/bin/env bash
# restructure_music.sh
#
# Goal:
# Move top-level album folders (e.g. "إصدار ...") into Artist/Album layout.
# Example:
#   /music/إصدار ذهب        -> /music/باسم الكربلائي/إصدار ذهب
#   /music/إصدار افرح...    -> /music/بسام العبدالله/إصدار افرح...
#
# This script supports TWO modes:
#  1) Mapping file mode (recommended): you create/adjust a TSV mapping once, then run non-interactively.
#  2) Interactive mode: if no mapping file exists, it will ask you artist for each album folder and create the mapping file.

set -euo pipefail
IFS=$'\n\t'

MUSIC_ROOT="${1:-/opt/navidrome/music}"
MAPPING_FILE="${MUSIC_ROOT%/}/album_to_artist.tsv"
DRY_RUN="${DRY_RUN:-1}"   # DRY_RUN=1 (default) prints actions, DRY_RUN=0 actually moves

# The 3 artists you mentioned:
ARTIST_1="باسم الكربلائي"
ARTIST_2="بسام العبدالله"
ARTIST_3="صالح الدرازي"

# Which folders to consider as "album folders" at library root:
# Customize if needed (e.g. add "Album *" etc.)
ALBUM_GLOB_1="إصدار "*   # top-level folders like "إصدار ذهب"
ALBUM_GLOB_2="اصدار "*   # in case of different hamza/spelling

msg() { printf '%s\n' "$*" >&2; }
die() { msg "ERROR: $*"; exit 1; }

[[ -d "$MUSIC_ROOT" ]] || die "Music root not found: $MUSIC_ROOT"

# --- Helper: safe move (keeps names; won’t overwrite) ---
do_move() {
  local src="$1"
  local dest_dir="$2"
  local base
  base="$(basename "$src")"
  mkdir -p "$dest_dir"

  if [[ -e "$dest_dir/$base" ]]; then
    msg "SKIP (already exists): $dest_dir/$base"
    return 0
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    msg "DRY_RUN: mv -- '$src' '$dest_dir/'"
  else
    mv -- "$src" "$dest_dir/"
    msg "MOVED: $src -> $dest_dir/"
  fi
}

# --- Load mapping file (TSV: album_folder<TAB>artist) ---
declare -A MAP
load_mapping() {
  [[ -f "$MAPPING_FILE" ]] || return 0
  while IFS=$'\t' read -r album artist; do
    [[ -z "${album:-}" || -z "${artist:-}" ]] && continue
    MAP["$album"]="$artist"
  done < <(grep -v '^\s*#' "$MAPPING_FILE" || true)
}

# --- Create mapping file header if missing ---
init_mapping_file() {
  if [[ ! -f "$MAPPING_FILE" ]]; then
    cat > "$MAPPING_FILE" <<EOF
# album_to_artist.tsv
# Format: <album_folder_name><TAB><artist_folder_name>
# Example:
# إصدار ذهب\tباسم الكربلائي
EOF
    msg "Created mapping file: $MAPPING_FILE"
  fi
}

# --- Interactive artist chooser ---
choose_artist() {
  local album="$1"
  msg ""
  msg "Album folder: [$album]"
  msg "Choose artist:"
  msg "  1) $ARTIST_1"
  msg "  2) $ARTIST_2"
  msg "  3) $ARTIST_3"
  msg "  s) skip"
  msg "  c) custom (type artist name)"
  printf "> " >&2
  read -r choice
  case "$choice" in
    1) printf '%s' "$ARTIST_1" ;;
    2) printf '%s' "$ARTIST_2" ;;
    3) printf '%s' "$ARTIST_3" ;;
    s|S) printf '' ;;
    c|C)
      msg "Type artist folder name (exact Arabic):"
      printf "> " >&2
      read -r custom
      printf '%s' "$custom"
      ;;
    *) msg "Invalid choice, skipping."; printf '' ;;
  esac
}

# --- Find candidate album folders at root (maxdepth 1) ---
find_albums() {
  # We avoid .covers and artist folders by only taking "إصدار *" (and variant) at root.
  find "$MUSIC_ROOT" -mindepth 1 -maxdepth 1 -type d \( -name "$ALBUM_GLOB_1" -o -name "$ALBUM_GLOB_2" \) -print0
}

main() {
  msg "Music root: $MUSIC_ROOT"
  msg "Mapping file: $MAPPING_FILE"
  msg "DRY_RUN: $DRY_RUN (set DRY_RUN=0 to actually move)"
  msg ""

  init_mapping_file
  load_mapping

  # Collect albums
  mapfile -d '' albums < <(find_albums)

  if [[ "${#albums[@]}" -eq 0 ]]; then
    msg "No top-level album folders matched (إصدار*). Nothing to do."
    exit 0
  fi

  # If mapping file is empty/unhelpful, we’ll ask interactively for missing entries.
  for album_path in "${albums[@]}"; do
    album_name="$(basename "$album_path")"

    # Determine artist: mapping file first
    artist="${MAP[$album_name]:-}"

    if [[ -z "${artist:-}" ]]; then
      artist="$(choose_artist "$album_name")"
      if [[ -n "$artist" ]]; then
        # Append to mapping file for next runs
        printf '%s\t%s\n' "$album_name" "$artist" >> "$MAPPING_FILE"
        MAP["$album_name"]="$artist"
        msg "Saved mapping: $album_name -> $artist"
      else
        msg "Skipped: $album_name"
        continue
      fi
    fi

    # Move into /music/<artist>/<album>
    dest_dir="${MUSIC_ROOT%/}/$artist"
    do_move "$album_path" "$dest_dir"
  done

  msg ""
  msg "Done."
  msg "If DRY_RUN=1, rerun with: DRY_RUN=0 $0 \"$MUSIC_ROOT\""
  msg "Mapping saved at: $MAPPING_FILE"
}

main "$@"

