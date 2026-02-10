from __future__ import annotations

import argparse
from pathlib import Path

# ВАЖНО: используем абсолютные импорты, чтобы код корректно работал
# как в виде пакета (python -m src.app), так и внутри собранного PyInstaller .app.
from src.batch_processor import BatchProcessor
from src.gui import run_gui
from src.models import CompressionMode, CompressionSettings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Пакетное сжатие изображений (GUI по умолчанию)."
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        help="Исходная папка с изображениями (для CLI‑режима).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Папка для сохранения сжатых изображений (для CLI‑режима).",
    )
    parser.add_argument(
        "--mode",
        choices=[CompressionMode.BY_QUALITY.value, CompressionMode.BY_TARGET_SIZE.value],
        default=CompressionMode.BY_TARGET_SIZE.value,
        help="Режим сжатия: by_quality или by_target_size.",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=85,
        help="Качество JPEG (для режима by_quality).",
    )
    parser.add_argument(
        "--target-size-kb",
        type=int,
        default=120,
        help="Целевой размер файла в КБ (для режима by_target_size).",
    )
    parser.add_argument(
        "--no-convert-to-jpeg",
        action="store_true",
        help="Не конвертировать изображения в JPEG (оставлять исходный формат, если возможно).",
    )
    parser.add_argument(
        "--no-keep-structure",
        action="store_true",
        help="Не сохранять структуру подпапок (складывать все файлы в одну папку).",
    )
    parser.add_argument(
        "--max-long-edge",
        type=int,
        default=1600,
        metavar="PX",
        help="Максимальный размер длинной стороны в пикселях (по умолчанию 1600). 0 — без ограничения.",
    )

    return parser.parse_args()


def run_cli(
    input_dir: Path,
    output_dir: Path,
    settings: CompressionSettings,
    max_long_edge_px: int | None = None,
) -> None:
    processor = BatchProcessor(
        input_dir=input_dir,
        output_dir=output_dir,
        settings=settings,
        max_long_edge_px=max_long_edge_px or getattr(
            settings, "max_long_edge_px", None
        ),
    )

    def progress_cb(progress) -> None:
        # Простой текстовый прогресс для терминала.
        status = f"{progress.current_index}/{progress.total_files}: {progress.current_file.name}"
        if progress.result and progress.result.succeeded:
            status += f" (x{progress.result.compression_ratio:.2f})"
        else:
            status += " (ошибка)"
        print(status)

    stats = processor.run(progress_callback=progress_cb)
    print(
        "\nГотово:",
        f"обработано={stats.processed_files},",
        f"ошибок={stats.failed_files},",
        f"среднее_сжатие={stats.average_ratio:.2f}x",
    )


def main() -> None:
    args = parse_args()

    # Если не указаны input/output, запускаем GUI.
    if args.input is None or args.output is None:
        run_gui()
        return

    input_dir: Path = args.input.expanduser()
    output_dir: Path = args.output.expanduser()

    if not input_dir.is_dir():
        raise SystemExit(f"Исходная папка не найдена: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    mode = (
        CompressionMode.BY_QUALITY
        if args.mode == CompressionMode.BY_QUALITY.value
        else CompressionMode.BY_TARGET_SIZE
    )

    max_long_edge = args.max_long_edge if args.max_long_edge > 0 else None

    settings = CompressionSettings(
        mode=mode,
        quality=args.quality,
        target_size_kb=args.target_size_kb,
        convert_to_jpeg=not args.no_convert_to_jpeg,
        keep_structure=not args.no_keep_structure,
        max_long_edge_px=max_long_edge,
    )

    run_cli(
        input_dir=input_dir,
        output_dir=output_dir,
        settings=settings,
        max_long_edge_px=max_long_edge,
    )


if __name__ == "__main__":
    main()

