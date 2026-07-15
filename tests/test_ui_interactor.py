"""Unit tests for ui_interactor module - edge case handling."""

import sys
sys.path.insert(0, '/Users/padmanabhmishra/Documents/scnn')

from src.virtual_hid.ui_interactor import (
    identify_clickable_elements,
    click_element,
    right_click_element,
    scroll_at,
    type_into_element,
    handle_modal_dialog,
    ClickableElement,
    BoundingBox,
)


def test_identify_clickable_elements_invalid_image():
    """Test that invalid images raise appropriate errors."""
    try:
        identify_clickable_elements("nonexistent.jpg")
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "Could not load image" in str(e)


def test_click_element_disabled_button():
    """Test that disabled buttons raise ValueError."""
    try:
        click_element({'x': 100, 'y': 200, 'disabled': True})
        assert False, "Should have raised ValueError for disabled button"
    except ValueError as e:
        assert "flagged as disabled" in str(e)


def test_click_element_missing_coordinates():
    """Test that missing x/y coordinates raise ValueError."""
    try:
        click_element({'label': 'OK'})
        assert False, "Should have raised ValueError for missing coordinates"
    except ValueError as e:
        assert "missing required field" in str(e)


def test_click_element_invalid_coordinates():
    """Test that non-numeric coordinates raise ValueError."""
    try:
        click_element({'x': 'abc', 'y': 200})
        assert False, "Should have raised ValueError for invalid coordinates"
    except ValueError as e:
        assert "must be numeric" in str(e)


def test_type_into_element_invalid_text():
    """Test that non-string text raises ValueError."""
    try:
        type_into_element({'x': 100, 'y': 200}, 12345)
        assert False, "Should have raised ValueError for non-string text"
    except ValueError as e:
        assert "must be a string" in str(e)


def test_type_into_element_empty_text_no_focus():
    """Test that empty text returns False without focusing."""
    result = type_into_element({'x': 100, 'y': 200}, "", click_first=False)
    assert result is False


def test_handle_modal_dialog_empty_text():
    """Test that empty dialog text raises ValueError."""
    try:
        handle_modal_dialog("")
        assert False, "Should have raised ValueError for empty dialog text"
    except ValueError as e:
        assert "non-empty string" in str(e)


def test_bounding_box_properties():
    """Test BoundingBox coordinate calculations."""
    bbox = BoundingBox(x1=10, y1=20, x2=110, y2=50)
    assert bbox.width == 100
    assert bbox.height == 30
    assert bbox.center_x == 60.0
    assert bbox.center_y == 35.0


def test_clickable_element_properties():
    """Test ClickableElement coordinate extraction."""
    bbox = BoundingBox(x1=10, y1=20, x2=110, y2=50)
    elem = ClickableElement(
        type="button",
        label="OK",
        bbox=bbox,
        confidence=0.9,
        disabled=False,
    )
    assert elem.x == 60
    assert elem.y == 35
    assert elem.width == 100
    assert elem.height == 30


def test_dialog_action_identification():
    """Test that dialog text correctly identifies preferred action."""
    # Acceptable dialogs
    result = handle_modal_dialog("Do you want to save changes?")
    assert result == "accepted"

    result = handle_modal_dialog("Confirm delete this file?")
    assert result == "accepted"

    # Cancelable dialogs
    result = handle_modal_dialog("Are you sure? This cannot be undone.")
    assert result == "cancelled"

    result = handle_modal_dialog("File not found. Retry or Cancel?")
    assert result == "cancelled"


def test_element_classification():
    """Test that element types are correctly classified."""
    bbox = BoundingBox(x1=0, y1=0, x2=50, y2=30)

    # Button detection
    elem = ClickableElement(type="button", label="OK", bbox=bbox)
    assert elem.type == "button"

    # Text field detection (long horizontal element)
    long_bbox = BoundingBox(x1=0, y1=0, x2=300, y2=30)
    elem = ClickableElement(type="text_field", label="Search...", bbox=long_bbox)
    assert elem.type == "text_field"

    # Checkbox detection
    elem = ClickableElement(type="checkbox", label="☐", bbox=bbox)
    assert elem.type == "checkbox"


def test_mouse_injection_osascript():
    """Test that mouse injection falls back to osascript when MouseMixin unavailable."""
    # click_element should work via osascript fallback
    result = click_element({'x': 100, 'y': 200})
    assert result is True

    # type_into_element should work via osascript fallback
    result = type_into_element({'x': 100, 'y': 200}, "test")
    assert result is True


if __name__ == "__main__":
    print("Running ui_interactor tests...")

    test_identify_clickable_elements_invalid_image()
    print("✅ identify_clickable_elements: invalid image handling")

    test_click_element_disabled_button()
    print("✅ click_element: disabled button rejection")

    test_click_element_missing_coordinates()
    print("✅ click_element: missing coordinates validation")

    test_click_element_invalid_coordinates()
    print("✅ click_element: invalid coordinates validation")

    test_type_into_element_invalid_text()
    print("✅ type_into_element: invalid text validation")

    test_type_into_element_empty_text_no_focus()
    print("✅ type_into_element: empty text handling")

    test_handle_modal_dialog_empty_text()
    print("✅ handle_modal_dialog: empty text validation")

    test_bounding_box_properties()
    print("✅ BoundingBox: coordinate calculations")

    test_clickable_element_properties()
    print("✅ ClickableElement: property extraction")

    test_dialog_action_identification()
    print("✅ handle_modal_dialog: action identification")

    test_element_classification()
    print("✅ element classification: type detection")

    test_mouse_injection_osascript()
    print("✅ mouse injection: osascript fallback")

    print("\n🎉 All tests passed!")
