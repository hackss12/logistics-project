from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent


def build_public_assets(source: Path = ROOT / "static", output: Path = ROOT / "public") -> None:
    shutil.copytree(source, output / "static", dirs_exist_ok=True)
    shutil.copy2(source / "manifest.webmanifest", output / "manifest.webmanifest")
    shutil.copy2(source / "service-worker.js", output / "service-worker.js")


if __name__ == "__main__":
    build_public_assets()
