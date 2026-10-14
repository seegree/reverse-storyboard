"""Replaceable captioner using a pinned llama.cpp CLI, with no Python ML framework."""

from dataclasses import dataclass
import math
from pathlib import Path
import re
import time

from .config import executable, runtime_root
from .errors import AppError
from .process import check_cancel, run_process

PROMPT = (
    "Describe the visible subjects and setting in one short, factual sentence. "
    "Use present tense. Do not speculate. Output only the caption."
)
RETRY_PROMPT = "Describe what is visible in this image in one simple sentence. Output only that sentence."


def clean_caption(raw: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", raw).strip().strip('"` ')
    text = re.sub(r"^(?:caption|assistant|description)\s*:\s*", "", text, flags=re.I)
    text = re.sub(r"^\s*(?:\d+[.)]|[-*])\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:this|the) (?:image|picture|photo) (?:shows|depicts)\s+", "", text, flags=re.I)
    # Keep the first sentence, but never mechanically cut off a sentence at word 20.
    first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip('" ')
    words = first.split()
    if (not 4 <= len(words) <= 35 or not re.search(r"[A-Za-z]", first)
            or re.search(r"<\|?|\|>|https?://|\b(?:sorry|cannot|can't|unable|as an ai)\b", first, re.I)
            or re.search(r"\b(\w+)(?:\s+\1){2}\b", first, re.I)):
        raise ValueError("The model did not return a usable short caption.")
    return first[0].upper() + first[1:].rstrip(".!? ") + "."


@dataclass(frozen=True)
class Caption:
    text: str
    raw: str
    seconds: float
    attempts: int


class LlamaCaptioner:
    def __init__(self, *, model: Path | None = None, mmproj: Path | None = None,
                 binary: str | None = None, threads=4, temperature=0.0, timeout=120):
        if (model is None) != (mmproj is None):
            raise AppError("Supply both --model and its matching --mmproj, or neither.")
        root = runtime_root()
        self.model = (model or root / "models" / "SmolVLM-256M-Instruct-Q8_0.gguf").resolve()
        self.mmproj = (mmproj or root / "models" / "mmproj-SmolVLM-256M-Instruct-Q8_0.gguf").resolve()
        self.binary = binary or executable("llama-mtmd-cli", root)
        for path in (self.model, self.mmproj):
            if not path.is_file():
                raise AppError(f"Missing model file: {path}. Run scripts/fetch_runtime.py before analysis.")
            with path.open("rb") as file:
                if file.read(4) != b"GGUF":
                    raise AppError(f"Not a GGUF model file: {path}")
        if (threads < 1 or not math.isfinite(temperature) or not 0 <= temperature <= 2
                or not math.isfinite(timeout) or timeout <= 0):
            raise AppError("Threads and timeout must be positive; temperature must be between 0 and 2.")
        self.threads, self.temperature, self.timeout = threads, temperature, timeout

    def caption(self, image: Path, *, cancel=None) -> Caption:
        if not image.is_file():
            raise AppError(f"Caption image does not exist: {image}")
        start = time.perf_counter()
        last = ""
        for attempt, prompt in enumerate((PROMPT, RETRY_PROMPT), 1):
            check_cancel(cancel)
            raw = run_process([
                self.binary, "--model", str(self.model), "--mmproj", str(self.mmproj),
                "--image", str(image.resolve()), "--prompt", prompt,
                "--device", "none", "--gpu-layers", "0", "--no-mmproj-offload", "--offline",
                "--ctx-size", "2048", "--threads", str(self.threads),
                "--temp", str(self.temperature), "--seed", "42", "--n-predict", "64",
                "--log-colors", "off",
            ], cancel=cancel, timeout=self.timeout)
            try:
                text = clean_caption(raw)
                return Caption(text, raw.strip(), time.perf_counter() - start, attempt)
            except ValueError as exc:
                last = str(exc)
        raise AppError(f"Captioning failed for {image.name} after two attempts. {last}")
