import importlib.resources

import dirsize

# The public API. Add every exported name here as the library grows; this list is the
# contract and the test below fails if the module and this list disagree.
PUBLIC_API: list[str] = [
    "DirUsage",
    "ErrorKind",
    "FileUsage",
    "Measure",
    "OnError",
    "ScanError",
    "Usage",
    "dir_size",
    "file_count",
    "iter_dirs",
    "largest",
    "scan",
]


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(dirsize.__all__) == sorted(PUBLIC_API)


def test_every_exported_name_resolves() -> None:
    for name in dirsize.__all__:
        assert hasattr(dirsize, name)


def test_version_is_a_three_part_string() -> None:
    parts = dirsize.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("dirsize").joinpath("py.typed").is_file()


def test_results_are_frozen() -> None:
    usage = dirsize.Usage("p", 1, 2, 3, 4, 5)
    try:
        usage.files = 9  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("Usage must be immutable")
