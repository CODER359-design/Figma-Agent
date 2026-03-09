from __future__ import annotations

import asyncio
import os
import sys
import threading
from typing import Dict, Iterable, Literal, Tuple

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont
from tkinter import filedialog, messagebox

from dotenv import load_dotenv

load_dotenv()

BG_COLOR = "#090f1f"
CARD_COLOR = "#101a35"
ACCENT_COLOR = "#7b5bff"
MUTED_TEXT = "#8ca0d1"
PRIMARY_TEXT = "#f4f6ff"
LOG_BG = "#050b16"
SWITCH_OFF_COLOR = "#f6f7ff"
SWITCH_BUTTON_COLOR = "#e3e7ff"

LOG_COLORS: Dict[str, str] = {
    "info": "#6cb2ff",
    "success": "#66d19e",
    "warning": "#f7c948",
    "error": "#ff7b7b",
}


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#" + "".join(f"{component:02x}" for component in rgb)


def _blend_color(start: str, end: str, fraction: float) -> str:
    s = _hex_to_rgb(start)
    e = _hex_to_rgb(end)
    blended = tuple(int(s[i] + (e[i] - s[i]) * fraction) for i in range(3))
    return _rgb_to_hex(blended)


def _darken(color: str, delta: float = 0.15) -> str:
    rgb = _hex_to_rgb(color)
    darker = tuple(max(0, int(component * (1 - delta))) for component in rgb)
    return _rgb_to_hex(darker)


def _env_value(key: str, default: str = "") -> str:
    return os.getenv(key, default) or ""


