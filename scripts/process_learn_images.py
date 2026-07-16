"""Remove outer dark background and crop learn infographic images."""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

BASE = Path(__file__).resolve().parents[1] / "web" / "static" / "img" / "learn"
NAMES = ["learn-kline.png", "learn-ma.png", "learn-kd.png", "learn-macd.png"]


def color_close(a: tuple[int, int, int], b: tuple[int, int, int], tol: int) -> bool:
    return all(abs(a[i] - b[i]) <= tol for i in range(3))


def flood_transparent(im: Image.Image, tol: int = 12) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    ref = im.convert("RGB").getpixel((0, 0))

    q: deque[tuple[int, int]] = deque()
    seen: set[tuple[int, int]] = set()
    for x in range(w):
        for y in (0, h - 1):
            if px[x, y][3] and color_close(px[x, y][:3], ref, tol):
                q.append((x, y))
                seen.add((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if (x, y) not in seen and px[x, y][3] and color_close(px[x, y][:3], ref, tol):
                q.append((x, y))
                seen.add((x, y))

    while q:
        x, y = q.popleft()
        px[x, y] = (0, 0, 0, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                r, g, b, a = px[nx, ny]
                if a and color_close((r, g, b), ref, tol):
                    seen.add((nx, ny))
                    q.append((nx, ny))
    return im


def content_bbox(im: Image.Image) -> tuple[int, int, int, int]:
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    minx, miny, maxx, maxy = w, h, 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 8 or (r + g + b) > 95:
                found = True
                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x)
                maxy = max(maxy, y)
    if not found:
        return (0, 0, w, h)
    return (minx, miny, maxx + 1, maxy + 1)


def process(name: str) -> None:
    path = BASE / name
    im = Image.open(path)
    im = flood_transparent(im)
    im = im.crop(content_bbox(im))
    im.save(path, optimize=True)
    print(f"{name} -> {im.size} {im.mode}")


if __name__ == "__main__":
    for filename in NAMES:
        process(filename)
