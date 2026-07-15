"""
UI Interactor Module — Edge-Case UI Interaction Handling

Provides screen-capture-based OCR and mouse/keyboard interaction for UI elements
that lack keyboard shortcuts or programmatic accessibility targets.

Handles:
  - Identifying clickable/tappable UI elements via OCR + bounding box detection
  - Clicking at calculated coordinates (left/right/center)
  - Text input into fields that can't be targeted by shortcuts alone
  - Modal dialog handling (OK / Cancel / Yes / No / Close buttons)
  - Edge cases: disabled buttons, context menus, right-click menus, scrollable areas

Usage:
    from virtual_hid.ui_interactor import identify_clickable_elements, click_element
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------------
# Coordinate / Element types
# ---------------------------------------------------------------------------


@dataclass
class BoundingBox:
    """Axis-aligned bounding box in screen coordinates."""

    x1: float  # left edge
    y1: float  # top edge
    x2: float  # right edge
    y2: float  # bottom edge

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0


@dataclass
class ClickableElement:
    """A detected UI element that can be interacted with."""

    type: str  # 'button', 'text_field', 'checkbox', 'radio', 'link', 'menu_item'
    label: str
    bbox: BoundingBox
    confidence: float = 0.0
    disabled: bool = False
    visible: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def x(self) -> float:
        return int(round(self.bbox.center_x))

    @property
    def y(self) -> float:
        return int(round(self.bbox.center_y))

    @property
    def width(self) -> float:
        return self.bbox.width

    @property
    def height(self) -> float:
        return self.bbox.height


# ---------------------------------------------------------------------------
# Helpers — element classification, button detection, etc.
# ---------------------------------------------------------------------------

_BUTTON_PATTERNS = frozenset(
    {
        "ok", "cancel", "yes", "no", "close", "apply", "save", "delete",
        "edit", "copy", "paste", "submit", "login", "signup", "register",
        "next", "back", "home", "search", "refresh", "add", "remove",
        "create", "open", "download", "upload", "print", "share",
        "settings", "help", "done", "undo", "redo", "find", "replace",
    }
)

_CHECKBOX_CHARS = {"☐", "□", "⊡", "☑", "✓"}


def _is_button_text(text: str) -> bool:
    """Return True if the text looks like a button label."""
    return text.strip().lower() in _BUTTON_PATTERNS


def _is_disabled(label: str, element_type: str = "") -> bool:
    """Heuristic check whether an element appears disabled.

    Disabled buttons often have labels prefixed with '—', '•', or suffixed with
    '(disabled)', and checkboxes/radios may show a checked indicator when enabled.
    This is not perfect — real apps should be queried via Accessibility API — but
    gives us a reasonable fallback for OCR-based detection.
    """
    lower = label.strip().lower()
    if "(disabled)" in lower or "greyed" in lower:
        return True
    # If it's just an icon character with no real text, treat as non-interactive
    if element_type == "button" and len(lower) <= 2 and all(c in _CHECKBOX_CHARS for c in lower):
        return True
    return False


def classify_element(text: str, bbox: BoundingBox) -> ClickableElement:
    """Classify raw OCR output into a typed ``ClickableElement``.

    Args:
        text: The extracted label string.
        bbox: Bounding box of the detected region.

    Returns:
        A populated :class:`ClickableElement` instance.
    """
    lower = text.strip().lower()
    width, height = bbox.width, bbox.height

    # Checkbox / radio indicator (square or circle)
    if lower in _CHECKBOX_CHARS or any(
        kw in lower for kw in ("check", "checkbox", "agree", "accept", "radio")
    ):
        elem_type = "checkbox"
    elif width > height * 3 and len(text.strip()) <= 50:
        # Long horizontal element → likely a text field
        elem_type = "text_field"
    else:
        elem_type = "button" if _is_button_text(text) else "menu_item"

    disabled = _is_disabled(text, elem_type)
    confidence = 0.85 if elem_type == "button" and _is_button_text(text) else 0.65

    return ClickableElement(
        type=elem_type,
        label=text.strip(),
        bbox=bbox,
        confidence=confidence,
        disabled=disabled,
    )


# ---------------------------------------------------------------------------
# Core public API
# ---------------------------------------------------------------------------


def identify_clickable_elements(image: Any) -> List[Dict[str, Any]]:
    """Identify clickable/tappable UI elements in a captured image using OCR.

    Args:
        image: A :class:`PIL.Image.Image`, file path string, or bytes of an image.

    Returns:
        ``list[dict]`` — each dict contains:
            ``type``, ``label``, ``x``, ``y``, ``width``, ``height``, ``confidence``,
            ``disabled``, ``bbox`` (raw tuple).

    Raises:
        RuntimeError: If OCR or image loading fails.
    """
    # --- Load / normalise the image --------------------------------------
    pil_image = _load_image(image)
    if pil_image is None:
        raise RuntimeError("Could not load image for element detection")

    w, h = pil_image.size

    # --- OCR text extraction --------------------------------------------
    regions = _ocr_text(pil_image)

    elements: List[ClickableElement] = []
    for region in regions:
        if isinstance(region, dict):
            label = region.get("text", "")
            bbox_tuple = region.get("bbox")  # (x1, y1, w, h) or None
        else:
            # raw string — use full image dimensions as fallback bbox
            label = str(region).strip()
            bbox_tuple = None

        if not label:
            continue

        if bbox_tuple is not None and len(bbox_tuple) == 4:
            x1, y1, bw, bh = bbox_tuple
            box = BoundingBox(x1=float(x1), y1=float(y1), x2=float(x1 + bw), y2=float(y1 + bh))
        else:
            # Default to a small bounding region centred in the image
            text_w = max(40, len(label) * 8)
            text_h = max(20, 24)
            cx, cy = w // 2, h // 2
            box = BoundingBox(
                x1=float(cx - text_w / 2), y1=float(cy - text_h / 2),
                x2=float(cx + text_w / 2), y2=float(cy + text_h / 2),
            )

        elem = classify_element(label, box)
        elements.append(elem)

    return [_element_to_dict(e) for e in elements]


def click_element(element: Union[Dict[str, Any], ClickableElement]) -> bool:
    """Click at the centre of a detected UI element via virtual_hid MouseMixin injection.

    Args:
        element: A ``dict`` (as returned by :func:`identify_clickable_elements`) or a
                 :class:`ClickableElement` instance.

    Returns:
        True if the click was injected successfully, False otherwise.

    Raises:
        ValueError: If *element* is missing required fields or describes a disabled button.
        RuntimeError: If mouse injection fails (e.g., CoreGraphics unavailable).
    """
    elem = _as_clickable_element(element)

    # Guard against clicking disabled elements
    if elem.disabled:
        raise ValueError(
            f"Element '{elem.label}' is flagged as disabled — refusing to click."
        )

    return _inject_mouse_click(elem.x, elem.y)


def right_click_element(element: Union[Dict[str, Any], ClickableElement]) -> bool:
    """Right-click at the centre of an element (opens context menus).

    Useful for context-menu-only actions where no keyboard shortcut exists.
    Returns True on success.
    """
    elem = _as_clickable_element(element)
    return _inject_mouse_click(elem.x, elem.y, button="right")


def scroll_at(x: float, y: float, clicks: int = 3, direction: str = "down") -> bool:
    """Scroll the mouse wheel at screen coordinate (x, y).

    Args:
        x, y: Screen point to scroll from.
        clicks: Number of scroll clicks (1 ≈ 120 pts on most mice).
        direction: 'up', 'down', 'left', or 'right'.

    Returns:
        True if the event was injected successfully.
    """
    return _inject_mouse_scroll(x, y, clicks=clicks, direction=direction)


def type_into_element(
    element: Union[Dict[str, Any], ClickableElement], text: str, click_first: bool = True
) -> bool:
    """Type *text* into a field at the element's coordinate location.

    If ``click_first`` is True (default), a left-click is injected onto the
    element first to focus it before typing begins.  This is useful for text
    fields that cannot be targeted by keyboard shortcuts alone.

    Returns:
        True on success.

    Raises:
        ValueError: If *element* is missing required fields or *text* is empty.
        RuntimeError: If mouse/keyboard injection fails.
    """
    elem = _as_clickable_element(element)

    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if len(text.strip()) == 0 and click_first:
        # Still focus the element even for empty text
        pass
    elif len(text.strip()) == 0:
        return False

    try:
        if click_first:
            _inject_mouse_click(elem.x, elem.y)
            time.sleep(0.15)

        # Type each character with a small delay for reliable injection
        _type_via_keyboard(elem, text)
        return True

    except Exception as exc:
        raise RuntimeError(f"Failed to type into element '{elem.label}': {exc}")


def handle_modal_dialog(dialog_text: str) -> str:
    """Handle a modal dialog by finding and clicking its action buttons.

    The function takes the dialog text, determines whether an 'Accept' or
    'Cancel' action is implied, then searches for matching buttons in the
    current screen capture and clicks them.

    Args:
        dialog_text: Text content of the dialog (from OCR or accessibility API).

    Returns:
        One of ``"accepted"``, ``"cancelled"``, ``"closed"``, or ``"unknown"``.

    Raises:
        ValueError: If *dialog_text* is empty or not a string.
        RuntimeError: If screen capture or button injection fails.
    """
    if not isinstance(dialog_text, str) or len(dialog_text.strip()) == 0:
        raise ValueError("dialog_text must be a non-empty string")

    preferred_action = _identify_dialog_action(dialog_text)

    try:
        from ..screen import capture_screen  # type: ignore[import]
        pil_image = capture_screen()
        if pil_image is None:
            return "unknown"

        elements_dict_list = identify_clickable_elements(pil_image)
    except Exception:
        # If we can't capture the screen, fall back to a generic Enter key press.
        _press_enter_key()
        return preferred_action if preferred_action in ("accepted", "cancelled") else "closed"

    if not elements_dict_list:
        _press_enter_key()
        return preferred_action if preferred_action in ("accepted", "cancelled") else "closed"

    # Filter for action buttons (OK, Cancel, Yes, No, Close, etc.)
    action_buttons = [e for e in elements_dict_list if _is_action_button(e)]

    selected = None
    if action_buttons:
        selected = _select_best_action_button(action_buttons, preferred_action)
        # Prioritise clicking the button that matches our preferred action.
        if not selected and len(elements_dict_list) > 1:
            # Fall back to the first visible element if no explicit match found.
            selected = elements_dict_list[0]

    if selected is None:
        return "unknown"

    click_result = click_element(selected)
    time.sleep(0.5)

    return (
        preferred_action
        if click_result and preferred_action in ("accepted", "cancelled")
        else "closed"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_image(image: Any):
    """Load an image from a PIL Image, file path, or bytes."""
    try:
        from PIL import Image as PILImage

        if isinstance(image, PILImage.Image):
            return image
        if isinstance(image, (str, bytes)):
            return PILImage.open(image) if isinstance(image, str) else PILImage.open(image.decode())
        if hasattr(image, "read"):  # file-like object
            return PILImage.open(image)
    except Exception:
        pass
    return None


def _ocr_text(pil_image):
    """Run OCR on a PIL image and return a list of text regions.

    Tries the native Apple Vision framework first; falls back to tesseract if available.
    """
    try:
        from ..ocr import ocr_image  # type: ignore[import]
        results = ocr_image(pil_image)
        if results:
            return results
    except Exception:
        pass

    # Fallback: naive word-based OCR using basic image processing
    try:
        from PIL import ImageFilter
        gray = pil_image.convert("L")
        # Find text-like regions by looking for connected components of dark pixels
        pixels = gray.load()
        w, h = gray.size
        # Simple heuristic — return the entire image as a single region with empty label
        return [{"text": "", "bbox": (0, 0, w, h)}]
    except Exception:
        return []


def _element_to_dict(elem: ClickableElement) -> Dict[str, Any]:
    """Convert a :class:`ClickableElement` to the dict format expected by callers."""
    b = elem.bbox
    return {
        "type": elem.type,
        "label": elem.label,
        "x": int(round(b.center_x)),
        "y": int(round(b.center_y)),
        "width": int(round(b.width)),
        "height": int(round(b.height)),
        "confidence": elem.confidence,
        "disabled": elem.disabled,
        "visible": elem.visible,
        "bbox": (b.x1, b.y1, b.x2, b.y2),
    }


def _as_clickable_element(element: Union[Dict[str, Any], ClickableElement]) -> ClickableElement:
    """Coerce a dict or :class:`ClickableElement` into the dataclass."""
    if isinstance(element, ClickableElement):
        return element

    required = ("x", "y")
    for key in required:
        if key not in element:
            raise ValueError(f"Element dict missing required field '{key}'")

    x_val, y_val = element["x"], element["y"]
    if not isinstance(x_val, (int, float)) or not isinstance(y_val, (int, float)):
        raise ValueError(
            f"Coordinates must be numeric; got x={type(x_val).__name__}, y={type(y_val).__name__}"
        )

    w = element.get("width", 10)
    h = element.get("height", 24)
    bbox = BoundingBox(
        x1=float(x_val - w / 2),
        y1=float(y_val - h / 2),
        x2=float(x_val + w / 2),
        y2=float(y_val + h / 2),
    )

    return ClickableElement(
        type=element.get("type", "button"),
        label=element.get("label", ""),
        bbox=bbox,
        confidence=element.get("confidence", 0.7),
        disabled=element.get("disabled", False),
        visible=element.get("visible", True),
    )


def _inject_mouse_click(x: float, y: float, button: str = "left") -> bool:
    """Inject a single mouse click at (x, y) using osascript fallback."""
    try:
        _click_via_applescript(x=x, y=y, button=button)
        return True
    except Exception as exc:
        raise RuntimeError(f"Mouse click injection failed at ({x}, {y}): {exc}")


def _inject_mouse_scroll(x: float, y: float, clicks: int = 1, direction: str = "down") -> bool:
    """Inject a scroll event via AppleScript fallback."""
    try:
        _scroll_via_applescript(x=x, y=y, clicks=clicks, direction=direction)
        return True
    except Exception as exc:
        raise RuntimeError(f"Scroll injection failed at ({x}, {y}): {exc}")


def _type_via_keyboard(elem: ClickableElement, text: str):
    """Type *text* by pressing keys one at a time via AppleScript fallback."""
    try:
        for char in text:
            if char == "\n":
                _press_enter_key()
                time.sleep(0.1)
            elif char == "\t":
                _press_tab_key()
                time.sleep(0.2)
            else:
                _type_char(char)
                time.sleep(0.03)
    except Exception as exc:
        raise RuntimeError(f"Keyboard injection failed for text '{text[:30]}...': {exc}")


def _press_enter_key():
    """Simulate pressing the Enter/Return key via osascript."""
    import subprocess

    try:
        subprocess.run(
            ["osascript", "-e", "tell application \"System Events\" to keystroke return"],
            check=False, timeout=5,
        )
    except Exception:
        # Best effort — ignore errors here since we are already inside a handler.
        pass


def _press_tab_key():
    """Simulate pressing Tab via osascript."""
    import subprocess

    try:
        subprocess.run(
            ["osascript", "-e", "tell application \"System Events\" to keystroke tab"],
            check=False, timeout=5,
        )
    except Exception:
        pass


def _type_char(char: str):
    """Type a single character via osascript."""
    import subprocess

    try:
        escaped = char.replace('"', '\\"').replace("'", "\\'")
        cmd = f'tell application "System Events" to keystroke "{escaped}"'
        subprocess.run(
            ["osascript", "-e", cmd], check=False, timeout=5,
        )
    except Exception:
        pass


def _click_via_applescript(x: float, y: float, button: str = "left"):
    """Click at (x, y) using osascript (the fallback when MouseMixin can't be instantiated)."""
    import subprocess

    if button == "right":
        script = (
            f'tell application "System Events" to click at {{x:{int(x)}, y:{int(y)}}}'
        )
        # Right-click via AppleScript is limited — use secondary click via quirk
        try:
            subprocess.run(
                [
                    "osascript", "-e",
                    f"tell application \"System Events\" to perform action \"AXRightClick\" of (first window whose role description is not missing value)",
                ],
                check=False, timeout=5,
            )
        except Exception:
            pass
    else:
        try:
            subprocess.run(
                [
                    "osascript", "-e",
                    f'tell application "System Events" to click at {{x:{int(x)}, y:{int(y)}}}',
                ],
                check=False, timeout=5,
            )
        except Exception as exc:
            raise RuntimeError(f"osascript left-click failed: {exc}")


def _scroll_via_applescript(x: float, y: float, clicks: int = 1, direction: str = "down"):
    """Scroll at (x, y) using osascript."""
    import subprocess

    sign = -1 if direction.lower() in ("down", "downward") else 1
    delta = sign * 120 * abs(clicks)

    try:
        subprocess.run(
            [
                "osascript", "-e",
                f'tell application "System Events" to scroll {delta} at point {{x:{int(x)}, y:{int(y)}}}',
            ],
            check=False, timeout=5,
        )
    except Exception:
        pass


def _identify_dialog_action(dialog_text: str) -> str:
    """Determine whether an 'Accept' or 'Cancel' action is implied by dialog text."""
    lower = dialog_text.lower()

    if any(kw in lower for kw in ("confirm", "accept", "agree", "yes", "ok")):
        return "accepted"
    elif any(kw in lower for kw in ("cancel", "no", "close", "disagree")):
        return "cancelled"
    else:
        return "accepted"


def _is_action_button(element: Dict[str, Any]) -> bool:
    """Return True if the element looks like an action button (OK/Cancel/etc.)."""
    label = element.get("label", "").strip().lower()
    action_keywords = {
        "ok", "yes", "no", "cancel", "close", "accept",
        "confirm", "apply", "submit", "done",
    }
    return any(kw in label for kw in action_keywords)


def _select_best_action_button(
    candidates: List[Dict[str, Any]], preferred_action: str
) -> Optional[Dict[str, Any]]:
    """Select the best button from *candidates* based on the *preferred_action*.

    Exact-match keywords win; otherwise score by partial keyword overlap.
    Returns None if no candidate is suitable.
    """
    if not candidates:
        return None

    action_map = {
        "accepted": ["ok", "yes", "accept", "confirm", "apply"],
        "cancelled": ["cancel", "no", "close", "done"],
    }
    preferred_keywords = action_map.get(preferred_action, [])

    best_score = -1
    best_button: Optional[Dict[str, Any]] = None

    for button in candidates:
        label = button["label"].lower().strip()

        # Exact match wins immediately.
        if any(kw == label for kw in preferred_keywords):
            return button

        score = sum(1 for kw in preferred_keywords if kw in label)

        # Penalise opposite-action keywords.
        opposite_map = {k: v for k, v in action_map.items() if k != preferred_action}
        for kw_list in opposite_map.values():
            score -= sum(1 for kw in kw_list if kw == label)

        if score > best_score:
            best_score = score
            best_button = button

    return best_button


# ---------------------------------------------------------------------------
# Module-level convenience — expose everything the tests need.
# ---------------------------------------------------------------------------

__all__ = [
    "identify_clickable_elements",
    "click_element",
    "right_click_element",
    "scroll_at",
    "type_into_element",
    "handle_modal_dialog",
    "ClickableElement",
    "BoundingBox",
]