class PipelineApp(ctk.CTk):
    """Premium desktop GUI with modern theme, icons, and async pipeline launch."""

    def __init__(self) -> None:
        ctk.set_default_color_theme("dark-blue")
        ctk.set_appearance_mode("dark")

        super().__init__()
        self.title("Figma → HTML/CSS Agent")
        self.geometry("1100x680")
        self.minsize(980, 640)
        self.configure(fg_color=BG_COLOR)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.loop_thread.start()
        self.pipeline_future: asyncio.Future[None] | None = None

        self.theme_var = ctk.StringVar(value="Dark")
        self.status_var = ctk.StringVar(value="Очікує запуску")

        self.token_var = ctk.StringVar(value=_env_value("FIGMA_TOKEN"))
        self.file_key_var = ctk.StringVar(value=_env_value("FIGMA_FILE_KEY"))
        self.node_id_var = ctk.StringVar(value=_env_value("FIGMA_NODE_ID"))
        self.normalized_var = ctk.StringVar()
        self.output_var = ctk.StringVar(value=_env_value("OUTPUT_DIR", "output"))
        self.trace_dir_var = ctk.StringVar(value=_env_value("TRACE_DIR", "traces"))
        self.dry_run_var = ctk.BooleanVar(value=False)
        self.trace_var = ctk.BooleanVar(value=True)
        self.assets_var = ctk.BooleanVar(value=True)

        self.icons = self._load_icons()
        self._color_jobs: Dict[ctk.CTkBaseClass, str] = {}
        self._current_colors: Dict[ctk.CTkBaseClass, str] = {}
        self._button_palettes: Dict[ctk.CTkBaseClass, Tuple[str, str]] = {}
        self._progress_visible = False
        self._form_layout_mode: Literal["columns", "stacked"] = "columns"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.viewport = ctk.CTkScrollableFrame(self, fg_color=BG_COLOR, corner_radius=0)
        self.viewport.grid(row=0, column=0, sticky="nsew")
        self.viewport.grid_columnconfigure(0, weight=1)
        self.viewport.grid_rowconfigure(0, weight=0)
        self.viewport.grid_rowconfigure(1, weight=3)
        self.viewport.grid_rowconfigure(2, weight=5)
        self.viewport.grid_rowconfigure(3, weight=0)

        self._build_header()
        self._build_form_card()
        self._build_log_card()
        self._build_footer()
        self.bind("<Configure>", self._handle_resize)
        self.after(50, self._apply_form_layout)

    # ------------------------------------------------------------------
    # UI BUILDERS
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self.viewport, fg_color=BG_COLOR)
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 12))
        header.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(header, fg_color=CARD_COLOR, corner_radius=26)
        hero.grid(row=0, column=0, sticky="ew", pady=(8, 6))
        hero.grid_columnconfigure(0, weight=1)
        hero.grid_rowconfigure(4, weight=0)

        top_row = ctk.CTkFrame(hero, fg_color=CARD_COLOR)
        top_row.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        top_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top_row, text="FIGMA OPS AGENT", text_color=MUTED_TEXT, font=("Inter", 12, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        controls = ctk.CTkFrame(top_row, fg_color=CARD_COLOR)
        controls.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(controls, text="Тема", text_color=MUTED_TEXT).pack(anchor="e")
        theme_switch = ctk.CTkSegmentedButton(
            controls,
            values=["Dark", "Light"],
            command=self._change_theme,
            variable=self.theme_var,
            font=("Inter", 12, "bold"),
        )
        theme_switch.pack(anchor="e", pady=(4, 0))

        ctk.CTkLabel(hero, text="Перетворюйте макети у код за хвилини", font=("Inter", 24, "bold"), text_color=PRIMARY_TEXT).grid(
            row=1, column=0, sticky="w", padx=24
        )
        ctk.CTkLabel(
            hero,
            text="Сучасний GUI із dry-run, трейси, експорт асетів та перемиканням тем.",
            text_color=MUTED_TEXT,
            font=("Inter", 14),
        ).grid(row=2, column=0, sticky="w", padx=24, pady=(4, 20))

        self.progress = ctk.CTkProgressBar(
            hero,
            height=8,
            corner_radius=6,
            progress_color=ACCENT_COLOR,
            fg_color="#0d1327",
        )
        self.progress.configure(mode="indeterminate")
        self.progress.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 20))
        self.progress.grid_remove()

    def _build_form_card(self) -> None:
        card = ctk.CTkFrame(self.viewport, fg_color=CARD_COLOR, corner_radius=28)
        card.grid(row=1, column=0, sticky="nsew", padx=28, pady=(2, 8))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(card, fg_color=CARD_COLOR)
        left.grid(row=0, column=0, sticky="nsew", padx=(32, 18), pady=32)
        left.grid_columnconfigure(0, weight=0)
        left.grid_columnconfigure(1, weight=1)
        left.grid_rowconfigure((0, 1, 2, 3, 4, 5), weight=0)

        right = ctk.CTkFrame(card, fg_color=CARD_COLOR)
        right.grid(row=0, column=1, sticky="nsew", padx=(18, 32), pady=32)
        right.grid_columnconfigure(0, weight=1, minsize=420)
        right.grid_rowconfigure((0, 1, 2, 3), weight=0)

        self.form_card = card
        self.left_panel = left
        self.right_panel = right

        self._add_entry(left, "Figma Token", self.token_var, placeholder="FIGMA_TOKEN", show="•")
        self._add_entry(left, "File Key", self.file_key_var, placeholder="FIGMA_FILE_KEY")
        self._add_entry(left, "Node ID", self.node_id_var, placeholder="Необов'язково")

        ctk.CTkLabel(left, text="Normalized JSON", text_color=MUTED_TEXT).grid(row=3, column=0, sticky="w", pady=(16, 4))
        normalized_entry = ctk.CTkEntry(left, textvariable=self.normalized_var, placeholder_text="output/normalized.json")
        normalized_entry.grid(row=3, column=1, sticky="ew", padx=(16, 0), pady=(12, 0))
        browse_btn = ctk.CTkButton(
            left,
            text="Browse",
            command=self._select_normalized,
            fg_color=ACCENT_COLOR,
            hover_color="#9d80ff",
        )
        browse_btn.grid(row=3, column=2, padx=(16, 0), pady=(12, 0))
        self._register_button_animation(browse_btn, ACCENT_COLOR, "#b68cff")

        self._add_entry(left, "Output Dir", self.output_var, row=4, placeholder="output")
        self._add_entry(left, "Trace Dir", self.trace_dir_var, row=5, placeholder="traces")

        ctk.CTkLabel(right, text="Опції запуску", text_color=MUTED_TEXT, font=("Inter", 13, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        toggles = ctk.CTkFrame(right, fg_color=CARD_COLOR)
        toggles.grid(row=1, column=0, sticky="nsew", pady=(8, 18))
        toggles.grid_columnconfigure(1, weight=1)

        switch_defs = (
            ("Dry run", "Запуск без LLM: лише normalized JSON та preview.html", self.dry_run_var),
            ("Record trace", "Зберегти JSON+HTML+CSS до Trace Dir", self.trace_var),
            ("Export assets", "Скачати всі зображення у output/assets", self.assets_var),
        )

        for idx, (label, hint, var) in enumerate(switch_defs):
            switch = ctk.CTkSwitch(
                toggles,
                text=label,
                variable=var,
                fg_color=SWITCH_OFF_COLOR,
                progress_color=ACCENT_COLOR,
                button_color=SWITCH_BUTTON_COLOR,
                button_hover_color=_darken(SWITCH_BUTTON_COLOR, 0.2),
                switch_width=64,
                switch_height=28,
            )
            switch.grid(row=idx, column=0, sticky="w", pady=(0 if idx == 0 else 12, 0))
            ctk.CTkLabel(
                toggles,
                text=hint,
                text_color=MUTED_TEXT,
                font=("Inter", 11),
                wraplength=260,
                justify="left",
            ).grid(row=idx, column=1, sticky="w", padx=(12, 0))

        self.run_button = ctk.CTkButton(
            right,
            text="Запустити",
            image=self.icons["play"],
            compound="left",
            fg_color=ACCENT_COLOR,
            hover_color="#9d80ff",
            corner_radius=16,
            height=50,
            width=0,
            command=self.run_pipeline,
        )
        self.run_button.grid(row=2, column=0, sticky="ew", pady=(6, 18))
        self._register_button_animation(self.run_button, ACCENT_COLOR, "#b68cff")

        helper = ctk.CTkLabel(
            right,
            text="Можна запускати dry-run на готовому normalized JSON без звернення до Figma API.",
            text_color=MUTED_TEXT,
            wraplength=340,
            justify="left",
        )
        helper.grid(row=3, column=0, sticky="ew", pady=(10, 0))

    def _build_log_card(self) -> None:
        log_card = ctk.CTkFrame(self.viewport, fg_color=CARD_COLOR, corner_radius=28)
        log_card.grid(row=2, column=0, sticky="nsew", padx=28, pady=(12, 20))
        log_card.grid_rowconfigure(1, weight=1)
        log_card.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(log_card, fg_color=CARD_COLOR)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16), padx=12)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Лог виконання", font=("Inter", 16, "bold"), text_color=PRIMARY_TEXT).grid(
            row=0, column=0, sticky="w"
        )
        self.status_icon = ctk.CTkLabel(header, text="", image=self.icons["idle"])
        self.status_icon.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.status_label = ctk.CTkLabel(header, textvariable=self.status_var, text_color=MUTED_TEXT)
        self.status_label.grid(row=0, column=2, sticky="e")

        self.log = ctk.CTkTextbox(
            log_card,
            fg_color=LOG_BG,
            text_color=PRIMARY_TEXT,
            corner_radius=20,
            font=("JetBrains Mono", 12),
        )
        self.log.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log.configure(state="disabled")
        self._configure_log_tags()

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self.viewport, fg_color=BG_COLOR)
        footer.grid(row=3, column=0, sticky="ew", padx=32, pady=(0, 28))
        ctk.CTkLabel(
            footer,
            text="Натисніть «Запустити», щоб згенерувати HTML/CSS або dry-run без LLM.",
            text_color=MUTED_TEXT,
        ).pack(anchor="w")

    # ------------------------------------------------------------------
    # CONFIG HELPERS
    # ------------------------------------------------------------------
    def _add_entry(
        self,
        parent: ctk.CTkFrame,
        label: str,
        variable: ctk.StringVar,
        row: int | None = None,
        placeholder: str = "",
        show: str | None = None,
    ) -> None:
        if row is None:
            row = parent.grid_size()[1]

        ctk.CTkLabel(parent, text=label, text_color=MUTED_TEXT).grid(row=row, column=0, sticky="w", pady=(0, 6))
        entry = ctk.CTkEntry(
            parent,
            textvariable=variable,
            placeholder_text=placeholder,
            show=show,
        )
        entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=(0, 12))

    def _select_normalized(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if filename:
            self.normalized_var.set(filename)

    def _configure_log_tags(self) -> None:
        for level, color in LOG_COLORS.items():
            self.log.tag_config(level, foreground=color)

    def _handle_resize(self, event: ctk.Event) -> None:  # type: ignore[override]
        if event.widget is self:
            self._apply_form_layout(event.width)

    def _apply_form_layout(self, width: int | None = None) -> None:
        if not hasattr(self, "form_card"):
            return
        if width is None or width <= 0:
            width = self.winfo_width()
        target_mode: Literal["columns", "stacked"] = "stacked" if width < 1180 else "columns"
        if target_mode == self._form_layout_mode:
            return

        if target_mode == "stacked":
            self.form_card.grid_columnconfigure(0, weight=1)
            self.form_card.grid_columnconfigure(1, weight=0)
            self.form_card.grid_rowconfigure(0, weight=1)
            self.form_card.grid_rowconfigure(1, weight=1)
            self.left_panel.grid_configure(row=0, column=0, padx=32, pady=(32, 16), sticky="nsew")
            self.right_panel.grid_configure(row=1, column=0, padx=32, pady=(0, 32), sticky="nsew")
        else:
            self.form_card.grid_columnconfigure(0, weight=1)
            self.form_card.grid_columnconfigure(1, weight=1)
            self.form_card.grid_rowconfigure(0, weight=1)
            self.form_card.grid_rowconfigure(1, weight=0)
            self.left_panel.grid_configure(row=0, column=0, padx=(32, 18), pady=32, sticky="nsew")
            self.right_panel.grid_configure(row=0, column=1, padx=(18, 32), pady=32, sticky="nsew")

        self._form_layout_mode = target_mode

    def _change_theme(self, value: str) -> None:
        mode = "dark" if value.lower() == "dark" else "light"
        ctk.set_appearance_mode(mode)
        for button, (base, _) in self._button_palettes.items():
            self._current_colors[button] = base
            button.configure(fg_color=base)

    # ------------------------------------------------------------------
    # PIPELINE EXECUTION (ASYNC)
    # ------------------------------------------------------------------
    def run_pipeline(self) -> None:
        token = self.token_var.get().strip()
        normalized = self.normalized_var.get().strip()
        if not token and not normalized:
            messagebox.showerror("Помилка", "Потрібен або Figma токен, або normalized JSON")
            return

        if self.pipeline_future and not self.pipeline_future.done():
            messagebox.showwarning("Очікуйте", "Поточний запуск ще триває")
            return

        frozen = getattr(sys, "frozen", False)

        args: list[str] = []
        if normalized:
            args.extend(["--normalized-input", normalized])
        else:
            file_key = self.file_key_var.get().strip()
            if not file_key:
                messagebox.showerror("Помилка", "Вкажіть FIGMA_FILE_KEY")
                return
            args.extend(["--file-key", file_key])
            node_id = self.node_id_var.get().strip()
            if node_id:
                args.extend(["--node-id", node_id])

        args.extend(["--output-dir", self.output_var.get().strip() or "output"])
        if self.dry_run_var.get():
            args.append("--dry-run")
        if self.trace_var.get():
            args.append("--record-trace")
            args.extend(["--trace-dir", self.trace_dir_var.get().strip() or "traces"])
        if self.assets_var.get():
            args.append("--export-assets")

        env = os.environ.copy()
        env.update(
            {
                "FIGMA_TOKEN": token,
                "FIGMA_FILE_KEY": self.file_key_var.get().strip(),
                "FIGMA_NODE_ID": self.node_id_var.get().strip(),
                "OUTPUT_DIR": self.output_var.get().strip() or "output",
                "TRACE_DIR": self.trace_dir_var.get().strip() or "traces",
            }
        )

        self._set_running(True)

        if frozen:
            self._append_log("\n▶ Запуск (in-process)\n", level="info")
            self.pipeline_future = asyncio.run_coroutine_threadsafe(
                self._run_inprocess_async(args, env), self.loop
            )
        else:
            cmd = [sys.executable, "-m", "src.main", *args]
            self._append_log(f"\n▶ Запуск: {' '.join(cmd)}\n", level="info")
            self.pipeline_future = asyncio.run_coroutine_threadsafe(
                self._run_pipeline_async(cmd, env), self.loop
            )

        self.pipeline_future.add_done_callback(self._handle_future_result)

    async def _run_inprocess_async(self, args: list[str], env: Dict[str, str]) -> None:
        def runner() -> tuple[int, str | None]:
            os.environ.update(env)
            from src import main as main_module

            parsed = main_module.parse_args(args)
            try:
                main_module.run_with_args(parsed)
                return 0, "✅ Готово"
            except Exception as exc:  # pragma: no cover
                return 1, f"Exception: {exc}"

        loop = asyncio.get_running_loop()
        code, message = await loop.run_in_executor(None, runner)
        if message:
            level = "success" if code == 0 else "error"
            self.after(0, lambda msg=message, lvl=level: self._append_log(msg + "\n", level=lvl))
        self.after(0, lambda: self._set_running(False, code == 0, code))

    def _handle_future_result(self, future: asyncio.Future[None]) -> None:
        try:
            future.result()
        except Exception as exc:  # pragma: no cover - UI error path
            self.after(0, lambda: self._on_pipeline_exception(exc))

    async def _run_pipeline_async(self, cmd: list[str], env: Dict[str, str]) -> None:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )

        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="ignore")
            level = self._detect_level(text)
            self.after(0, lambda t=text, lvl=level: self._append_log(t, lvl))

        code = await process.wait()
        self.after(0, lambda: self._finalize_run(code))

    def _finalize_run(self, return_code: int) -> None:
        success = return_code == 0
        level = "success" if success else "error"
        message = "✅ Готово" if success else f"❌ Помилка (код {return_code})"
        self._append_log(message + "\n", level=level)
        self._set_running(False, success, return_code)

    def _on_pipeline_exception(self, exc: Exception) -> None:
        self._append_log(f"Exception: {exc}\n", level="error")
        self._set_running(False, False, None)

    def _set_running(self, running: bool, success: bool | None = None, code: int | None = None) -> None:
        if running:
            self.run_button.configure(state="disabled", text="Запускається…", image=self.icons["spinner"])
            self.status_var.set("Виконання…")
            self.status_icon.configure(image=self.icons["spinner"])
            self._show_progress()
        else:
            self.run_button.configure(state="normal", text="Запустити", image=self.icons["play"])
            if success is True:
                self.status_var.set("Готово")
                self.status_icon.configure(image=self.icons["success"])
            elif success is False:
                reason = f"код {code}" if code is not None else "див. лог"
                self.status_var.set(f"Помилка ({reason})")
                self.status_icon.configure(image=self.icons["error"])
            else:
                self.status_var.set("Очікує запуску")
                self.status_icon.configure(image=self.icons["idle"])
            self._hide_progress()

    # ------------------------------------------------------------------
    # LOGGING
    # ------------------------------------------------------------------
    def _append_log(self, text: str, level: Literal["info", "success", "warning", "error"] = "info") -> None:
        tag = level if level in LOG_COLORS else "info"
        self.log.configure(state="normal")
        self.log.insert("end", text, (tag,))
        self.log.configure(state="disabled")
        self.log.see("end")

    @staticmethod
    def _detect_level(text: str) -> Literal["info", "success", "warning", "error"]:
        lowered = text.lower()
        if "error" in lowered or "traceback" in lowered or "exception" in lowered:
            return "error"
        if any(keyword in lowered for keyword in ("warning", "retry")):
            return "warning"
        if any(keyword in lowered for keyword in ("success", "ready", "done", "completed")):
            return "success"
        return "info"

    def _register_button_animation(self, button: ctk.CTkButton, base_color: str, hover_color: str) -> None:
        self._button_palettes[button] = (base_color, hover_color)
        self._current_colors[button] = base_color
        button.configure(fg_color=base_color)

        button.bind("<Enter>", lambda _: self._animate_button_color(button, hover_color))
        button.bind("<Leave>", lambda _: self._animate_button_color(button, base_color))
        button.bind("<ButtonPress-1>", lambda _: self._animate_button_color(button, _darken(hover_color, 0.2), fast=True))
        button.bind("<ButtonRelease-1>", lambda _: self._animate_button_color(button, hover_color))

    def _animate_button_color(self, button: ctk.CTkButton, target_color: str, fast: bool = False) -> None:
        start_color = self._current_colors.get(button, target_color)
        if start_color == target_color:
            return

        steps = 6 if fast else 12
        delay = 8 if fast else 15

        if button in self._color_jobs:
            self.after_cancel(self._color_jobs[button])

        def step(index: int) -> None:
            fraction = index / steps
            blended = _blend_color(start_color, target_color, fraction)
            self._current_colors[button] = blended
            button.configure(fg_color=blended)
            if index < steps:
                self._color_jobs[button] = self.after(delay, lambda: step(index + 1))
            else:
                self._color_jobs.pop(button, None)

        step(1)

    def _show_progress(self) -> None:
        if not self._progress_visible:
            self.progress.grid()
            self.progress.start()
            self._progress_visible = True

    def _hide_progress(self) -> None:
        if self._progress_visible:
            self.progress.stop()
            self.progress.set(0)
            self.progress.grid_remove()
            self._progress_visible = False

    # ------------------------------------------------------------------
    # ICONS & CLEANUP
    # ------------------------------------------------------------------
    def _load_icons(self) -> Dict[str, ctk.CTkImage]:
        return {
            "play": self._build_icon("▶", ACCENT_COLOR),
            "spinner": self._build_icon("⟳", "#ffaa3b"),
            "success": self._build_icon("✓", "#2ecc71"),
            "error": self._build_icon("!", "#ff5f5f"),
            "idle": self._build_icon("•", MUTED_TEXT),
        }

    @staticmethod
    def _build_icon(symbol: str, color: str, size: int = 28) -> ctk.CTkImage:
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((0, 0, size - 1, size - 1), fill=color)
        try:
            font = ImageFont.truetype("seguisym.ttf", int(size * 0.6))
        except OSError:
            font = ImageFont.load_default()
        draw.text((size / 2, size / 2), symbol, fill="white", anchor="mm", font=font)
        return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))

    def on_close(self) -> None:
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.destroy()


def main() -> None:
    """Entrypoint used by `python -m src.ui`. Creates and runs the GUI app."""

    app = PipelineApp()
    app.mainloop()


if __name__ == "__main__":
    main()
