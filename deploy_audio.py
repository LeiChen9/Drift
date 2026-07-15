"""
deploy_audio.py - 推音频到 R2 并更新 manifest

用法:
  python build_manifest.py <project>   # 先确保 manifest 是最新的
  python deploy_audio.py <project> [--dry-run]
"""

import sys
import json
import subprocess
import datetime
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def log(msg):
    print(f"[deploy_audio] {msg}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print("用法: python deploy_audio.py <project> [--dry-run]")
        sys.exit(1)

    project = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    output_dir = ROOT / 'asset' / 'output' / project
    manifest_path = ROOT / 'listen' / 'web' / 'data' / project / 'manifest.json'

    if not output_dir.is_dir():
        log(f"ERROR: 输出目录不存在: {output_dir}")
        sys.exit(1)
    if not manifest_path.is_file():
        log(f"ERROR: manifest 不存在，先运行 python build_manifest.py {project}")
        sys.exit(1)

    if not shutil.which('rclone'):
        log("ERROR: rclone not found in PATH")
        sys.exit(1)

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    episodes = manifest.get('episodes', [])
    unpublished = [ep for ep in episodes if not ep.get('published', False)]

    if not unpublished:
        log("All episodes already published, nothing to do.")
        sys.exit(0)

    log(f"Found {len(unpublished)} unpublished episode(s), processing...")

    for ep in unpublished:
        ep_id = ep['episode_id']
        audio_path = ep['audio_path']
        log(f"  [{ep_id}] processing...")

        source_file = output_dir / f"{ep_id}.mp3"
        if not source_file.is_file():
            log(f"  [{ep_id}] ERROR: source file not found: {source_file}")
            sys.exit(1)
        log(f"  [{ep_id}] source: {source_file.name}")

        try:
            from mutagen.mp3 import MP3
            audio = MP3(str(source_file))
            duration = round(audio.info.length)
        except Exception as e:
            log(f"  [{ep_id}] ERROR: failed to read duration: {e}")
            sys.exit(1)
        log(f"  [{ep_id}] duration: {duration}s")

        dest = f"r2:bonfire/{audio_path}"
        if dry_run:
            log(f"  [{ep_id}] [DRY-RUN] rclone copyto {source_file} {dest} --ignore-existing")
        else:
            log(f"  [{ep_id}] uploading to {dest} ...")
            result = subprocess.run(
                ['rclone', 'copyto', '--progress', '--ignore-existing', str(source_file), dest],
                capture_output=False
            )
            if result.returncode != 0:
                log(f"  [{ep_id}] ERROR: rclone upload failed (exit code {result.returncode})")
                sys.exit(1)
            log(f"  [{ep_id}] upload OK")

        ep['published'] = True
        ep['duration_sec'] = duration

    manifest['updated_at'] = datetime.date.today().isoformat()

    if dry_run:
        log("[DRY-RUN] manifest not written")
    else:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        log(f"manifest updated: {manifest_path}")

    log("Done.")


if __name__ == '__main__':
    main()
