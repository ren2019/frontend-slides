from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from base64 import b64encode
from hashlib import sha256
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "bundle-html.py"
SPEC = importlib.util.spec_from_file_location("bundle_html", SCRIPT)
assert SPEC and SPEC.loader
BUNDLE_HTML = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE_HTML)


class BundleHtmlTests(unittest.TestCase):
    def test_binary_asset_and_repeated_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"\x89PNG\r\n\x1a\nexample"
            (root / "image.png").write_bytes(payload)
            source = root / "source.html"
            source.write_text('<img src="image.png"><style>url(image.png)</style>', encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_sha256": sha256(source.read_bytes()).hexdigest(),
                        "entries": [
                            {
                                "reference": "image.png",
                                "path": "image.png",
                                "media_type": "image/png",
                                "expected_occurrences": 2,
                                "source_sha256": sha256(payload).hexdigest(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = BUNDLE_HTML.build(source, manifest).decode("utf-8")
            data_uri = f"data:image/png;base64,{b64encode(payload).decode('ascii')}"
            self.assertEqual(result.count(data_uri), 2)

    def test_nested_html_is_bundled_before_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frame.gif").write_bytes(b"GIF89a")
            (root / "panel.html").write_text('<img src="frame.gif">', encoding="utf-8")
            source = root / "source.html"
            source.write_text('<iframe src="panel.html"></iframe>', encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "entries": [
                            {
                                "reference": "panel.html",
                                "path": "panel.html",
                                "media_type": "text/html",
                                "expected_occurrences": 1,
                                "entries": [
                                    {
                                        "reference": "frame.gif",
                                        "path": "frame.gif",
                                        "media_type": "image/gif",
                                        "expected_occurrences": 1,
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = BUNDLE_HTML.build(source, manifest).decode("utf-8")
            nested = '<img src="data:image/gif;base64,R0lGODlh">'.encode("utf-8")
            expected = f'data:text/html;base64,{b64encode(nested).decode("ascii")}'
            self.assertIn(expected, result)

    def test_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "outside-bundle-html-test.png"
            outside.write_bytes(b"test")
            self.addCleanup(outside.unlink, missing_ok=True)
            source = root / "source.html"
            source.write_text("../outside-bundle-html-test.png", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "entries": [
                            {
                                "reference": "../outside-bundle-html-test.png",
                                "path": "../outside-bundle-html-test.png",
                                "media_type": "image/png",
                                "expected_occurrences": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(BUNDLE_HTML.BundleError, "escapes manifest directory"):
                BUNDLE_HTML.build(source, manifest)

    def test_cli_refuses_overwrite_and_check_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.html"
            source.write_text("<p>plain</p>", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text('{"schema_version":1,"entries":[]}', encoding="utf-8")
            output = root / "release.html"

            first = subprocess.run(
                [sys.executable, str(SCRIPT), str(source), str(manifest), str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            overwrite = subprocess.run(
                [sys.executable, str(SCRIPT), str(source), str(manifest), str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(overwrite.returncode, 0)
            output.write_text("drift", encoding="utf-8")
            check = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(source),
                    str(manifest),
                    str(output),
                    "--check",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(check.returncode, 0)
            self.assertIn("check failed", check.stderr)


if __name__ == "__main__":
    unittest.main()
