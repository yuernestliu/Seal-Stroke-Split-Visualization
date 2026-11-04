from dataclasses import dataclass

import numpy as np


Point = tuple[int, int]


@dataclass(slots=True)
class StrokeSegment:
    stroke_id: int
    points: list[Point]


@dataclass(slots=True)
class SplitResult:
    binary: np.ndarray
    cropped_binary: np.ndarray
    skeleton: np.ndarray
    stroke_map: np.ndarray
    stroke_masks: list[np.ndarray]
    segments: list[StrokeSegment]
    debug: dict
