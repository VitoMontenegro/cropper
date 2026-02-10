from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterable, Optional

from .image_compressor import ImageCompressor
from .models import BatchProgress, BatchStats, CompressionResult, CompressionSettings


ProgressCallback = Callable[[BatchProgress], None]


class BatchProcessor:
    """
    Пакетная обработка изображений.

    SRP: отвечает за обход файловой системы и вызовы ImageCompressor.
    Не знает о GUI, только о колбэке прогресса.
    """

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        settings: CompressionSettings,
        max_long_edge_px: int | None = None,
    ) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.settings = settings
        self.max_long_edge_px = max_long_edge_px

    def run(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        stop_flag: Optional[object] = None,
    ) -> BatchStats:
        """
        Запускает обработку всех изображений.

        stop_flag — объект с методом is_set() (например, threading.Event),
        чтобы можно было мягко прервать процесс.
        """

        stats = BatchStats()
        compressor = ImageCompressor(
            self.settings, max_long_edge_px=self.max_long_edge_px
        )

        files = list(self._iter_image_files())
        stats.total_files = len(files)

        if stats.total_files == 0:
            return stats

        for index, input_path in enumerate(files, start=1):
            if _should_stop(stop_flag):
                break

            # Расчёт путей вывода
            rel_path = input_path.relative_to(self.input_dir)
            if not self.settings.keep_structure:
                rel_path = Path(rel_path.name)

            output_path = self._build_output_path(rel_path)

            result = self._process_single(
                compressor=compressor,
                input_path=input_path,
                output_path=output_path,
                stats=stats,
            )

            progress = BatchProgress(
                current_index=index,
                total_files=stats.total_files,
                current_file=input_path,
                result=result,
                stats=stats,
            )

            if progress_callback is not None:
                progress_callback(progress)

        return stats

    def _iter_image_files(self) -> Iterable[Path]:
        """
        Рекурсивно перечисляет изображения в исходной директории.
        """

        valid_ext = {".jpg", ".jpeg", ".png"}

        for root, _, files in os.walk(self.input_dir):
            root_path = Path(root)
            for name in files:
                ext = Path(name).suffix.lower()
                if ext in valid_ext:
                    yield root_path / name

    def _build_output_path(self, rel_path: Path) -> Path:
        """
        Формирует путь для сохранения сжатого файла.

        Если включена конвертация в JPEG, то расширение меняется на .jpg.
        """

        if self.settings.convert_to_jpeg:
            stem = rel_path.stem
            rel_path = rel_path.with_name(f"{stem}.jpg")

        return self.output_dir / rel_path

    def _process_single(
        self,
        compressor: ImageCompressor,
        input_path: Path,
        output_path: Path,
        stats: BatchStats,
    ) -> CompressionResult:
        """
        Обрабатывает один файл и обновляет агрегированную статистику.
        """

        stats.total_files = max(stats.total_files, 1)

        result = compressor.compress(input_path=input_path, output_path=output_path)

        if result.succeeded:
            stats.processed_files += 1
            stats.bytes_before += result.original_size
            stats.bytes_after += result.compressed_size
            if result.reached_min_quality and result.compressed_size > (
                self.settings.target_size_kb * 1024
            ):
                stats.unable_to_meet_target += 1
        else:
            stats.failed_files += 1

        return result


def _should_stop(stop_flag: Optional[object]) -> bool:
    """
    Универсальная проверка флага остановки без жёсткой привязки к threading.Event.
    """

    if stop_flag is None:
        return False

    is_set = getattr(stop_flag, "is_set", None)
    if callable(is_set):
        try:
            return bool(is_set())
        except Exception:
            return False

    return False

