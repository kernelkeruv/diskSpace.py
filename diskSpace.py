#!/usr/bin/env python3
"""
DiskSpace: Cross‑platform Top‑N disk usage scanner.

New in this version:
- Input accepts "all" to scan every listed disk
- Ranges like "1-4" (also "1 - 4")
- Mixed forms like "1,3,5" and "1, 3, 5" (spaces tolerated)

Examples:
  python diskSpace.py
  python diskSpace.py --include-folders --export
  python diskSpace.py --top 50 --export --output-dir ~/Downloads
"""
import os
import sys
import csv
import heapq
import shutil
import argparse
import time
from datetime import datetime

IS_WINDOWS = os.name == "nt"
PSEUDO_FS_TYPES = {
    "autofs", "binfmt_misc", "bpf", "cgroup", "cgroup2", "configfs", "debugfs",
    "devpts", "devtmpfs", "fusectl", "hugetlbfs", "mqueue", "nsfs", "overlay",
    "proc", "pstore", "ramfs", "rpc_pipefs", "securityfs", "selinuxfs", "sysfs",
    "tmpfs", "tracefs",
}

# --------------------------- Formatting ---------------------------

def format_bytes(size: int) -> str:
    orig = float(size)
    for unit in ['B','KB','MB','GB','TB','PB']:
        if orig < 1024 or unit == 'PB':
            return f"{orig:.2f} {unit}" if unit != 'B' else f"{int(orig)} B"
        orig /= 1024

# --------------------------- Disk enumeration ---------------------------

def enumerate_disks():
    disks = []  # list of tuples: (name, path, total, free)
    if IS_WINDOWS:
        import string, ctypes
        GetLogicalDrives = ctypes.windll.kernel32.GetLogicalDrives
        GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW
        DRIVE_FIXED = 3
        bitmask = GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if bitmask & (1 << i):
                root = f"{letter}:\\"
                try:
                    if GetDriveTypeW(ctypes.c_wchar_p(root)) == DRIVE_FIXED:
                        total, used, free = shutil.disk_usage(root)
                        disks.append((f"{letter}:", root, total, free))
                except Exception:
                    continue
    else:
        mounts = []
        # Prefer /proc/mounts; fallback to df for macOS
        try:
            with open('/proc/mounts', 'r', errors='ignore') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3:
                        src, mnt, fstype = parts[0], parts[1], parts[2]
                        mounts.append((src, mnt, fstype))
        except Exception:
            # macOS / BSD fallback
            import subprocess
            try:
                out = subprocess.check_output(['df'], text=True, errors='ignore')
                for line in out.splitlines()[1:]:
                    cols = line.split()
                    if len(cols) >= 6:
                        mounts.append((cols[0], cols[-1], "unknown"))
            except Exception:
                mounts = [('/', '/', 'unknown')]
        # Filter likely real mounts
        seen_paths = set()
        seen_devices = set()
        for src, mnt, fstype in mounts:
            if not os.path.isdir(mnt):
                continue
            if fstype in PSEUDO_FS_TYPES:
                continue
            # Skip kernel pseudo mounts that can appear as binds on Linux.
            if any(mnt.startswith(p) for p in ('/proc','/sys','/dev','/run','/snap','/private/var')):
                continue
            if mnt in seen_paths:
                continue
            try:
                st = os.stat(mnt)
                total, used, free = shutil.disk_usage(mnt)
                if total <= 0:
                    continue
                # Avoid duplicate entries from bind/alias mounts of same device.
                dev_key = st.st_dev
                if dev_key in seen_devices:
                    continue
                seen_devices.add(dev_key)
                seen_paths.add(mnt)
                disks.append((mnt, mnt, total, free))
            except Exception:
                continue
    # Stable sort by name
    disks.sort(key=lambda t: t[0])
    return disks

# --------------------------- Scanning ---------------------------

def iter_files(root: str):
    try:
        root_dev = os.stat(root).st_dev
    except Exception:
        root_dev = None
    for dp, dn, fn in os.walk(root, topdown=True, onerror=lambda e: None):
        if root_dev is not None:
            same_fs_dirs = []
            for d in dn:
                sub = os.path.join(dp, d)
                try:
                    if os.lstat(sub).st_dev == root_dev:
                        same_fs_dirs.append(d)
                except Exception:
                    continue
            dn[:] = same_fs_dirs
        for f in fn:
            fp = os.path.join(dp, f)
            try:
                st = os.stat(fp, follow_symlinks=False)
                if root_dev is not None and st.st_dev != root_dev:
                    continue
                yield fp, st.st_size, st.st_mtime
            except Exception:
                continue

def top_files(root: str, n: int):
    heap = []  # (size, path, mtime)
    push = heapq.heappush
    replace = heapq.heapreplace
    for path, size, mtime in iter_files(root):
        if len(heap) < n:
            push(heap, (size, path, mtime))
        elif size > heap[0][0]:
            replace(heap, (size, path, mtime))
    heap.sort(reverse=True)
    return heap  # list[(size, path, mtime)] largest first

def folder_size(folder: str, root_dev: int = None) -> int:
    total = 0
    for dp, dn, fn in os.walk(folder, topdown=True, onerror=lambda e: None):
        if root_dev is not None:
            same_fs_dirs = []
            for d in dn:
                sub = os.path.join(dp, d)
                try:
                    if os.lstat(sub).st_dev == root_dev:
                        same_fs_dirs.append(d)
                except Exception:
                    continue
            dn[:] = same_fs_dirs
        for f in fn:
            try:
                fp = os.path.join(dp, f)
                st = os.stat(fp, follow_symlinks=False)
                if root_dev is not None and st.st_dev != root_dev:
                    continue
                total += st.st_size
            except Exception:
                continue
    return total

