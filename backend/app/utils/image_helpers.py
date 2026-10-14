import io
import uuid
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import numpy as np
from ..config import settings

def compute_dhash(image: Image.Image, hash_size: int = 8) -> str:
    """
    Computes difference hash (dHash) for an image.
    dHash is highly robust to scaling, slight rotations, compression, and brightness changes.
    """
    # Resize to (hash_size + 1, hash_size) in grayscale
    resized = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = np.array(resized)
    
    # Compare adjacent pixels
    diff = pixels[:, 1:] > pixels[:, :-1]
    
    # Convert binary array to hex string
    decimal_val = 0
    hex_str = []
    for index, val in enumerate(diff.flatten()):
        if val:
            decimal_val += 2 ** (index % 4)
        if (index % 4) == 3:
            hex_str.append(hex(decimal_val)[2:])
            decimal_val = 0
    return "".join(hex_str)

def hash_similarity(hash1: str, hash2: str) -> float:
    """
    Calculate similarity [0.0, 1.0] between two hex dHash strings based on Hamming distance.
    """
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 0.0
    
    hamming_dist = 0
    for c1, c2 in zip(hash1, hash2):
        val1 = int(c1, 16)
        val2 = int(c2, 16)
        hamming_dist += bin(val1 ^ val2).count("1")
    
    max_bits = len(hash1) * 4
    # Hamming distance 0 means 1.0 similarity, max_bits means 0.0
    similarity = 1.0 - (hamming_dist / max_bits)
    return round(max(0.0, min(1.0, similarity)), 4)

def compute_color_histogram(image: Image.Image, bins: int = 8) -> np.ndarray:
    """
    Compute normalized HSV color histogram.
    """
    hsv_image = image.convert("HSV")
    np_img = np.array(hsv_image)
    
    # 3D histogram in HSV color space
    hist, _ = np.histogramdd(
        np_img.reshape(-1, 3),
        bins=(bins, bins, bins),
        range=((0, 256), (0, 256), (0, 256))
    )
    hist = hist.astype(np.float32)
    norm = np.linalg.norm(hist)
    if norm > 0:
        hist /= norm
    return hist.flatten()

def color_similarity(hist1: np.ndarray, hist2: np.ndarray) -> float:
    """
    Compute cosine similarity between two normalized color histograms.
    """
    if hist1 is None or hist2 is None or len(hist1) != len(hist2):
        return 0.0
    dot = np.dot(hist1, hist2)
    return round(float(max(0.0, min(1.0, dot))), 4)

def save_uploaded_image(file_bytes: bytes, original_filename: str) -> Tuple[str, str]:
    """
    Saves an uploaded image with a unique filename, computes its dHash,
    and returns (relative_path, dhash_hex).
    """
    ext = Path(original_filename).suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
        ext = ".jpg"
    
    filename = f"{uuid.uuid4().hex}{ext}"
    target_path = settings.UPLOADS_DIR / filename
    
    image = Image.open(io.BytesIO(file_bytes))
    image = image.convert("RGB")
    
    # Normalize size (max 1200px) while maintaining aspect ratio
    image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    image.save(target_path, "JPEG", quality=88, optimize=True)
    
    dhash = compute_dhash(image)
    relative_path = f"/uploads/{filename}"
    return relative_path, dhash
