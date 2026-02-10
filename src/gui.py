from __future__ import annotations

import queue
import traceback
import threading
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .batch_processor import BatchProcessor
from .models import BatchProgress, CompressionMode, CompressionSettings


class ImageCompressorApp(tk.Tk):
    """
    Минимальное десктоп‑приложение для пакетного сжатия изображений.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("Image Compressor")

        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._progress_queue: "queue.Queue[BatchProgress | tuple[str, object]]" = (
            queue.Queue()
        )

        self._build_ui()
        self._poll_progress_queue()

    # UI

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        # Исходная папка
        tk.Label(self, text="Исходная папка:").grid(
            row=0, column=0, sticky="w", padx=8, pady=4
        )
        self.entry_input = tk.Entry(self)
        self.entry_input.grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        tk.Button(self, text="Обзор…", command=self._browse_input).grid(
            row=0, column=2, sticky="ew", padx=8, pady=4
        )

        # Выходная папка
        tk.Label(self, text="Выходная папка:").grid(
            row=1, column=0, sticky="w", padx=8, pady=4
        )
        self.entry_output = tk.Entry(self)
        self.entry_output.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        tk.Button(self, text="Обзор…", command=self._browse_output).grid(
            row=1, column=2, sticky="ew", padx=8, pady=4
        )

        # Режим
        mode_frame = tk.LabelFrame(self, text="Режим сжатия")
        mode_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=4)
        mode_frame.columnconfigure(1, weight=1)

        self.mode_var = tk.StringVar(value=CompressionMode.BY_TARGET_SIZE.value)
        tk.Radiobutton(
            mode_frame,
            text="По размеру (КБ)",
            variable=self.mode_var,
            value=CompressionMode.BY_TARGET_SIZE.value,
            command=self._update_mode_state,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=2)

        tk.Radiobutton(
            mode_frame,
            text="По качеству (%)",
            variable=self.mode_var,
            value=CompressionMode.BY_QUALITY.value,
            command=self._update_mode_state,
        ).grid(row=0, column=1, sticky="w", padx=8, pady=2)

        # Параметры качества
        quality_frame = tk.Frame(mode_frame)
        quality_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        quality_frame.columnconfigure(1, weight=1)

        tk.Label(quality_frame, text="Качество JPEG:").grid(
            row=0, column=0, sticky="w"
        )
        self.quality_scale = tk.Scale(
            quality_frame,
            from_=40,
            to=95,
            orient=tk.HORIZONTAL,
        )
        self.quality_scale.set(85)
        self.quality_scale.grid(row=0, column=1, sticky="ew", padx=4)

        # Параметры размера
        tk.Label(quality_frame, text="Целевой размер (КБ):").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        self.entry_target_size = tk.Entry(quality_frame)
        self.entry_target_size.insert(0, "120")
        self.entry_target_size.grid(
            row=1, column=1, sticky="ew", padx=4, pady=(4, 0)
        )

        # Максимальный размер изображения
        tk.Label(quality_frame, text="Макс. длинная сторона (px):").grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )
        self.entry_max_long_edge = tk.Entry(quality_frame, width=8)
        self.entry_max_long_edge.insert(0, "1600")
        self.entry_max_long_edge.grid(
            row=2, column=1, sticky="w", padx=4, pady=(4, 0)
        )

        # Дополнительные опции
        options_frame = tk.LabelFrame(self, text="Опции")
        options_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

        self.keep_structure_var = tk.BooleanVar(value=True)
        self.convert_to_jpeg_var = tk.BooleanVar(value=True)

        tk.Checkbutton(
            options_frame,
            text="Сохранять структуру папок",
            variable=self.keep_structure_var,
        ).grid(row=0, column=0, sticky="w", padx=4, pady=2)

        tk.Checkbutton(
            options_frame,
            text="Конвертировать в JPEG",
            variable=self.convert_to_jpeg_var,
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        # Кнопки управления
        controls_frame = tk.Frame(self)
        controls_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=4)
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)

        self.btn_start = tk.Button(
            controls_frame,
            text="Старт",
            command=self._safe_on_start,
        )
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=4)

        self.btn_stop = tk.Button(
            controls_frame,
            text="Стоп",
            command=self._on_stop,
            state="disabled",
        )
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=4)

        # Прогресс
        progress_frame = tk.Frame(self)
        progress_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

        self.progress_bar = ttk.Progressbar(
            progress_frame, mode="determinate", maximum=1.0
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)

        self.status_label = tk.Label(self, text="Готово.")
        self.status_label.grid(
            row=6, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8)
        )

        self._update_mode_state()

    # Обработчики UI

    def _browse_input(self) -> None:
        directory = filedialog.askdirectory(title="Выберите исходную папку")
        if directory:
            self.entry_input.delete(0, tk.END)
            self.entry_input.insert(0, directory)

    def _browse_output(self) -> None:
        directory = filedialog.askdirectory(title="Выберите выходную папку")
        if directory:
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, directory)

    def _update_mode_state(self) -> None:
        mode = self.mode_var.get()
        if mode == CompressionMode.BY_QUALITY.value:
            self.quality_scale.configure(state="normal")
            self.entry_target_size.configure(state="disabled")
        else:
            self.quality_scale.configure(state="disabled")
            self.entry_target_size.configure(state="normal")

    # Запуск / остановка обработки

    def _show_dialog(self, title: str, message: str, dialog_type: str = "error") -> None:
        """Показывает диалог поверх окна (важно для macOS)."""
        self.lift()
        self.attributes("-topmost", True)
        self.update_idletasks()
        if dialog_type == "warning":
            messagebox.showwarning(title, message)
        else:
            messagebox.showerror(title, message)
        self.attributes("-topmost", False)

    def _show_error(self, title: str, message: str) -> None:
        """Показывает диалог ошибки поверх окна."""
        self._show_dialog(title, message, "error")

    def _safe_on_start(self) -> None:
        """Обёртка для отлова всех исключений при нажатии Старт."""
        try:
            self._on_start()
        except Exception:
            self._show_error("Ошибка (Старт)", traceback.format_exc())

    def _on_start(self) -> None:
        input_str = (self.entry_input.get() or "").strip()
        output_str = (self.entry_output.get() or "").strip()

        if not input_str:
            self._show_error("Ошибка", "Укажите исходную папку с изображениями.")
            return

        if not output_str:
            self._show_error("Ошибка", "Укажите выходную папку.")
            return

        input_dir = Path(input_str).expanduser()
        output_dir = Path(output_str).expanduser()

        if not input_dir.is_dir():
            self._show_error(
                "Ошибка",
                f"Исходная папка не найдена:\n{input_dir}",
            )
            return

        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self._show_error(
                    "Ошибка", f"Не удалось создать выходную папку:\n{exc}"
                )
                return

        mode = (
            CompressionMode.BY_QUALITY
            if self.mode_var.get() == CompressionMode.BY_QUALITY.value
            else CompressionMode.BY_TARGET_SIZE
        )

        try:
            target_size_kb = int(self.entry_target_size.get() or "120")
        except ValueError:
            self._show_error(
                "Ошибка", "Целевой размер должен быть целым числом (КБ)."
            )
            return

        max_long_edge_px = None
        raw_edge = (self.entry_max_long_edge.get() or "").strip()
        if raw_edge:
            try:
                value = int(raw_edge)
                if value > 0:
                    max_long_edge_px = value
            except ValueError:
                self._show_error(
                    "Ошибка",
                    "Максимальная длинная сторона должна быть целым числом (px).",
                )
                return

        settings = CompressionSettings(
            mode=mode,
            quality=int(self.quality_scale.get()),
            target_size_kb=target_size_kb,
            keep_structure=self.keep_structure_var.get(),
            convert_to_jpeg=self.convert_to_jpeg_var.get(),
        )

        processor = BatchProcessor(
            input_dir=input_dir,
            output_dir=output_dir,
            settings=settings,
            max_long_edge_px=max_long_edge_px,
        )

        self._disable_controls()
        self.status_label.config(text="Запуск обработки…")
        self.progress_bar["value"] = 0
        self._stop_event.clear()

        def worker() -> None:
            try:
                stats = processor.run(
                    progress_callback=self._progress_queue.put,
                    stop_flag=self._stop_event,
                )
                self._progress_queue.put(("finished", stats))
            except Exception as exc:  # noqa: BLE001
                self._progress_queue.put(("error", traceback.format_exc()))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _on_stop(self) -> None:
        self._stop_event.set()
        self.status_label.config(text="Остановка по запросу пользователя…")

    def _disable_controls(self) -> None:
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        for widget in (
            self.entry_input,
            self.entry_output,
        ):
            widget.config(state="disabled")

    def _enable_controls(self) -> None:
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        for widget in (
            self.entry_input,
            self.entry_output,
        ):
            widget.config(state="normal")

    # Обработка очереди прогресса (из фонового потока)

    def _poll_progress_queue(self) -> None:
        try:
            while True:
                item = self._progress_queue.get_nowait()
                try:
                    self._handle_progress_item(item)
                except Exception:
                    self._show_error("Ошибка (обработка очереди)", traceback.format_exc())
        except queue.Empty:
            pass

        self.after(100, self._poll_progress_queue)

    def _handle_progress_item(self, item: object) -> None:
        if isinstance(item, tuple) and item and item[0] == "finished":
            stats = item[1]
            self._enable_controls()
            text = (
                f"Готово. Обработано: {stats.processed_files}, "
                f"ошибок: {stats.failed_files}, "
                f"среднее сжатие: {stats.average_ratio:.2f}x."
            )
            self.status_label.config(text=text)
            if stats.total_files == 0:
                self._show_dialog(
                    "Нет изображений",
                    "В указанной папке не найдено изображений (jpg, jpeg, png).",
                    "warning",
                )
            return

        if isinstance(item, tuple) and item and item[0] == "error":
            message = str(item[1])
            self._enable_controls()
            self._show_error("Ошибка", message)
            self.status_label.config(text="Ошибка обработки.")
            return

        if isinstance(item, BatchProgress):
            self._update_progress(item)

    def _update_progress(self, progress: BatchProgress) -> None:
        self.progress_bar["maximum"] = max(progress.total_files, 1)
        self.progress_bar["value"] = progress.current_index

        file_name = progress.current_file.name
        if progress.result and progress.result.succeeded:
            ratio = progress.result.compression_ratio
            status = (
                f"{progress.current_index}/{progress.total_files}: {file_name} "
                f"(x{ratio:.2f})"
            )
        else:
            status = f"{progress.current_index}/{progress.total_files}: {file_name} (ошибка)"

        self.status_label.config(text=status)


def run_gui() -> None:
    app = ImageCompressorApp()
    app.mainloop()

