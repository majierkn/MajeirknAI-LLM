#!/usr/bin/env python3
"""Gera os icones PNG da interface web sem dependencias externas.

Uso: python scripts/make_icons.py
Saida: majeirkn/ui/icons/icon-192.png e icon-512.png
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

# Paleta da Majeirkn AI (tons escuros com ciano).
BG_TOP = (23, 37, 64)
BG_BOTTOM = (11, 18, 32)
GLOW = (34, 211, 238)
GLYPH = (241, 245, 249)

SUPERSAMPLE = 2  # 2x2 amostras por pixel, so para suavizar as bordas


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def write_png(path: Path, width: int, height: int, rows: list[bytes]) -> None:
    """Escreve um PNG RGBA de 8 bits a partir de linhas RGBA ja prontas."""
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    payload = b"".join(b"\x00" + row for row in rows)
    content = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(payload, 9))
        + _chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _bg_color(nx: float, ny: float) -> tuple[float, float, float]:
    """Gradiente vertical com brilho suave no centro."""
    base = tuple(
        BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * ny for i in range(3)
    )
    dist = ((nx - 0.5) ** 2 + (ny - 0.5) ** 2) * 4.0  # 0 no centro, 1 na borda
    strength = max(0.0, 1.0 - dist) * 0.16
    return tuple(base[i] + (GLOW[i] - base[i]) * strength for i in range(3))


def _rounded_square(
    x: float, y: float, size: float, radius: float
) -> float:
    """Cobertura de um quadrado de cantos arredondados (0 a 1)."""
    cx = min(max(x, radius), size - radius)
    cy = min(max(y, radius), size - radius)
    dx, dy = x - cx, y - cy
    dist = (dx * dx + dy * dy) ** 0.5
    if dist >= radius:
        return 0.0
    return min(1.0, max(0.0, (radius - dist) / 1.5))


# Segmentos do "M": (x1, y1, x2, y2) em fracao do tamanho.
M_SEGMENTS = [
    (0.42, 0.30, 0.42, 0.70),  # haste esquerda
    (0.58, 0.30, 0.58, 0.70),  # haste direita
    (0.42, 0.30, 0.50, 0.50),  # diagonal esquerda
    (0.50, 0.50, 0.58, 0.30),  # diagonal direita
]


def _glyph_coverage(x: float, y: float, size: float) -> float:
    """Cobertura do M: espessura proporcional ao tamanho."""
    half_width = size * 0.026
    for x1, y1, x2, y2 in M_SEGMENTS:
        ax, ay = x1 * size, y1 * size
        bx, by = x2 * size, y2 * size
        vx, vy = bx - ax, by - ay
        length_sq = vx * vx + vy * vy
        if length_sq == 0:
            continue
        t = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / length_sq))
        px, py = ax + t * vx, ay + t * vy
        dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        if dist < half_width:
            return 1.0
    return 0.0


def render(size: int) -> list[bytes]:
    """Renderiza o icone em `size` x `size` pixels RGBA."""
    rows: list[bytes] = []
    step = 1.0 / SUPERSAMPLE
    for py in range(size):
        row = bytearray()
        for px in range(size):
            r = g = b = alpha = 0.0
            for sy in range(SUPERSAMPLE):
                for sx in range(SUPERSAMPLE):
                    x = px + (sx + 0.5) * step
                    y = py + (sy + 0.5) * step
                    shape = _rounded_square(x, y, size, size * 0.22)
                    if shape == 0:
                        continue
                    color = _bg_color(x / size, y / size)
                    glyph = _glyph_coverage(x, y, size)
                    rr = color[0] + (GLYPH[0] - color[0]) * glyph
                    gg = color[1] + (GLYPH[1] - color[1]) * glyph
                    bb = color[2] + (GLYPH[2] - color[2]) * glyph
                    r += rr * shape
                    g += gg * shape
                    b += bb * shape
                    alpha += shape
            samples = SUPERSAMPLE * SUPERSAMPLE
            row += bytes(
                (
                    min(255, round(r / samples)),
                    min(255, round(g / samples)),
                    min(255, round(b / samples)),
                    min(255, round(alpha / samples)),
                )
            )
        rows.append(bytes(row))
    return rows


def main() -> int:
    ui_dir = Path(__file__).resolve().parent.parent / "majeirkn" / "ui" / "icons"
    for size in (192, 512):
        write_png(ui_dir / f"icon-{size}.png", size, size, render(size))
    print(f"icones gerados em {ui_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
