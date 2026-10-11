# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

- First release.
- `dir_size`: total size in bytes of a directory tree, with hardlink dedupe.
- `file_count`: number of files in a directory tree.
- `follow_symlinks` option with loop detection, and `on_error` raise, ignore or callback.
