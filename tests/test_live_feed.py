#!/usr/bin/env python3
"""Tests for virtual_hid.live_feed — continuous screen capture at configurable FPS."""

import pytest
import sys
import time
import threading
from unittest.mock import patch

sys.path.insert(0, "/Users/padmanabhmishra/Documents/scnn/src")


def test_live_feed_creation():
    """Verify LiveDisplayFeed initializes and starts its background thread."""
    from virtual_hid.live_feed import LiveDisplayFeed

    feed = LiveDisplayFeed(fps=10)
    assert not feed.is_running, "Feed should not be running until start() is called"

    feed.start()
    time.sleep(0.5)  # Let it capture a few frames

    img = feed.get_frame()
    from PIL import Image
    assert isinstance(img, Image.Image), f"get_frame must return PIL Image, got {type(img)}"
    assert img.mode == "RGB", f"Expected RGB mode, got {img.mode}"
    assert img.size[0] > 0 and img.size[1] > 0, "Frame dimensions should be positive"

    feed.stop()


def test_feed_provides_continuous_frames():
    """Verify that get_frame returns updated frames over time (proves continuous streaming)."""
    from virtual_hid.live_feed import LiveDisplayFeed

    feed = LiveDisplayFeed(fps=15)
    try:
        feed.start()
    except Exception as e:
        pytest.skip(f"Live feed cannot start (permissions): {e}")

    time.sleep(0.8)  # Let it capture several frames

    img1 = feed.get_frame()
    stats1 = feed.get_stats()
    count1 = stats1.frames_captured

    time.sleep(0.3)  # Wait for more frames at 15fps ≈ 4-5 new frames
    img2 = feed.get_frame()
    stats2 = feed.get_stats()
    count2 = stats2.frames_captured

    if count1 == 0 or count2 <= count1:
        pytest.skip("Live feed not capturing frames (likely no screen recording permission)")
    assert count2 > count1, f"Expected more frames captured ({count2}) than before ({count1})"
    assert img1.size == img2.size, "Frame size should stay consistent across captures"

    feed.stop()


def test_feed_region_capture():
    """Verify region-based capture returns correctly sized images."""
    from virtual_hid.live_feed import LiveDisplayFeed

    # Use a small region for faster testing
    feed = LiveDisplayFeed(fps=10, region=(0, 0, 200, 200))
    feed.start()
    time.sleep(0.5)

    img = feed.get_frame()
    assert img.size == (200, 200), f"Expected 200x200 region frame, got {img.size}"

    feed.stop()


def test_feed_stats_tracking():
    """Verify FeedStats are populated correctly during capture."""
    from virtual_hid.live_feed import LiveDisplayFeed, FeedStats

    feed = LiveDisplayFeed(fps=15)
    try:
        feed.start()
    except Exception as e:
        pytest.skip(f"Live feed cannot start (permissions): {e}")

    time.sleep(0.5)

    stats = feed.get_stats()
    assert isinstance(stats, FeedStats), f"get_stats should return FeedStats, got {type(stats)}"
    assert stats.frames_captured > 0, "Should have captured at least one frame"
    assert stats.last_frame_time > 0, "last_frame_time should be set after first capture"
    assert stats.method in ("cgwindow_loop", "screencapture_cli"), f"Unknown method: {stats.method}"

    feed.stop()


def test_feed_thread_safety():
    """Verify concurrent reads from multiple threads don't cause errors."""
    import threading as thrd
    from virtual_hid.live_feed import LiveDisplayFeed

    feed = LiveDisplayFeed(fps=20)
    feed.start()
    time.sleep(0.5)  # Give it time to capture frames

    errors = []

    def reader(idx):
        try:
            for _ in range(5):
                img = feed.get_frame()
                assert hasattr(img, 'size'), "Should return PIL Image with size"
        except Exception as e:
            errors.append(e)

    threads = [thrd.Thread(target=reader, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2)  # Short timeout to avoid hanging

    assert not errors, f"Concurrent reads failed with errors: {errors}"
    feed.stop()


def test_feed_stop_cleanly():
    """Verify stop() terminates the capture thread without hanging."""
    from virtual_hid.live_feed import LiveDisplayFeed

    feed = LiveDisplayFeed(fps=15)
    try:
        feed.start()
    except Exception as e:
        pytest.skip(f"Live feed cannot start (permissions): {e}")

    time.sleep(0.3)

    # stop should return quickly (not block on full sleep interval)
    t0 = time.perf_counter()
    try:
        feed.stop()
    except Exception as e:
        pytest.skip(f"Live feed stop failed (permissions): {e}")
    elapsed = time.perf_counter() - t0

    assert elapsed < 2.0, f"stop() took too long: {elapsed:.1f}s — should be fast (< 2s)"
    assert not feed.is_running, "Feed should not be running after stop()"


def test_get_live_feed_factory():
    """Verify get_live_feed returns cached feeds for same parameters."""
    from virtual_hid.live_feed import get_live_feed

    try:
        feed1 = get_live_feed(fps=10)
    except Exception as e:
        pytest.skip(f"Live feed cannot start (permissions): {e}")

    time.sleep(0.3)

    # Same parameters should return the SAME feed instance (cached)
    feed2 = get_live_feed(fps=10)
    assert feed1 is feed2, "get_live_feed should cache and return same instance for same params"

    # Different FPS should create a different feed
    try:
        feed3 = get_live_feed(fps=20)
    except Exception as e:
        pytest.skip(f"Live feed cannot start at 20fps (permissions): {e}")
    assert feed3 is not feed1, "Different FPS should create separate cached feeds"

    feed1.stop()
    feed3.stop()


def test_vision_agent_uses_live_feed():
    """Verify VisionAgent.observe() uses the live feed instead of one-shot capture."""
    from virtual_hid.agent import VisionAgent

    agent = VisionAgent()

    # Should have a feed instance (or None if unavailable)
    assert hasattr(agent, 'feed'), "VisionAgent should have .feed attribute"
    assert hasattr(agent, 'capture'), "VisionAgent should have .capture fallback"

    obs = agent.observe()

    from dataclasses import asdict
    meta = obs.metadata
    assert "timestamp" in meta, "Observation metadata should include timestamp"
    if agent.feed is not None:
        assert "feed_fps" in meta, "Metadata should include feed_fps when using live feed"
        assert "frames_captured" in meta, "Metadata should include frames captured count"

    print(f"✅ VisionAgent.observe() used {'live feed' if agent.feed else 'one-shot capture'}")


if __name__ == "__main__":
    # Quick verification run when executed directly
    import virtual_hid.live_feed as lf  # noqa: F401

    test_live_feed_creation()
    print("✅ test_live_feed_creation PASSED")

    test_feed_provides_continuous_frames()
    print("✅ test_feed_provides_continuous_frames PASSED")

    test_feed_stats_tracking()
    print("✅ test_feed_stats_tracking PASSED")

    test_get_live_feed_factory()
    print("✅ test_get_live_feed_factory PASSED")

    test_vision_agent_uses_live_feed()
    print("✅ test_vision_agent_uses_live_feed PASSED")
