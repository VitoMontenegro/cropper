from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class CompressionMode(str, Enum):
    """Режим сжатия изображений."""

    BY_QUALITY = "by_quality"
    BY_TARGET_SIZE = "by_target_size"


@dataclass
class CompressionSettings:
    """
    Настройки сжатия одного изображения.

    KISS: храним только параметры, связанные с качеством и именованием.
    Пути к файлам/директориям задаются на уровне BatchProcessor/GUI.
    """

    mode: CompressionMode = CompressionMode.BY_TARGET_SIZE
    quality: int = 85
    target_size_kb: int = 120
    min_quality: int = 40
    max_quality: int = 95
    convert_to_jpeg: bool = True
    keep_structure: bool = True


@dataclass
class CompressionResult:
    """Результат сжатия одного файла."""

    input_path: Path
    output_path: Path
    original_size: int
    compressed_size: int
    succeeded: bool
    reached_min_quality: bool = False
    error: Optional[str] = None

    @property
    def compression_ratio(self) -> float:
        """
        Отношение размера после/до.

        Значение < 1 означает уменьшение размера.
        """

        if self.original_size <= 0:
            return 1.0
        return self.compressed_size / self.original_size


@dataclass
class BatchStats:
    """Агрегированная статистика пакетной обработки."""

    total_files: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    bytes_before: int = 0
    bytes_after: int = 0
    unable_to_meet_target: int = 0

    @property
    def average_ratio(self) -> float:
        if self.processed_files == 0 or self.bytes_before == 0:
            return 1.0
        return self.bytes_after / self.bytes_before


@dataclass
class BatchProgress:
    """
    Объект прогресса для колбэков GUI/CLI.

    SRP: это просто контейнер данных, без логики.
    """

    current_index: int
    total_files: int
    current_file: Path
    result: Optional[CompressionResult]
    stats: BatchStats

