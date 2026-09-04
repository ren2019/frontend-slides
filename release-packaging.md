# Release packaging

Frontend Slides distinguishes three artifacts:

- **Source**: editable HTML and local assets. It may contain relative file
  references.
- **Workspace preview**: the source opened locally for design and browser QA.
- **Release**: one fully embedded HTML file. Speaker notes may accompany it as
  a separate delivery file.

Use `scripts/bundle-html.py` when a deck cannot be authored safely as one file.
The script is deliberately manifest-driven: it never crawls a directory or
guesses which resources should be embedded.

## Manifest

Paths are relative to the manifest directory and must remain inside it after
symlinks are resolved.

```json
{
  "schema_version": 1,
  "source_sha256": "optional sha256 of source html",
  "entries": [
    {
      "reference": "assets/logo.png",
      "path": "assets/logo.png",
      "media_type": "image/png",
      "expected_occurrences": 1,
      "source_sha256": "optional sha256 of the asset"
    }
  ]
}
```

`reference` is an exact string replacement, so it works in HTML attributes,
CSS, and JavaScript string literals. Entries are processed in manifest order.
For a local HTML asset, set `media_type` to `text/html` (or an exact safe value
such as `text/html;charset=utf-8`) and add its own `entries` array; the nested
document is bundled before it is embedded.

## Commands

Create a new release file (existing outputs are never overwritten):

```bash
python3 scripts/bundle-html.py source.html bundle-manifest.json release.html
```

Verify that a checked-in or delivered release is byte-identical to a fresh
bundle:

```bash
python3 scripts/bundle-html.py source.html bundle-manifest.json release.html --check
```

Keep one manifest per source/release pair. Pin hashes and exact occurrence
counts for release work. A temporary adapter may generate a manifest for an
unusual legacy deck, but the stable bundling step should still use this script.
