# diskSpace.py

A cross-platform Python 3 script to list the **largest files and folders** on one or more disks or mounted volumes. Works on Windows, macOS, and Linux without requiring any external dependencies.

---

## Features

* Automatically detects all fixed drives (Windows) or mounts (Linux/macOS)
* Interactive drive selection (comma-separated input like `1,3,4`)
* Lists the **Top-N largest files** (default 20)
* Optional: compute **Top-N largest folders** by cumulative size
* Optional: export results as CSV files in `~/Downloads`
* Uses only Python built-in modules (`os`, `csv`, `heapq`, `shutil`, etc.)
* Runs anywhere Python 3.8+ is available
* On Linux, ignores pseudo/virtual mounts and scans each selected mount without crossing into other filesystems

---

## Usage

### 1. Run the script

Open a terminal or PowerShell window in the directory containing `diskSpace.py`, then run:

```bash
python diskSpace.py
```

### 2. Interactive workflow

Example session:

```
== Disks ==
1. C:              total=476.94 GB   free=220.15 GB
2. D:              total=931.51 GB   free=515.23 GB

Enter disk numbers (comma-separated): 1,2

=== C: (C:\) ===
-- Top 20 Files --
  1.  42.33 GB  C:\VMs\Ubuntu.vhdx
  2.  18.70 GB  C:\Users\Public\Videos\OBS_Recording.mkv
...
```

---

## Parameters

| Option              | Description                            | Default       |
| ------------------- | -------------------------------------- | ------------- |
| `--top`             | Number of top items to list            | 20            |
| `--include-folders` | Also compute Top-N largest folders     | Off           |
| `--export`          | Export CSV reports to output directory | Off           |
| `--output-dir`      | Path to save CSV reports               | `~/Downloads` |

---

## Examples

### Default (interactive)

```bash
python diskSpace.py
```

### Include largest folders

```bash
python diskSpace.py --include-folders
```

### Export results to CSVs

```bash
python diskSpace.py --export
```

### Top 50 files and folders, export to a custom directory

```bash
python diskSpace.py --top 50 --include-folders --export --output-dir "T:/Reports"
```

---

## Output

### Console

```
-- Top 20 Files --
  1.  42.33 GB  C:\VMs\Ubuntu.vhdx
  2.  18.70 GB  C:\Users\Public\Videos\OBS_Recording.mkv
```

### CSV Exports (if `--export`)

```
C:\Users\<username>\Downloads\Top20Files_C_20251103_1930.csv
C:\Users\<username>\Downloads\Top20Folders_D_20251103_1930.csv
```

---

## Requirements

* Python 3.8 or newer
* No external dependencies
* Works on Windows, macOS, and Linux

---

## Notes

* Folder scanning is recursive and can take longer for large directories.
* CSVs are UTF-8 encoded for compatibility with Excel and LibreOffice.
* Tested on Windows 11, macOS Sequoia 15.x, and Debian 12.

---

## License

MIT License — free for personal and commercial use.

---

## Author

Grant Scott Turner
[https://gtai.dev](https://gtai.dev)
Engineering and Cybersecurity Student | Domain Admin | Blue/Purple Team Developer
