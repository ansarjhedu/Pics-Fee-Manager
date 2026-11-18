"""Build the desktop icon from the college seal."""

from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QImage

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "pics-seal.png"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def clear_edge_white(image: QImage) -> QImage:
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()
    seen = bytearray(width * height)
    stack = [(x, 0) for x in range(width)]
    stack += [(x, height - 1) for x in range(width)]
    stack += [(0, y) for y in range(height)]
    stack += [(width - 1, y) for y in range(height)]
    clear = QColor(0, 0, 0, 0)
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        index = y * width + x
        if seen[index]:
            continue
        seen[index] = 1
        color = image.pixelColor(x, y)
        if color.red() < 246 or color.green() < 246 or color.blue() < 246:
            continue
        image.setPixelColor(x, y, clear)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return image


def fitted(source: QImage, size: int) -> QImage:
    canvas = QImage(size, size, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    from PySide6.QtGui import QPainter

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawImage(x, y, scaled)
    painter.end()
    return canvas


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(images: list[tuple[int, bytes]], dest: Path) -> None:
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    entries = b""
    payload = b""
    offset = 6 + 16 * count
    for size, data in images:
        stored = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", stored, stored, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)
    dest.write_bytes(header + entries + payload)


def main() -> None:
    source = clear_edge_white(QImage(str(SOURCE)))
    if source.isNull():
        raise SystemExit("The logo could not be opened.")
    master = fitted(source, 256)
    master.save(str(ROOT / "pics-logo.png"))
    images = []
    for size in SIZES:
        frame = master if size == 256 else fitted(source, size)
        images.append((size, png_bytes(frame)))
    write_ico(images, ROOT / "pics-fee.ico")
    print("wrote", ROOT / "pics-fee.ico", (ROOT / "pics-fee.ico").stat().st_size)


if __name__ == "__main__":
    main()
