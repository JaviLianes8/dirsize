# dirsize

Total size and file count of a directory tree as one typed call, with hardlink dedupe and safe symlink handling

## Install

```
pip install dirsize
```

## Usage

```python
from dirsize import dir_size, file_count

total_bytes = dir_size("my_project")
print(total_bytes)

count = file_count("my_project")
print(count)
```

Both functions take keyword options:

```python
# Follow symlinked directories (loops are detected and skipped).
dir_size("my_project", follow_symlinks=True)

# Skip unreadable entries instead of raising.
dir_size("/var/log", on_error="ignore")

# Or handle each error yourself.
def note(error: OSError) -> None:
    print("skipped:", error)

dir_size("/var/log", on_error=note)
```

`dir_size` returns the total in bytes. Hardlinked files are counted once, so the
number matches the space actually used. `file_count` returns the number of files,
one per directory entry. The default raises on the first unreadable path.

## Why

The standard library has no single call for the size of a directory tree. The
common recipe, summing `os.path.getsize` over `os.walk`, double counts hardlinked
files and can loop forever on a symlink cycle. `dirsize` is the `du -s` primitive
as one typed function: `os.scandir` for speed, `(st_dev, st_ino)` dedupe for
hardlinks, cycle detection when following symlinks, and a choice of raising,
ignoring or handling permission errors. No dependencies, `mypy --strict` clean.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
