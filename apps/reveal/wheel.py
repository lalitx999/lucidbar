"""
Geometry for the prize wheel SVG. Pure math, no database.

Segment 0 starts at 12 o'clock and segments run clockwise. To bring segment
i under the pointer at the top, rotate the wheel by -(i + 0.5) * step.
"""

import math
from dataclasses import dataclass

RADIUS = 100
# Labels end near the rim and grow inward, so long names never overflow it.
LABEL_RADIUS = 93


@dataclass(frozen=True)
class Segment:
    index: int
    label: str
    path: str  # SVG path for the slice
    label_x: float
    label_y: float
    label_rotate: float  # degrees, text runs along the radius
    anchor: str  # "end" on the right half, "start" on the left (kept upright)
    tone: str  # "gold" or "dark", for alternating colours via CSS classes


def _point(angle_deg: float, r: float) -> tuple[float, float]:
    # 0 degrees = 12 o'clock, clockwise positive.
    rad = math.radians(angle_deg - 90)
    return (round(r * math.cos(rad), 3), round(r * math.sin(rad), 3))


def segments(labels: list[str]) -> list[Segment]:
    n = len(labels)
    if n == 0:
        return []
    step = 360 / n
    out = []
    for i, label in enumerate(labels):
        start, end = i * step, (i + 1) * step
        x1, y1 = _point(start, RADIUS)
        x2, y2 = _point(end, RADIUS)
        large = 1 if step > 180 else 0
        path = f"M0,0 L{x1},{y1} A{RADIUS},{RADIUS} 0 {large} 1 {x2},{y2} Z"
        mid = start + step / 2
        lx, ly = _point(mid, LABEL_RADIUS)
        # Right half: text points outward and ends at the rim. Left half: flip
        # it so it is not upside down, and start it at the rim instead.
        left_half = mid > 180
        rotate = mid + 90 if left_half else mid - 90
        out.append(
            Segment(
                index=i,
                label=label,
                path=path,
                label_x=lx,
                label_y=ly,
                label_rotate=round(rotate, 3),
                anchor="start" if left_half else "end",
                tone="gold" if i % 2 == 0 else "dark",
            )
        )
    return out


def landing_rotation(index: int, count: int, full_turns: int = 6) -> float:
    """Total clockwise rotation (degrees) that ends with `index` under the pointer."""
    step = 360 / count
    return full_turns * 360 + (360 - (index + 0.5) * step)
