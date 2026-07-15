#!/usr/bin/env python3
"""
OCR module for Vision/UI Reading capability.

Primary: Apple Vision framework directly via pyobjc (macOS-native, no subprocess).
Fallback: tesseract-ocr via subprocess (requires `brew install tesseract`).

Usage:
    from virtual_hid.ocr import ocr_image
    results = ocr_image(screenshot)  # Returns list of text regions with bounding boxes
"""

import logging
import objc
import os
import subprocess
import tempfile
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def _vision_ocr(image_path: str) -> Optional[str]:
    """Run Vision framework OCR directly via pyobjc (no subprocess).

    Uses ``NSData.dataWithContentsOfFile_`` → ``NSBitmapImageRep`` → CGImageRef
    to load the image, then runs ``VNRecognizeTextRequest`` on a
    ``VNImageRequestHandler`` and extracts per-observation top candidates.

    Returns raw newline-delimited text (one region per line), or None on any
    failure so callers can try a fallback.
    """
    try:
        from AppKit import NSData, NSBitmapImageRep  # noqa: F401 — imported for side-effect availability
        from Foundation import NSArray
        from Vision import VNRecognizeTextRequest, VNImageRequestHandler, VNRequestTextRecognitionLevelAccurate

        # Load image bytes and create CGImageRef.
        data = NSData.dataWithContentsOfFile_(image_path)
        if data is None:
            logger.debug("[ocr] NSData could not read %s", image_path)
            return None

        rep = NSBitmapImageRep.alloc().initWithData_(data)
        if rep is None:
            logger.debug("[ocr] NSBitmapImageRep initWithData_ failed for %s", image_path)
            return None

        cg_image = rep.CGImage()
        if cg_image is None:
            logger.debug("[ocr] CGImage extraction failed for %s", image_path)
            return None

        # Configure text recognition request.
        request = VNRecognizeTextRequest.new()
        request.setRecognitionLevel_(VNRequestTextRecognitionLevelAccurate)

        # Create handler and run recognition.
        handler = VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
        if handler is None:
            logger.debug("[ocr] VNImageRequestHandler creation failed for %s", image_path)
            return None

        arr = NSArray.arrayWithObject_(request)
        ok, err_out = handler.performRequests_error_(arr, objc.NULL)

        if not ok and err_out is not None:
            desc = getattr(err_out, "description", lambda: str(err_out))() or "unknown error"
            logger.debug("[ocr] Vision performRequests failed: %s", desc)
            return None

        # Extract recognized text from results.
        results = request.results()
        lines = []
        for obs in results:
            top_cands = obs.topCandidates_(1)
            if len(top_cands) > 0:
                lines.append(top_cands[0].string())
            else:
                lines.append(obs.string())

        return "\n".join(lines)

    except ImportError as exc:
        logger.debug("[ocr] pyobjc Vision framework unavailable: %s", exc)
        return None
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("[ocr] Vision OCR unexpected error: %s", exc)
        return None


