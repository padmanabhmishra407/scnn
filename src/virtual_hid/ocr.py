#!/usr/bin/env python3
"""
OCR module for Vision/UI Reading capability.

Primary: Uses Apple Vision framework via osascript (zero deps, macOS-native).
Fallback: tesseract-ocr via subprocess (requires `brew install tesseract`).

Usage:
    from virtual_hid.ocr import ocr_image
    results = ocr_image(screenshot)  # Returns list of text regions with bounding boxes
"""

import subprocess
from typing import List, Dict, Any
from PIL import Image


def _run_osascript(command: str) -> str:
    """Run an AppleScript command and return stdout."""
    result = subprocess.run(
        ["osascript", "-e", command],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def ocr_image(image: Image.Image) -> List[Dict[str, Any]]:
    """Extract text regions from an image using Apple Vision framework.

    Args:
        image: PIL Image to OCR.

    Returns:
        List of dicts with 'text', 'confidence', 'bbox' (tuple of x,y,w,h).
    """
    # Save image temporarily for osascript processing
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image.save(tmp.name, "PNG")
        tmp_path = tmp.name

    try:
        script = f"""
        use framework "Vision"
        use framework "AppKit"

        set imagePath to "{tmp_path}"
        set theImage to (current application's NSImage's alloc()'s initWithContentsOfFile:imagePath)
        set cgImage to (theImage's CGImageForProposedRect:missing value context:missing value hints: missing value)

        set textRecognizer to current application's VNRecognizeTextRequest's new()
        set success to textRecognizer's setDelegate:(missing value)
        set results to []
        try
            set theHandler to current application's VNImageRequestHandler's alloc()'s initWithCGImage:cgImage options:missing value
            theHandler's performRequests:{textRecognizer} error:(reference to results)
            if (count of results)'s contents is not 0 then
                repeat with observation in results' contents
                    set topCandidate to observation's topCandidates(1)'s item 1
                    return topCandidate's string
                end repeat
            else
                return "No text found"
            end if
        on error e
            return "OCR Error: " & e
        end try
        """

        result = _run_osascript(script)
        if result.startswith("OCR Error"):
            print(f"⚠️  Vision framework OCR failed: {result}")
            # Fallback to tesseract if available
            return ocr_image_tesseract(image)

        # Parse multi-line results into structured format
        text_lines = [line.strip() for line in result.split("\n") if line.strip()]
        return [{"text": line, "confidence": 0.9, "bbox": (0, 0, image.width, image.height)}
                for line in text_lines]

    except subprocess.CalledProcessError as e:
        print(f"⚠️  osascript Vision framework failed: {e.stderr}")
        return ocr_image_tesseract(image)
    finally:
        import os
        os.unlink(tmp_path)


def ocr_image_tesseract(image: Image.Image) -> List[Dict[str, Any]]:
    """Fallback OCR using tesseract-ocr (requires `brew install tesseract`).

    Args:
        image: PIL Image to OCR.

    Returns:
        List of dicts with 'text', 'confidence' (estimated), 'bbox'.
    """
    try:
        # Save image temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image.save(tmp.name, "PNG")
            tmp_path = tmp.name

        # Run tesseract and get structured output
        result = subprocess.run(
            ["tesseract", tmp_path, "-", "--psm", "6"],  # PSM 6 = assume single column text
            capture_output=True, text=True, check=True
        )

        lines = [line.strip() for line in result.stdout.split("\n") if line.strip()]
        return [{"text": line, "confidence": 0.85, "bbox": (0, 0, image.width, image.height)}
                for line in lines]

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"⚠️  Tesseract OCR failed: {e}")
        return []


def ocr_text_from_region(image: Image.Image, x: int, y: int, width: int, height: int) -> str:
    """Extract text from a specific region of an image.

    Args:
        image: Full PIL Image.
        x, y: Top-left corner of region.
        width, height: Region dimensions.

    Returns:
        Extracted text as string.
    """
    cropped = image.crop((x, y, x + width, y + height))
    results = ocr_image(cropped)
    return " ".join(r["text"] for r in results if r["text"])


if __name__ == "__main__":
    print("Testing OCR...")

    # Create a test image with text (using Pillow's draw)
    img = Image.new("RGB", (400, 100), color="white")
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((20, 20), "Hello World - SCNN Vision Test", fill="black", font=font)

    # Run OCR
    results = ocr_image(img)
    print(f"📝 Extracted {len(results)} text regions:")
    for r in results:
        print(f"   '{r['text']}' (confidence: {r['confidence']:.2f})")
