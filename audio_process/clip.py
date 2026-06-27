#!/usr/bin/env python3
from pathlib import Path

import librosa
import soundfile as sf

import numpy as np

def trim_edges(
    audio: np.ndarray,
    sr: int,
    *,
    top_db: float = 30,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> np.ndarray:
    """只去掉首尾静音，保留中间停顿"""
    trimmed, _ = librosa.effects.trim(
        audio,
        top_db=top_db,
        frame_length=frame_length,
        hop_length=hop_length,
    )
    return trimmed


def split_audio(
    input_path: str | Path,
    num_chunks: int,
    output_dir: str | Path | None = None,
    *,
    remove_blank: bool = True,
    top_db: float = 30,
) -> list[Path]:
    inp = Path(input_path)
    out_dir = Path(output_dir) if output_dir else inp.parent / f"{inp.stem}_chunks"
    out_dir.mkdir(parents=True, exist_ok=True)

    audio, sr = librosa.load(inp, sr=16000, mono=True)

    if remove_blank:
        audio = trim_edges(audio, sr, top_db=top_db)

    total_samples = len(audio)
    if total_samples == 0:
        raise ValueError("去空白后音频为空，请调低 top_db 或关闭 remove_blank")

    chunk_size = total_samples // num_chunks
    outputs: list[Path] = []
    for i in range(num_chunks):
        start = i * chunk_size
        end = total_samples if i == num_chunks - 1 else (i + 1) * chunk_size
        chunk_path = out_dir / f"{inp.stem}_chunk_{i:02d}.mp3"
        sf.write(str(chunk_path), audio[start:end], sr, format="MP3")
        outputs.append(chunk_path)
    return outputs


if __name__ == "__main__":
    # 直接改这里，不用 parser
    input_mp3 = "asset/zhongqing/pure_vocal/buzaichang_ep3_vocal.wav"
    num_chunks = 1

    paths = split_audio(input_mp3, num_chunks, remove_blank=True, top_db=40)
    total_sec = sum(
        len(librosa.load(p, sr=16000)) / 16000 for p in paths
    )
    print(f"输入: {input_mp3} | 分块数: {num_chunks}")
    for i, p in enumerate(paths):
        print(f"  [{i}] {p}")