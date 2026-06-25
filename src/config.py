from pathlib import Path


# Root of the project (two levels up from src/config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Object Detection (MM Grounding DINO) ──────────────────────────────
DETECTION = {
    # HuggingFace model ID for zero-shot detection
    "model_id": "openmmlab-community/mm_grounding_dino_tiny_o365v1_goldg_v3det",

    # Minimum confidence score [0-1] to keep a detection.
    # Lower = more detections but more false positives.
    "threshold": 0.3,

    # How many text labels to pass per inference call.
    # Smaller = less label-concatenation noise but more forward passes.
    # Larger = faster but may merge unrelated labels into one prompt.
    "batch_size": 20,
}

# ── Data paths ────────────────────────────────────────────────────────
DATA = {
    "image_dir": PROJECT_ROOT / "theker" / "Images",
    "output_dir": PROJECT_ROOT / "outputs",
}