def _tesseract_ocr(image_path: str) -> Optional[str]:
    """Try to OCR using tesseract if installed."""
    try:
        result = subprocess.run(
            ['tesseract', image_path, '-', '--psm', '6'],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def ocr_image(image) -> List[Dict[str, Any]]:
    """Extract text regions from an image using Apple Vision framework.

    Tries three paths in order:
      1. Apple Vision framework directly via pyobjc (``_vision_ocr``).
      2. tesseract-ocr subprocess fallback (``_tesseract_ocr``) if ``brew install
         tesseract`` is available on the system.
      3. Empty list with a warning log when both fail.

    Args:
        image: PIL Image to OCR.

    Returns:
        List of dicts with 'text', 'confidence', 'bbox' (tuple of x,y,w,h).
    """
    try:
        from PIL import Image as _PILImage
    except ImportError:
        logger.error(
            "[ocr] PIL (Pillow) is required but not installed. "
            "Install with `pip install -r requirements.txt`."
        )
        return []

    if not isinstance(image, _PILImage.Image):
        logger.warning("[ocr] input is not a PIL Image")
        return []

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image.save(tmp.name, "PNG")
            tmp_path = tmp.name

        # Path 1: Apple Vision framework.
        text = _vision_ocr(tmp_path)

        if not text or len(text.strip()) == 0:
            logger.debug("[ocr] Vision OCR returned empty; trying tesseract fallback.")
            text = _tesseract_ocr(tmp_path)

        if not text or len(text.strip()) == 0:
            logger.warning(
                "[ocr] All OCR paths exhausted (Vision + tesseract). "
                "Install tesseract via `brew install tesseract` for a secondary fallback."
            )
            return []

        # Split into lines and create regions.
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        w, h = image.size

        return [{"text": line, "confidence": 0.9, "bbox": (0, 0, w, h)} for line in lines]

    except Exception as e:
        logger.exception("[ocr] unexpected error during OCR")
        return []
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:  # pragma: no cover
                pass


def ocr_text_from_region(image, x: int, y: int, width: int, height: int) -> str:
    """Extract text from a specific region of an image.

    Args:
        image: Full PIL Image.
        x, y: Top-left corner of region.
        width, height: Region dimensions.

    Returns:
        Extracted text as string.
    """
    cropped = image.crop((x, y, min(x + width, image.width), y + height))
    results = ocr_image(cropped)
    return " ".join(r["text"] for r in results if r.get("text"))


def bpe_tokenize(text: str, max_tokens: int = 50) -> List[str]:
    """Tokenize text using Byte Pair Encoding (BPE).

    Splits text into subword units for more efficient processing.
    Returns list of tokens up to ``max_tokens`` length.
    """
    if not text:
        return []

    # Learn BPE merges from the input text.
    words = text.split()
    word_counts = {}
    for w in words:
        word_counts[w] = word_counts.get(w, 0) + 1

    end_marker = "</w>"
    tokens: List[str] = []

    # Count all character pair frequencies across the corpus.
    pair_freqs = {}
    for word in words:
        chars = list(word) + [end_marker]
        for i in range(len(chars) - 1):
            pair = (chars[i], chars[i + 1])
            pair_freqs[pair] = pair_freqs.get(pair, 0) + 1

    # Apply BPE merges iteratively.
    merged_pairs: set[tuple[str, str]] = set()

    while len(merged_pairs) < max_tokens // 2 and pair_freqs:
        # Find the most frequent pair.
        most_frequent_pair = max(pair_freqs, key=pair_freqs.get)
        a, b = most_frequent_pair

        # Merge all occurrences of this pair in each word.
        for word in words:
            chars = list(word) + [end_marker]
            new_chars = []
            i = 0
            while i < len(chars):
                if (i + 1 < len(chars)) and (chars[i], chars[i + 1]) == (a, b):
                    merged = chars[i] + chars[i + 1]
                    new_chars.append(merged)
                    i += 2
                else:
                    new_chars.append(chars[i])
                    i += 1

            # Update pair frequencies for the merged characters.
            for j in range(len(new_chars) - 1):
                pair = (new_chars[j], new_chars[j + 1])
                if pair not in merged_pairs and pair != most_frequent_pair:
                    pair_freqs[pair] = pair_freqs.get(pair, 0) + 1

        # Mark this pair as merged.
        merged_pairs.add(most_frequent_pair)

    # Apply learned merges to each word.
    for word in words:
        chars = list(word) + [end_marker]
        merged_chars = []
        i = 0
        while i < len(chars):
            if (i + 1 < len(chars)) and (chars[i], chars[i + 1]) in merged_pairs:
                # Merge the pair.
                merged_chars.append(chars[i] + chars[i + 1])
                i += 2
            else:
                merged_chars.append(chars[i])
                i += 1

        tokens.extend(merged_chars)
        tokens.append(" ")  # Space separator between words.

    if tokens and tokens[-1] == " ":
        tokens.pop()  # Remove trailing space.

    # Apply max_tokens limit.
    if len(tokens) > max_tokens:
        tail = " ".join(tokens[max_tokens - 1:])
        tokens = tokens[:max_tokens - 1] + [tail]

    return tokens


if __name__ == "__main__":
    print("Testing OCR...")

    # Create a test image with text (using Pillow's draw).
    img = Image.new("RGB", (400, 100), color="white")
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((20, 20), "Hello World - SCNN Vision Test", fill="black", font=font)

    # Run OCR.
    results = ocr_image(img)
    print(f"Extracted {len(results)} text regions:")
    for r in results:
        print(f"   '{r['text']}' (confidence: {r['confidence']:.2f})")

    # Test BPE tokenization.
    sample = "The quick brown fox jumps over the lazy dog. Vision framework OCR works!"
    tokens = bpe_tokenize(sample, max_tokens=30)
    print(f"\nBPE tokenize ({len(tokens)} tokens): {' '.join(tokens)!r}")
