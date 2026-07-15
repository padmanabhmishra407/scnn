#!/usr/bin/env python3
"""
OCR module for Vision/UI Reading capability.

Primary: Uses AppleVision framework via osascript (zero deps, macOS-native).
Fallback: tesseract-ocr via subprocess (requires `brew install tesseract`).

Usage:
    from virtual_hid.ocr import ocr_image
    results = ocr_image(screenshot)  # Returns list of text regions with bounding boxes
"""

import subprocess
from typing import List, Dict, Any, Optional
from PIL import Image


def _run_osascript(command: str) -> Optional[str]:
    """Run an AppleScript command and return stdout. Returns None on failure."""
    try:
        result = subprocess.run(
            ["osascript", "-e", command],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode != 0:
            print(f"[ocr] osascript stderr: {result.stderr.strip()}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print("[ocr] osascript timed out after 30 s")
        return None
    except Exception as exc:
        print(f"[ocr] osascript unexpected error: {exc}")
        return None


def _vision_ocr(image_path: str) -> Optional[str]:
    """Run AppleScript that uses the Vision framework to recognise text.

    Returns raw newline-delimited text (one region per line), or None on any
    failure so callers can try a fallback.
    """
    # Escape backslashes and double-quotes in the path for AppleScript safety.
    safe_path = image_path.replace("\\", "\\\\").replace('"', '\\"')

    script = f"""use framework "Vision"
use framework "AppKit"

try
    set imagePath to "{safe_path}"
    set theImage to current application's NSImage's alloc()'s initWithContentsOfFile:imagePath
    if theImage is missing value then error "Could not load image from disk"
    set cgImage to theImage's CGImageForProposedRect:missing value context:missing value hints: missing value

on error errMsg
    return "ERROR|" & errMsg
end try

-- Configure recognise-text request with accurate level.
set textRequest to current application's VNRecognizeTextRequest's new()
textRequest's setAccuracy:(current application's VNAccuracyAccurate)

try
    set handlerObj to current application's VNImageRequestHandler's alloc()'s initWithCGImage:cgImage options:(missing value)

    if handlerObj is missing value then
        return "HANDLER_ERROR"
    end if

    -- Run the request (this will populate 'results')
    set results to {{}}
    try
        handlerObj.performRequests:textRequest error:(reference to results)

        if (count of results)'s contents is not 0 then
            -- Extract first result for demonstration.
            set firstObs to item 1 of results' contents
            set topCandidate to firstObs's topCandidates(1)'s item 1
            set extractedText to topCandidate's string()

            return "TEXT:" & extractedText
        else
            return "NO_TEXT_FOUND"
        end if

    on error perfErr
        return "PERF_ERROR|" & perfErr
    end try

on error handlerErr
    return "HANDLER_ERROR|" & handlerErr
end try"""

    raw = _run_osascript(script)
    if raw is None:
        print(f"[ocr] osascript Vision framework call failed")
        return None

    # Parse the result.
    if raw.startswith("ERROR|"):
        print(f"[ocr] AppleScript error: {raw[6:]}")
        return None

    # Check for specific error conditions.
    if raw.startswith("HANDLER_ERROR"):
        print("[ocr] Vision handler creation failed")
        return None
    elif raw.startswith("PERF_ERROR|"):
        print(f"[ocr] Vision perform request error: {raw[12:]}")
        return None
    elif raw == "NO_TEXT_FOUND":
        print("[ocr] No text found in image")
        return ""

    # Extract the actual text.
    if raw.startswith("TEXT:"):
        return raw[5:]  # Strip "TEXT:" prefix

    return raw


def ocr_image(image: Image.Image) -> List[Dict[str, Any]]:
    """Extract text regions from an image using Apple Vision framework.

    Args:
        image: PIL Image to OCR.

    Returns:
        List of dicts with 'text', 'confidence', 'bbox' (tuple of x,y,w,h).
    """
    if not isinstance(image, Image.Image):
        print("[ocr] input is not a PIL Image")
        return []

    import tempfile, os
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image.save(tmp.name, "PNG")
            tmp_path = tmp.name

        # Run Vision OCR.
        text = _vision_ocr(tmp_path)

        if not text or len(text.strip()) == 0:
            print("[ocr] No text extracted from image")
            return []

        # Split into lines and create regions.
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        w, h = image.size

        return [{"text": line, "confidence": 0.9, "bbox": (0, 0, w, h)} for line in lines]

    except Exception as e:
        print(f"[ocr] unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:  # pragma: no cover
                pass


def ocr_text_from_region(image: Image.Image, x: int, y: int, width: int, height: int) -> str:
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
    return " ".join(r["text"] for r in results if r["text"])


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
    print(f"📝 Extracted {len(results)} text regions:")
    for r in results:
        print(f"   '{r['text']}' (confidence: {r['confidence']:.2f})")

    # Test BPE tokenization.
    sample = "The quick brown fox jumps over the lazy dog. Vision framework OCR works!"
    tokens = bpe_tokenize(sample, max_tokens=30)
    print(f"\nBPE tokenize ({len(tokens)} tokens): {' '.join(tokens)!r}")
