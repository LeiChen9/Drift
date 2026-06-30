"""Batch TTS: generate episode mp3 files sequentially from outline.json."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
COSYVOICE_DIR = ROOT / "cosyvoice"
sys.path.insert(0, str(COSYVOICE_DIR))
sys.path.append(str(COSYVOICE_DIR / "third_party/Matcha-TTS"))

import torch
from cosyvoice.cli.cosyvoice import AutoModel
from engine import DEFAULT_PROMPT_TEXT, load_text_from_file, save_mp3, synthesize_episode

from utils import load_json

# === Config ===
ASSET_DIR = ROOT / "asset/national_org"
OUTLINE_PATH = ASSET_DIR / "outline.json"
SCRIPT_DIR = ASSET_DIR / "episodes"
OUTPUT_DIR = ROOT / "output/national_org"

MODEL_DIR = COSYVOICE_DIR / "pretrained_models/Fun-CosyVoice3-0.5B"
PROMPT_WAV = ROOT / "asset/curr/bon_clean_clip.wav"
PROMPT_TEXT = DEFAULT_PROMPT_TEXT

SKIP_UNTIL_EP = 5
STOP_IF_SCRIPT_MISSING = True


def sanitize_filename(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|：？?]', '', text).strip()


def episode_output_name(episode: dict) -> str:
    ep_id = episode["episode_id"]
    title = sanitize_filename(episode["title"])
    question = sanitize_filename(episode["central_question"].rstrip("？?"))
    return f"{ep_id}_{title}_{question}.mp3"


def ep_number(episode_id: str) -> int:
    match = re.search(r"\d+", episode_id)
    if not match:
        raise ValueError(f"Cannot parse episode number from: {episode_id}")
    return int(match.group())


def skip_reason(episode: dict, output_path: Path) -> str | None:
    if ep_number(episode["episode_id"]) < SKIP_UNTIL_EP:
        return f"episode < EP{SKIP_UNTIL_EP:02d}"
    if output_path.exists():
        return "output already exists"
    return None


def main():
    outline = load_json(OUTLINE_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if torch.cuda.is_available():
        print(f"CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        print("CUDA not available, using CPU")

    print(f"Loading model from {MODEL_DIR}...")
    cosyvoice = AutoModel(model_dir=str(MODEL_DIR))

    for episode in outline["episodes"]:
        ep_id = episode["episode_id"]
        output_path = OUTPUT_DIR / episode_output_name(episode)
        script_path = SCRIPT_DIR / f"{ep_id}_script_final.txt"

        reason = skip_reason(episode, output_path)
        if reason:
            print(f"Skip {ep_id}: {reason}")
            continue

        if not script_path.exists():
            msg = f"Script not ready: {script_path}"
            if STOP_IF_SCRIPT_MISSING:
                print(f"{msg}, stopping batch")
                break
            print(f"{msg}, skipping")
            continue

        print(f"Generating {ep_id} -> {output_path.name}")
        target_text = load_text_from_file(str(script_path))
        print(f"Loaded script ({len(target_text)} chars) from {script_path}")

        audio = synthesize_episode(
            cosyvoice,
            target_text,
            PROMPT_TEXT,
            str(PROMPT_WAV),
        )
        if audio is None:
            print(f"Failed {ep_id}: no audio generated")
            continue

        save_mp3(str(output_path), audio, cosyvoice.sample_rate)
        print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
