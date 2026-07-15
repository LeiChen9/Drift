"""
build_manifest.py - 从 outline + 音频文件生成 manifest

用法: python build_manifest.py <project>
"""

import sys
import json
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def log(msg):
    print(f"[build_manifest] {msg}")


def get_duration(audio_path: Path) -> int | None:
    if not audio_path.is_file():
        return None
    try:
        from mutagen.mp3 import MP3
        audio = MP3(str(audio_path))
        return round(audio.info.length)
    except Exception:
        return None


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print("用法: python build_manifest.py <project>")
        sys.exit(1)

    project = sys.argv[1]

    outline_path = ROOT / 'asset' / 'outline' / f'{project}.json'
    output_dir = ROOT / 'asset' / 'output' / project
    manifest_path = ROOT / 'listen' / 'web' / 'data' / project / 'manifest.json'

    if not outline_path.is_file():
        log(f"ERROR: outline 不存在: {outline_path}")
        sys.exit(1)

    with open(outline_path, 'r', encoding='utf-8') as f:
        outline = json.load(f)

    existing = {}
    if manifest_path.is_file():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        for ep in existing_data.get('episodes', []):
            existing[ep['episode_id']] = ep.get('published', False)

    episodes = []
    for ep in outline['episodes']:
        ep_id = ep['episode_id']
        audio_file = output_dir / f"{ep_id}.mp3"
        duration = get_duration(audio_file)

        entry = {
            "episode_id": ep_id,
            "title": ep["title"],
            "central_question": ep.get("central_question"),
            "duration_sec": duration,
            "audio_path": f"{project}/{ep_id}.mp3",
            "published": existing.get(ep_id, False),
            "key_concepts": ep.get("key_concepts", []),
            "reasoning_summary": ep.get("reasoning_summary"),
        }
        episodes.append(entry)

    manifest = {
        "series_id": project,
        "book_title": outline["book_title"],
        "updated_at": datetime.date.today().isoformat(),
        "episodes": episodes,
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    published_count = sum(1 for ep in episodes if ep['published'])
    log(f"manifest 已生成: {manifest_path}")
    log(f"  episodes: {len(episodes)}, published: {published_count}")


if __name__ == '__main__':
    main()
