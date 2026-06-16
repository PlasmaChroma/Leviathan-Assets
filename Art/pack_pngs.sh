#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="${1:-.}"

QUALITY="${QUALITY:-90-100}"
COLORS="${COLORS:-256}"
SPEED="${SPEED:-8}"
OPTI_LEVEL="${OPTI_LEVEL:-2}"
JOBS="${JOBS:-$(nproc)}"

# 0 = use existing *-fs8.png as candidate if present
# 1 = regenerate indexed candidates with pngquant
FORCE_QUANT="${FORCE_QUANT:-0}"

# 0 = choose smaller of lossless/indexed
# 1 = prefer indexed if available, even if slightly larger
PREFER_INDEXED="${PREFER_INDEXED:-0}"

# 1 = delete sidecar *-fs8.png files after successful replacement
DELETE_FS8="${DELETE_FS8:-0}"

BACKUP_DIR="${BACKUP_DIR:-_png_backup_originals}"
WORK_DIR="${WORK_DIR:-_png_work}"
REPORT="${REPORT:-_png_optimization_report.tsv}"

command -v optipng >/dev/null || {
  echo "Missing optipng. Install with: sudo apt install optipng"
  exit 1
}

command -v pngquant >/dev/null || {
  echo "Missing pngquant. Install with: sudo apt install pngquant"
  exit 1
}

mkdir -p "$BACKUP_DIR" "$WORK_DIR/logs" "$WORK_DIR/report_rows"

process_one() {
  src="$1"

  filename="$(basename "$src")"
  stem="${filename%.png}"
  dir="$(dirname "$src")"

  existing_fs8="$dir/${stem}-fs8.png"

  safe_name="$(printf '%s' "$filename" | sed 's/[^A-Za-z0-9._-]/_/g')"
  job_dir="$WORK_DIR/$safe_name.$$"

  mkdir -p "$job_dir"

  lossless_out="$job_dir/lossless.png"
  indexed_out="$job_dir/indexed.png"
  chosen_out="$job_dir/chosen.png"
  log="$WORK_DIR/logs/$safe_name.log"
  row="$WORK_DIR/report_rows/$safe_name.tsv"

  original_size="$(stat -c '%s' "$src")"

  {
    echo "==> $filename"

    # Backup original once.
    if [[ ! -f "$BACKUP_DIR/$filename" ]]; then
      cp -p -- "$src" "$BACKUP_DIR/$filename"
    fi

    # Candidate 1: lossless optimized original.
    cp -f -- "$src" "$lossless_out"
    optipng -quiet -o"$OPTI_LEVEL" -strip all "$lossless_out" || true
    lossless_size="$(stat -c '%s' "$lossless_out")"

    # Candidate 2: indexed/palette.
    indexed_ok=0
    indexed_size="NA"

    if [[ "$FORCE_QUANT" == "0" && -f "$existing_fs8" ]]; then
      echo "    using existing indexed candidate: $(basename "$existing_fs8")"
      cp -f -- "$existing_fs8" "$indexed_out"
      indexed_ok=1
    else
      echo "    generating indexed candidate"
      if pngquant "$COLORS" \
        --quality="$QUALITY" \
        --speed "$SPEED" \
        --strip \
        --force \
        --output "$indexed_out" \
        -- "$src"; then
        indexed_ok=1
      else
        indexed_ok=0
      fi
    fi

    if [[ "$indexed_ok" == "1" && -s "$indexed_out" ]]; then
      optipng -quiet -o"$OPTI_LEVEL" -strip all "$indexed_out" || true
      indexed_size="$(stat -c '%s' "$indexed_out")"
    else
      rm -f -- "$indexed_out"
    fi

    # Choose final candidate.
    chosen="lossless"
    chosen_path="$lossless_out"

    if [[ "$indexed_ok" == "1" && -s "$indexed_out" ]]; then
      if [[ "$PREFER_INDEXED" == "1" ]] || (( indexed_size < lossless_size )); then
        chosen="indexed"
        chosen_path="$indexed_out"
      fi
    fi

    cp -f -- "$chosen_path" "$chosen_out"
    chosen_size="$(stat -c '%s' "$chosen_out")"
    saved="$(( original_size - chosen_size ))"

    # Replace original filename atomically-ish.
    tmp_replace="${src}.tmp-optimized-$$"
    cp -f -- "$chosen_out" "$tmp_replace"
    mv -f -- "$tmp_replace" "$src"

    if [[ "$DELETE_FS8" == "1" && -f "$existing_fs8" ]]; then
      rm -f -- "$existing_fs8"
    fi

    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "$filename" \
      "$original_size" \
      "$lossless_size" \
      "$indexed_size" \
      "$chosen" \
      "$chosen_size" \
      "$saved" > "$row"

    echo "    original: $original_size bytes"
    echo "    lossless: $lossless_size bytes"
    echo "    indexed:  $indexed_size bytes"
    echo "    chosen:   $chosen → $chosen_size bytes"
    echo "    replaced: $src"
  } > "$log" 2>&1

  rm -rf -- "$job_dir"
}

export -f process_one
export QUALITY COLORS SPEED OPTI_LEVEL FORCE_QUANT PREFER_INDEXED DELETE_FS8
export BACKUP_DIR WORK_DIR

find "$SRC_DIR" \
  -maxdepth 1 \
  -type f \
  -iname "*.png" \
  ! -iname "*-fs8.png" \
  -print0 |
  xargs -0 -n 1 -P "$JOBS" bash -c 'process_one "$0"'

{
  printf "source\toriginal_bytes\tlossless_bytes\tindexed_bytes\tchosen\tchosen_bytes\tsaved_vs_original\n"
  cat "$WORK_DIR"/report_rows/*.tsv 2>/dev/null || true
} > "$REPORT"

echo
echo "Done."
echo "Originals backed up in: $BACKUP_DIR"
echo "Report written to:       $REPORT"
echo

column -t -s $'\t' "$REPORT" | sort -k7 -nr | head -30