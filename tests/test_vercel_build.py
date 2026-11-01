import tempfile
import unittest
from pathlib import Path

from vercel_build import build_public_assets


class VercelBuildTests(unittest.TestCase):
    def test_build_copies_public_assets_and_pwa_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            output = root / "public"
            (source / "css").mkdir(parents=True)
            (source / "css" / "app.css").write_text("body {}", encoding="utf-8")
            (source / "manifest.webmanifest").write_text("{}", encoding="utf-8")
            (source / "service-worker.js").write_text("self.addEventListener('fetch', () => {});", encoding="utf-8")

            build_public_assets(source, output)

            self.assertEqual((output / "static" / "css" / "app.css").read_text(encoding="utf-8"), "body {}")
            self.assertTrue((output / "manifest.webmanifest").is_file())
            self.assertTrue((output / "service-worker.js").is_file())


if __name__ == "__main__":
    unittest.main()
