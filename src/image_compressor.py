from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageOps

from .models import (
    BatchStats,
    CompressionMode,
    CompressionResult,
    CompressionSettings,
)


class ImageCompressor:
    """
    Класс, инкапсулирующий логику сжатия одного изображения.

    SRP: отвечает только за преобразование одного файла, без обхода директорий и GUI.
    """

    def __init__(
        self,
        settings: CompressionSettings,
        max_long_edge_px: int | None = None,
    ) -> None:
        self.settings = settings
        self._max_long_edge_px = max_long_edge_px

    def compress(
        self,
        input_path: Path,
        output_path: Path,
    ) -> CompressionResult:
        """
        Унифицированная точка входа: выбирает стратегию в зависимости от режима.
        """

        if self.settings.mode == CompressionMode.BY_QUALITY:
            return self.compress_with_quality(
                input_path=input_path,
                output_path=output_path,
                quality=self.settings.quality,
            )

        return self.compress_to_target_size(
            input_path=input_path,
            output_path=output_path,
            target_size_kb=self.settings.target_size_kb,
            min_quality=self.settings.min_quality,
            max_quality=self.settings.max_quality,
        )

    def compress_with_quality(
        self,
        input_path: Path,
        output_path: Path,
        quality: int,
    ) -> CompressionResult:
        """
        Сжатие с фиксированным качеством.

        Используется как отдельный режим и как вспомогательный шаг в бинарном поиске.
        """

        original_size = _safe_getsize(input_path)

        try:
            img, fmt = self._prepare_image(input_path)
            data, compressed_size = self._save_to_bytes(
                img, fmt=fmt, quality=quality
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(data)

            return CompressionResult(
                input_path=input_path,
                output_path=output_path,
                original_size=original_size,
                compressed_size=compressed_size,
                succeeded=True,
                reached_min_quality=False,
            )
        except Exception as exc:  # KISS: единый перехват, логика выше
            return CompressionResult(
                input_path=input_path,
                output_path=output_path,
                original_size=original_size,
                compressed_size=original_size,
                succeeded=False,
                reached_min_quality=False,
                error=str(exc),
            )

    def compress_to_target_size(
        self,
        input_path: Path,
        output_path: Path,
        target_size_kb: int,
        min_quality: int,
        max_quality: int,
        max_iterations: int = 8,
    ) -> CompressionResult:
        """
        Сжатие до целевого размера файла (примерно target_size_kb КБ)
        с использованием бинарного поиска по качеству.
        """

        original_size = _safe_getsize(input_path)
        target_bytes = max(target_size_kb, 1) * 1024

        try:
            img, fmt = self._prepare_image(input_path)

            # Если файл и так меньше цели — можно просто скопировать как есть.
            # Это бережно к качеству и соответствует KISS.
            if original_size > 0 and original_size <= target_bytes:
                data, compressed_size = self._save_to_bytes(
                    img, fmt=fmt, quality=max_quality
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(data)
                return CompressionResult(
                    input_path=input_path,
                    output_path=output_path,
                    original_size=original_size,
                    compressed_size=compressed_size,
                    succeeded=True,
                    reached_min_quality=False,
                )

            # Бинарный поиск по качеству.
            low = min_quality
            high = max_quality
            best_data: bytes | None = None
            best_size: int = original_size
            best_quality: int | None = None

            for _ in range(max_iterations):
                if low > high:
                    break

                mid = (low + high) // 2
                data, size = self._save_to_bytes(img, fmt=fmt, quality=mid)

                if size <= target_bytes:
                    # Нашли вариант, который укладывается в размер:
                    # пытаемся улучшить качество (увеличить quality).
                    best_data = data
                    best_size = size
                    best_quality = mid
                    low = mid + 1
                else:
                    # Слишком большой размер — уменьшаем качество.
                    high = mid - 1

            reached_min_quality = False

            if best_data is None:
                # Не удалось уложиться в цель даже при бинарном поиске.
                # Пробуем прямой минимум качества как последний шанс.
                data, size = self._save_to_bytes(
                    img, fmt=fmt, quality=min_quality
                )
                best_data = data
                best_size = size
                best_quality = min_quality
                reached_min_quality = True

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(best_data)

            # Если даже при минимальном качестве превышаем цель,
            # помечаем это в результате.
            if best_size > target_bytes and best_quality == min_quality:
                reached_min_quality = True

            return CompressionResult(
                input_path=input_path,
                output_path=output_path,
                original_size=original_size,
                compressed_size=best_size,
                succeeded=True,
                reached_min_quality=reached_min_quality,
            )
        except Exception as exc:
            return CompressionResult(
                input_path=input_path,
                output_path=output_path,
                original_size=original_size,
                compressed_size=original_size,
                succeeded=False,
                reached_min_quality=False,
                error=str(exc),
            )

    # Внутренние утилиты

    def _prepare_image(self, input_path: Path) -> Tuple[Image.Image, str]:
        """
        Открывает изображение и выбирает целевой формат.

        По умолчанию стараемся сохранять/конвертировать в JPEG ради лучшего сжатия.
        """

        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img)
        img_format = (img.format or "JPEG").upper()

        if self.settings.convert_to_jpeg:
            target_fmt = "JPEG"
        else:
            target_fmt = img_format

        # JPEG не поддерживает альфа‑канал, приводим к RGB при необходимости.
        if target_fmt == "JPEG" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Масштабируем слишком большие изображения до max_long_edge_px по большей стороне.
        max_edge = self._max_long_edge_px or getattr(
            self.settings, "max_long_edge_px", None
        )
        if max_edge is not None and max_edge > 0:
            width, height = img.size
            long_edge = max(width, height)
            if long_edge > max_edge:
                scale = max_edge / float(long_edge)
                new_size = (int(width * scale), int(height * scale))
                # LANCZOS даёт хорошее качество уменьшения для фото.
                img = img.resize(new_size, Image.LANCZOS)

        return img, target_fmt

    @staticmethod
    def _save_to_bytes(
        img: Image.Image,
        fmt: str,
        quality: int,
    ) -> Tuple[bytes, int]:
        """
        Сохраняет изображение в память и возвращает байты и размер.
        """

        buffer = io.BytesIO()
        save_kwargs = {}

        if fmt.upper() == "JPEG":
            save_kwargs.update(
                {
                    "optimize": True,
                    "quality": int(quality),
                    "progressive": True,
                }
            )

        img.save(buffer, format=fmt, **save_kwargs)
        data = buffer.getvalue()
        return data, len(data)


def _safe_getsize(path: Path) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0

