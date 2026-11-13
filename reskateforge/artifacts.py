"""Safe file operations and tiny generated icon assets (stdlib only)."""

from __future__ import annotations

import json
import re
import shutil
import struct
import zlib
from pathlib import Path


NAME = re.compile(r"^[A-Za-z0-9_]+$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
WINDOWS_PROGRAM_EXTENSIONS = {
    ".exe", ".dll", ".sys", ".scr", ".com", ".cpl", ".msi",
    ".msp", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe",
    ".js", ".jse", ".wsf", ".wsh", ".hta", ".lnk", ".pif", ".reg",
}


def json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_inside(root: Path, path: Path) -> Path:
    """Resolve a path and ensure it stays below root (including symlinks)."""
    root = root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path escapes project: {path}")
    return resolved


def copy_tree(source: Path, target: Path) -> list[str]:
    """Copy regular files only, rejecting symlinks. Destination must be absent."""
    if target.exists():
        raise FileExistsError(f"Destination exists: {target}")
    if not source.is_dir():
        raise NotADirectoryError(source)
    paths = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlink not accepted: {path}")
        if path.is_file():
            rel = path.relative_to(source)
            paths.append(str(rel).replace("\\", "/"))
    target.mkdir(parents=True)
    for name in paths:
        dst = target / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, dst)
    return paths


FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "_": ["00000", "00000", "00000", "00000", "00000", "00000", "11111"],
    " ": ["00000"] * 7,
}


def make_icon(path: Path, initials: str = "RS") -> None:
    """Generate an actual 256x256 PNG; no third-party imaging dependency."""
    width = height = 256
    pixels = bytearray()
    initials = "".join(c for c in initials.upper() if c in FONT)[:3] or "RS"
    char_size, spacing = 13, 11
    total = len(initials) * 5 * char_size + (len(initials) - 1) * spacing
    ox, oy = (width - total) // 2, 78
    for y in range(height):
        pixels.append(0)  # PNG filter 0
        for x in range(width):
            glow = max(0, 70 - abs(x - 130) // 3 - abs(y - 118) // 4)
            rgb = (17 + glow // 4, 10 + glow // 6, 40 + glow)
            if 20 < y < 236 and (x in (20, 21, 234, 235)):
                rgb = (103, 87, 190)
            if 20 < x < 236 and (y in (20, 21, 234, 235)):
                rgb = (103, 87, 190)
            if 181 <= y < 188 and 48 <= x < 208:
                rgb = (53, 200, 227)
            for idx, letter in enumerate(initials):
                start = ox + idx * (5 * char_size + spacing)
                if start <= x < start + 5 * char_size and oy <= y < oy + 7 * char_size:
                    gx, gy = (x - start) // char_size, (y - oy) // char_size
                    if FONT[letter][gy][gx] == "1":
                        rgb = (224, 217, 255)
            pixels.extend(rgb)
    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(pixels), 8)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
