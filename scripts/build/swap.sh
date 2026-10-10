#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh" "$@"
dir="$base/swap"
file="$dir/swapfile"
mode=${mode:-status}
active() { swapon --noheadings --raw --show=NAME | grep -Fxq -- "$file"; }
case "$mode" in status) swapon --show; exit 0;; enable|remove) ;; *) exit 2;; esac
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
mkdir -p "$base"
exec 9>"$base/swap.lock"
flock -n 9
exec 8>"$base/build.lock"
flock -n 8 || { echo 'Stop the protected build first.'; exit 1; }
if [[ "$mode" == enable ]]; then
  [[ $(findmnt -no FSTYPE -T "$base") == btrfs ]]
  if active; then echo 'Already active.'; exit 0; fi
  if [[ ! -e "$dir" ]]; then
    available=$(df -B1 --output=avail "$base" | tail -1)
    (( available > 164 * 1024 * 1024 * 1024 ))
    btrfs subvolume create "$dir"
    chmod 700 "$dir"
  fi
  btrfs subvolume show "$dir" >/dev/null
  if [[ ! -e "$file" ]]; then btrfs filesystem mkswapfile --size 64G "$file"; fi
  [[ ! -L "$file" && $(stat -c %s "$file") -eq 68719476736 ]]
  chmod 600 "$file"
  btrfs inspect-internal map-swapfile "$file"
  swapon --priority 10 "$file"
  swapon --show
else
  if active; then
    used=$(swapon --bytes --noheadings --raw --show=NAME,USED | awk -v target="$file" '$1==target {print $2}')
    available=$(awk '/^MemAvailable:/ {print $2*1024}' /proc/meminfo)
    python3 -c 'import sys; sys.exit(0 if float(sys.argv[1])>int(sys.argv[2])+2*1024**3 else 1)' "$available" "$used" || {
      echo 'Insufficient RAM for safe swapoff. Reboot first, then rerun remove.'; exit 1;
    }
    swapoff "$file"
  fi
  if [[ -e "$dir" ]]; then
    btrfs subvolume show "$dir" >/dev/null
    [[ ! -L "$file" ]]
    if [[ -f "$file" ]]; then rm -- "$file"; fi
    btrfs subvolume delete "$dir"
  fi
  echo 'SSD swap removed; zram unchanged.'
fi