def top_folders(root: str, n: int):
    entries = []  # (size, path, mtime)
    try:
        root_dev = os.stat(root).st_dev
    except Exception:
        root_dev = None
    try:
        with os.scandir(root) as it:
            for e in it:
                if e.is_dir(follow_symlinks=False):
                    try:
                        est = e.stat(follow_symlinks=False)
                        if root_dev is not None and est.st_dev != root_dev:
                            continue
                        sz = folder_size(e.path, root_dev=root_dev)
                        mtime = e.stat(follow_symlinks=False).st_mtime
                        entries.append((sz, e.path, mtime))
                    except Exception:
                        continue
    except Exception:
        return []
    entries.sort(reverse=True)
    return entries[:n]

# --------------------------- CSV ---------------------------

def export_csv(rows, headers, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for rank, (size, p, m) in enumerate(rows, start=1):
            w.writerow([rank, size, format_bytes(size), p,
                        datetime.fromtimestamp(m).strftime('%Y-%m-%d %H:%M:%S')])

# --------------------------- Selection parsing ---------------------------

def parse_selection(s: str, max_idx: int):
    """Parse user input like:
       - "all"
       - "1-4" or "1 - 4"
       - "1,3,5" or with spaces "1, 3, 5"
       - Mixed: "1-3, 5, 7-8"
       Returns sorted unique list of indices within [1, max_idx].
    """
    if not s:
        return []
    s = s.strip().lower()
    if s == 'all':
        return list(range(1, max_idx + 1))

    # Normalize separators: treat semicolons and multiple spaces as commas
    norm = s.replace(';', ',')
    # Allow ranges with spaces around hyphen
    norm = norm.replace(' - ', '-')

    chosen = set()
    for token in [t.strip() for t in norm.split(',') if t.strip()]:
        if token == 'all':
            return list(range(1, max_idx + 1))
        if '-' in token:
            # Range like 1-4
            parts = [p.strip() for p in token.split('-') if p.strip()]
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                a, b = int(parts[0]), int(parts[1])
                if a > b:
                    a, b = b, a
                for i in range(a, b + 1):
                    if 1 <= i <= max_idx:
                        chosen.add(i)
                continue
        # Single number
        if token.isdigit():
            i = int(token)
            if 1 <= i <= max_idx:
                chosen.add(i)
    return sorted(chosen)

# --------------------------- Main ---------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="List Top-N largest files and optional folders on selected disks/mounts.")
    ap.add_argument('--top', type=int, default=20, help='number of items to show (default 20)')
    ap.add_argument('--include-folders', action='store_true', help='also compute Top-N folders by total size')
    ap.add_argument('--export', action='store_true', help='export CSVs to output directory')
    ap.add_argument('--output-dir', default=os.path.expanduser('~/Downloads'), help='where to write CSVs')
    args = ap.parse_args()

    disks = enumerate_disks()
    if not disks:
        print('No disks found.')
        return 1

    print('\n== Disks ==')
    print(f"{'Idx':>3}  {'Name':<20} {'Total':>12} {'Free':>12} {'Used':>12}")
    for idx, (name, path, total, free) in enumerate(disks, start=1):
        print(f"{idx:>3}  {name:<20} {format_bytes(total):>12} {format_bytes(free):>12} {format_bytes(total-free):>12}")

    prompt = "\nEnter disk numbers (e.g., 1,3,5), ranges (e.g., 1-4), or 'all': "
    selection_raw = input(prompt)
    indices = parse_selection(selection_raw, max_idx=len(disks))
    if not indices:
        print('No valid selections. Exiting.')
        return 1

    ts = time.strftime('%Y%m%d_%H%M%S')
    if args.export:
        os.makedirs(args.output_dir, exist_ok=True)

    for i in indices:
        name, path, total, free = disks[i - 1]
        print(f"\n=== {name} ({path}) ===")

        files = top_files(path, args.top)
        print(f"\n-- Top {args.top} Files --")
        if files:
            print(f"{'Rank':>4}  {'Size':>10}  {'Path'}")
            for rank, (size, p, m) in enumerate(files, start=1):
                print(f"{rank:>4}  {format_bytes(size):>10}  {p}")
            if args.export:
                fcsv = os.path.join(args.output_dir, f"Top{args.top}Files_{name.replace(':','')}_{ts}.csv")
                export_csv(files, ["Rank","SizeBytes","Size","Path","LastWrite"], fcsv)
                print(f"Exported: {fcsv}")
        else:
            print('No files found or access denied.')

        if args.include_folders:
            print(f"\n-- Top {args.top} Folders --")
            folders = top_folders(path, args.top)
            if folders:
                print(f"{'Rank':>4}  {'Size':>10}  {'Folder'}")
                for rank, (size, p, m) in enumerate(folders, start=1):
                    print(f"{rank:>4}  {format_bytes(size):>10}  {p}")
                if args.export:
                    fc2 = os.path.join(args.output_dir, f"Top{args.top}Folders_{name.replace(':','')}_{ts}.csv")
                    export_csv(folders, ["Rank","SizeBytes","Size","Folder","LastWrite"], fc2)
                    print(f"Exported: {fc2}")
            else:
                print('No folders found or access denied.')

    print('\nDone.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
