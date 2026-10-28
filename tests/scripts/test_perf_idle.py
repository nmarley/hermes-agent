from __future__ import annotations

from scripts.perf.idle import classify_frames


def test_classify_frames_attributes_nearby_react_commits() -> None:
    frames = [
        {"ts": 1000, "phases": {"patches": 3}},
        {"ts": 1100, "phases": {"patches": 0}},
        {"ts": 1200, "phases": {"patches": 2}},
    ]
    react = [{"ts": 1001, "id": "appChrome"}, {"ts": 1204, "id": "prompt"}]

    counts = classify_frames(frames, react)

    assert counts["react:appChrome"] == 1
    assert counts["react:prompt"] == 1
    assert counts["noop"] == 1
    assert counts["render"] == 0


def test_classify_frames_without_a_react_commit_is_a_render() -> None:
    counts = classify_frames([{"ts": 1000, "phases": {"patches": 1}}], [])
    assert counts["render"] == 1


def test_classify_frames_labels_a_one_second_cadence_as_a_clock() -> None:
    frames = [
        {"ts": 1000, "phases": {"patches": 1}},
        {"ts": 2000, "phases": {"patches": 1}},
    ]
    react = [{"ts": 1000, "id": "composer"}, {"ts": 2000, "id": "composer"}]
    counts = classify_frames(frames, react)
    assert counts["clock:composer"] == 2


def test_classify_frames_counts_each_frame_once_when_panes_share_a_commit() -> None:
    counts = classify_frames(
        [{"ts": 1000, "phases": {"patches": 1}}],
        [{"ts": 1001, "id": "a"}, {"ts": 1002, "id": "b"}],
    )
    assert sum(counts.values()) == 1
    assert counts["react:a"] == 1


def test_classify_frames_is_empty_without_frames() -> None:
    assert classify_frames([], []) == {}
