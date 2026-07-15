import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COSYVOICE_DIR = ROOT / "cosyvoice"
sys.path.insert(0, str(COSYVOICE_DIR))
sys.path.append(str(COSYVOICE_DIR / "third_party/Matcha-TTS"))

import torch
from cosyvoice.cli.cosyvoice import AutoModel
from tqdm import tqdm

from core.utils import load_json


DEFAULT_PROMPT_TEXT = "You are a helpful assistant.<|endofprompt|>"


def episode_output_name(episode: dict) -> str:
    return f"{episode['episode_id']}.mp3"


def ep_number(episode_id: str) -> int:
    match = re.search(r"\d+", episode_id)
    if not match:
        raise ValueError(f"Cannot parse episode number from: {episode_id}")
    return int(match.group())


def load_text_from_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def save_mp3(path: str, audio, sample_rate: int) -> None:
    import torchaudio
    torchaudio.save(path, audio, sample_rate)


def concatenate_with_silence(audio_list, sample_rate, silence_duration=0.2):
    if not audio_list:
        return None
    silence_samples = int(sample_rate * silence_duration)
    silence = torch.zeros((1, silence_samples), dtype=audio_list[0].dtype, device=audio_list[0].device)
    combined_audio = []
    for i, audio in enumerate(audio_list):
        combined_audio.append(audio)
        if i < len(audio_list) - 1:
            combined_audio.append(silence)
    return torch.cat(combined_audio, dim=1)


def synthesize_episode(cosyvoice, target_text: str, prompt_text: str, prompt_wav: str):
    audio_segments = []
    for result in cosyvoice.inference_zero_shot(
        target_text,
        prompt_text,
        prompt_wav,
        stream=False,
    ):
        audio_segments.append(result["tts_speech"])
    if not audio_segments:
        return None
    return concatenate_with_silence(audio_segments, cosyvoice.sample_rate)


def batch_synthesize(
    outline_path: str | Path,
    script_dir: str | Path,
    output_dir: str | Path,
    model_dir: str | Path,
    prompt_wav: str | Path,
    prompt_text: str = DEFAULT_PROMPT_TEXT,
    skip_until_ep: int = 0,
    stop_if_missing: bool = True,
) -> None:
    outline = load_json(outline_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if torch.cuda.is_available():
        print(f"CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        print("CUDA not available, using CPU")

    print(f"Loading model from {model_dir}...", flush=True)
    t0 = time.time()
    cosyvoice = AutoModel(model_dir=str(model_dir))
    print(f"Model loaded in {time.time() - t0:.1f}s", flush=True)

    episodes = outline["episodes"]
    for episode in tqdm(episodes, desc="TTS", unit="ep"):
        ep_id = episode["episode_id"]
        output_path = output_dir / episode_output_name(episode)
        script_path = Path(script_dir) / f"{ep_id}_final.txt"

        if ep_number(ep_id) < skip_until_ep:
            tqdm.write(f"Skip {ep_id}: ep < {skip_until_ep}")
            continue

        if output_path.exists():
            tqdm.write(f"Skip {ep_id}: output exists")
            continue

        if not script_path.exists():
            msg = f"Script not ready: {script_path}"
            if stop_if_missing:
                tqdm.write(f"{msg}, stopping batch")
                break
            tqdm.write(f"{msg}, skipping")
            continue

        tqdm.write(f"Generating {ep_id} -> {output_path.name}")
        target_text = load_text_from_file(str(script_path))
        tqdm.write(f"Loaded script ({len(target_text)} chars)")

        t1 = time.time()
        audio = synthesize_episode(
            cosyvoice,
            target_text,
            prompt_text,
            str(prompt_wav),
        )
        if audio is None:
            tqdm.write(f"Failed {ep_id}: no audio generated")
            continue

        save_mp3(str(output_path), audio, cosyvoice.sample_rate)
        tqdm.write(f"Done {ep_id} ({time.time() - t1:.1f}s): {output_path.name}")