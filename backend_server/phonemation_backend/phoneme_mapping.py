"""Phoneme conversion utilities.

Converts the raw IPA token stream emitted by the phoneme ONNX model into
the higher-level phoneme sets that frontends (e.g. the Godot character
controller's mouth sprites) actually need. Two stages are supported:

1. IPA -> CMU_39, using ``json_files/ipa_cmu.json``.
2. CMU_39 -> a target set (default ``preston_blair``) using the
   ``cmu_39_phoneme_conversion`` table inside ``phonemes/<target>.json``.

The ``preston_blair`` target matches the standard PNGTuber mouth sprite
names: ``AI``, ``E``, ``FV``, ``L``, ``MBP``, ``O``, ``U``, ``WQ``,
``etc``, ``rest``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional

_SPECIAL_TOKENS = {"", "[PAD]", "[UNK]", "[CLS]", "[SEP]", "<pad>", "<unk>", "<s>", "</s>"}

_PACKAGE_ROOT = Path(__file__).resolve().parent
_IPA_CMU_PATH = _PACKAGE_ROOT / "json_files" / "ipa_cmu.json"
_PHONEMES_DIR = _PACKAGE_ROOT / "phonemes"


def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning("Phoneme mapping file not found: %s", path)
        return {}
    except Exception as exc:  # pragma: no cover - defensive
        logging.error("Failed to load phoneme mapping %s: %s", path, exc)
        return {}


class PhonemeMapper:
    """Lightweight, dependency-free IPA -> CMU -> viseme converter."""

    def __init__(self, target_set: str = "preston_blair") -> None:
        self.target_set = target_set
        self.ipa_to_cmu: Dict[str, str] = _load_json(_IPA_CMU_PATH)
        target_data = _load_json(_PHONEMES_DIR / f"{target_set}.json")
        self.cmu_to_viseme: Dict[str, str] = target_data.get("cmu_39_phoneme_conversion", {})
        self.viseme_set: List[str] = list(target_data.get("phoneme_set", []))

    def ipa_to_cmu_token(self, token: str) -> Optional[str]:
        if token is None:
            return None
        if token in _SPECIAL_TOKENS:
            return None
        stripped = token.strip()
        if not stripped:
            return None
        # Direct lookup first; fall back to the stripped version. If the model
        # already emits a CMU label, accept it as-is (it will be uppercased so
        # downstream lookups still work).
        cmu = self.ipa_to_cmu.get(token) or self.ipa_to_cmu.get(stripped)
        if cmu:
            return cmu
        if stripped.upper() in self.cmu_to_viseme or stripped.upper() == "REST":
            return stripped.upper()
        # Unknown token; treat as silence so the mouth closes instead of
        # flickering on an unmapped sprite.
        return "rest"

    def cmu_to_viseme_token(self, cmu_token: Optional[str]) -> Optional[str]:
        if not cmu_token:
            return None
        if cmu_token == "rest":
            return "rest"
        return self.cmu_to_viseme.get(cmu_token, "rest")

    def convert_phoneme(self, token: str) -> Optional[str]:
        return self.cmu_to_viseme_token(self.ipa_to_cmu_token(token))

    def convert_phonemes(self, tokens: Iterable[str]) -> List[str]:
        out: List[str] = []
        for token in tokens or []:
            cmu = self.ipa_to_cmu_token(token)
            if cmu is None:
                continue
            out.append(cmu)
        return out

    def convert_visemes(self, tokens: Iterable[str]) -> List[str]:
        out: List[str] = []
        for token in tokens or []:
            viseme = self.convert_phoneme(token)
            if viseme is None:
                continue
            out.append(viseme)
        return out
