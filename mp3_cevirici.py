# -*- coding: utf-8 -*-
"""Basit Türkçe yt-dlp MP3 arayüzü.
byfinega
Portable kullanım hedeflenir: bu dosyadan üretilen exe ile aynı klasörde
yt-dlp.exe, ffmpeg.exe ve deno.exe bulunmalıdır.

Video adreslerindeki müzik/ses MP3'e çevrilerek indirilir.
Tüm indirme mantığı mp3_core.py içindedir.
"""

from __future__ import annotations

import argparse
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, List, Optional

from mp3_core import (
    APP_NAME,
    APP_VERSION,
    AUDIO_CHOICES,
    DOWNLOAD_MODES,
    TOOL_FILENAMES,
    DownloadWorker,
    ToolManager,
    build_download_command,
    get_app_dir,
    get_default_download_dir,
    iter_missing_tools,
    missing_tools_message,
    normalize_mode,
    parse_progress_line,
    validate_url,
    yt_dlp_stale_warning,
)


def run_self_test() -> int:
    app_dir = get_app_dir()
    tool_manager = ToolManager(app_dir)
    statuses = tool_manager.check(include_versions=True)
    print(f"{APP_NAME} {APP_VERSION} self-test")
    print(f"App dir: {app_dir}")
    print(f"Default downloads: {get_default_download_dir()}")

    ok = True
    for name, status in statuses.items():
        state = "OK" if status.ok else "FAIL"
        detail = status.version or status.error or str(status.path)
        print(f"{state}: {name} -> {detail}")
        ok = ok and status.ok

    stale = yt_dlp_stale_warning(statuses.get("yt-dlp").version if statuses.get("yt-dlp") else "")
    if stale:
        print(f"UYARI: {stale}")

    sample_output = app_dir / "self-test-output"
    required_flags = [
        "--ffmpeg-location",
        "--js-runtimes",
        "--download-archive",
        "-x",
        "--audio-format",
        "--audio-quality",
        "--add-metadata",
    ]
    for quality in AUDIO_CHOICES:
        for mode in DOWNLOAD_MODES:
            command = build_download_command(
                tool_manager=tool_manager,
                url="https://example.com/muzik",
                quality=quality,
                output_dir=sample_output,
                use_firefox_cookies=False,
                mode=mode,
            )
            for flag in required_flags:
                if flag not in command:
                    print(f"FAIL: {quality}/{mode} komutunda {flag} yok")
                    ok = False

            if "mp3" not in command:
                print(f"FAIL: {quality}/{mode} komutunda mp3 formatı yok")
                ok = False

            if "--merge-output-format" in command:
                print(f"FAIL: {quality}/{mode} komutunda MP4 birleştirme bayrağı olmamalı")
                ok = False

            if "--embed-thumbnail" in command or "--convert-thumbnails" in command:
                print(f"FAIL: {quality}/{mode} komutunda kapak bayrağı olmamalı")
                ok = False

            playlist_flag = "--yes-playlist" if mode == "playlist" else "--no-playlist"
            if playlist_flag not in command:
                print(f"FAIL: {quality}/{mode} komutunda {playlist_flag} yok")
                ok = False

            subdir = "playlist" if mode == "playlist" else "tekli"
            if not any(subdir in part for part in command):
                print(f"FAIL: {quality}/{mode} komutunda {subdir} klasörü yok")
                ok = False

        if str(tool_manager.path_for("yt-dlp")) != command[0]:
            print("FAIL: yt-dlp yolu komutun ilk argümanı değil")
            ok = False

    progress_sample = parse_progress_line("[download]  14.5% of 145.80MiB at 2.20MiB/s ETA 00:56")
    if not progress_sample or progress_sample.get("kind") != "percent":
        print("FAIL: yüzde ilerleme satırı parse edilemedi")
        ok = False

    counter_sample = parse_progress_line("[download] Downloading item 3 of 12")
    if not counter_sample or counter_sample.get("current") != 3 or counter_sample.get("total") != 12:
        print("FAIL: playlist sayaç satırı parse edilemedi")
        ok = False

    print("Command check:", "OK" if ok else "FAIL")
    return 0 if ok else 1


class Mp3DownloaderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION} | byfinega")
        self.root.geometry("840x660")
        self.root.minsize(760, 600)

        self.app_dir = get_app_dir()
        self.tool_manager = ToolManager(self.app_dir)
        self.event_queue: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self.worker: Optional[DownloadWorker] = None
        self.current_playlist_counter = ""

        self.url_var = tk.StringVar()
        self.quality_var = tk.StringVar(value="192")
        self.mode_var = tk.StringVar(value="tekli")
        self.output_dir_var = tk.StringVar(value=str(get_default_download_dir()))
        self.use_firefox_cookies_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Hazır.")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_text_var = tk.StringVar(value="Henüz MP3 indirme yok.")
        self.tool_status_vars = {
            name: tk.StringVar(value="Kontrol bekleniyor.") for name in TOOL_FILENAMES
        }

        self._build_ui()
        self.root.after(100, self.refresh_tools)
        self.root.after(100, self._process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.configure(".", font=("Tahoma", 10))
        app_bg = "#F0E6C8"
        self.root.configure(background=app_bg)
        self.root.option_add("*Font", ("Tahoma", 10))
        style.configure("TFrame", background=app_bg)
        style.configure("TLabel", background=app_bg, foreground="#1F2937", font=("Tahoma", 10))
        style.configure("Title.TLabel", background=app_bg, foreground="#0F172A", font=("Tahoma", 16, "bold"))
        style.configure("Hint.TLabel", background=app_bg, foreground="#64748B", font=("Tahoma", 10))
        style.configure("Status.TLabel", background=app_bg, foreground="#334155", font=("Tahoma", 10))
        style.configure("TLabelframe", background=app_bg)
        style.configure("TLabelframe.Label", background=app_bg, foreground="#334155", font=("Tahoma", 10, "bold"))
        style.configure("Header.TLabel", background=app_bg, foreground="#1F2937", font=("Tahoma", 10, "bold"))
        style.configure("TRadiobutton", background=app_bg, foreground="#1F2937", font=("Tahoma", 10))
        style.configure("TCheckbutton", background=app_bg, foreground="#1F2937", font=("Tahoma", 10))
        style.configure("TButton", font=("Tahoma", 10))
        style.configure("TEntry", font=("Tahoma", 10))

        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main, text=APP_NAME, style="Title.TLabel")
        title.pack(anchor=tk.W)

        source_frame = ttk.LabelFrame(main, text="Video / Müzik / Playlist Bağlantısı")
        source_frame.pack(fill=tk.X, pady=(12, 8))
        source_frame.columnconfigure(0, weight=1)

        self.url_entry = ttk.Entry(source_frame, textvariable=self.url_var)
        self.url_entry.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        self.url_entry.focus_set()
        self._add_entry_context_menu(self.url_entry)

        options_frame = ttk.LabelFrame(main, text="Ayarlar")
        options_frame.pack(fill=tk.X, pady=8)
        options_frame.columnconfigure(1, weight=1)

        ttk.Label(options_frame, text="İndirme Türü:", style="Header.TLabel").grid(row=0, column=0, sticky=tk.W, padx=10, pady=8)
        mode_container = ttk.Frame(options_frame)
        mode_container.grid(row=0, column=1, sticky=tk.W, padx=10, pady=8)
        for label, value in (("Tek parça", "tekli"), ("Playlist", "playlist")):
            ttk.Radiobutton(
                mode_container,
                text=label,
                value=value,
                variable=self.mode_var,
            ).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(options_frame, text="MP3 Kalitesi:", style="Header.TLabel").grid(row=1, column=0, sticky=tk.W, padx=10, pady=8)
        quality_container = ttk.Frame(options_frame)
        quality_container.grid(row=1, column=1, sticky=tk.W, padx=10, pady=8)
        for label, value in (("128 kbps", "128"), ("192 kbps (önerilen)", "192"), ("320 kbps", "320")):
            ttk.Radiobutton(
                quality_container,
                text=label,
                value=value,
                variable=self.quality_var,
            ).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(options_frame, text="Klasör:", style="Header.TLabel").grid(row=2, column=0, sticky=tk.W, padx=10, pady=8)
        folder_row = ttk.Frame(options_frame)
        folder_row.grid(row=2, column=1, sticky=tk.EW, padx=10, pady=8)
        folder_row.columnconfigure(0, weight=1)
        self.output_dir_entry = ttk.Entry(folder_row, textvariable=self.output_dir_var)
        self.output_dir_entry.grid(row=0, column=0, sticky=tk.EW)
        self._add_entry_context_menu(self.output_dir_entry)
        ttk.Button(folder_row, text="Seç", command=self.choose_output_dir).grid(row=0, column=1, padx=(8, 0))

        ttk.Checkbutton(
            options_frame,
            text="Firefox çerezlerini kullan",
            variable=self.use_firefox_cookies_var,
        ).grid(row=3, column=1, sticky=tk.W, padx=10, pady=(0, 10))

        progress_frame = ttk.LabelFrame(main, text="İlerleme")
        progress_frame.pack(fill=tk.X, pady=8)
        progress_frame.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(10, 4))
        ttk.Label(progress_frame, textvariable=self.progress_text_var, style="Status.TLabel").grid(
            row=1,
            column=0,
            sticky=tk.W,
            padx=10,
            pady=(0, 10),
        )

        tools_frame = ttk.LabelFrame(main, text="Araç Kontrolü")
        tools_frame.pack(fill=tk.X, pady=8)
        tools_frame.columnconfigure(1, weight=1)

        for row, name in enumerate(TOOL_FILENAMES):
            ttk.Label(tools_frame, text=f"{TOOL_FILENAMES[name]}:").grid(
                row=row,
                column=0,
                sticky=tk.W,
                padx=10,
                pady=4,
            )
            ttk.Label(tools_frame, textvariable=self.tool_status_vars[name], style="Hint.TLabel").grid(
                row=row,
                column=1,
                sticky=tk.W,
                padx=10,
                pady=4,
            )

        ttk.Button(tools_frame, text="Tekrar Kontrol Et", command=self.refresh_tools).grid(
            row=0,
            column=2,
            rowspan=3,
            sticky=tk.NS,
            padx=10,
            pady=8,
        )

        action_frame = ttk.Frame(main)
        action_frame.pack(fill=tk.X, pady=(8, 10))
        self.start_button = ttk.Button(action_frame, text="MP3 Olarak İndir", command=self.start_download)
        self.start_button.pack(side=tk.LEFT)
        self.cancel_button = ttk.Button(
            action_frame,
            text="Durdur",
            command=self.cancel_download,
            state=tk.DISABLED,
        )
        self.cancel_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(action_frame, textvariable=self.status_var, style="Status.TLabel").pack(
            side=tk.LEFT,
            padx=(14, 0),
        )

        log_frame = ttk.LabelFrame(main, text="İşlem Günlüğü")
        log_frame.pack(fill=tk.BOTH, expand=True)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            height=12,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Tahoma", 9),
        )
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _add_entry_context_menu(self, entry: ttk.Entry) -> None:
        menu = tk.Menu(entry, tearoff=0, font=("Tahoma", 10))
        menu.add_command(label="Kes", command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label="Kopyala", command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="Yapıştır", command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Tümünü Seç", command=lambda: entry.select_range(0, tk.END))

        def show_menu(event: "tk.Event[Any]") -> None:
            entry.focus_set()
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        entry.bind("<Button-3>", show_menu)

    def choose_output_dir(self) -> None:
        selected = filedialog.askdirectory(
            title="MP3 indirme klasörünü seç",
            initialdir=self.output_dir_var.get() or str(get_default_download_dir()),
        )
        if selected:
            self.output_dir_var.set(selected)

    def refresh_tools(self) -> None:
        self.status_var.set("Araçlar kontrol ediliyor...")
        thread = threading.Thread(target=self._refresh_tools_worker, daemon=True)
        thread.start()

    def _refresh_tools_worker(self) -> None:
        statuses = self.tool_manager.check(include_versions=True)
        for name, status in statuses.items():
            if not status.exists:
                text = "Eksik"
            elif status.error:
                text = status.error
            elif status.version:
                text = f"Tamam - {status.version}"
            else:
                text = "Tamam"
            self.event_queue.put((f"tool:{name}", text))

        if all(status.ok for status in statuses.values()):
            self.event_queue.put(("status", "Hazır."))
        else:
            self.event_queue.put(("status", "Eksik araç var."))

    def start_download(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(APP_NAME, "Devam eden MP3 indirme bitmeden yeni indirme başlatılamaz.")
            return

        url = self.url_var.get().strip()
        url_error = validate_url(url)
        if url_error:
            messagebox.showwarning(APP_NAME, url_error)
            self.url_entry.focus_set()
            return

        output_dir = Path(self.output_dir_var.get().strip() or str(get_default_download_dir()))
        statuses = self.tool_manager.check(include_versions=False)
        missing = list(iter_missing_tools(statuses))
        if missing:
            messagebox.showerror(APP_NAME, missing_tools_message(list(missing)))
            self.refresh_tools()
            return

        self._clear_log()
        self.current_playlist_counter = ""
        self.progress_var.set(0.0)
        self.progress_text_var.set("Başlatılıyor...")
        self._append_log(f"{APP_NAME} {APP_VERSION}")
        self._append_log(f"Uygulama klasörü: {self.app_dir}")
        self._append_log("Algılanan müzikler MP3'e çevrilerek indirilecek.")
        self.status_var.set("MP3 indirme çalışıyor...")
        self.start_button.configure(state=tk.DISABLED)
        self.cancel_button.configure(state=tk.NORMAL)

        self.worker = DownloadWorker(
            tool_manager=self.tool_manager,
            url=url,
            quality=self.quality_var.get(),
            output_dir=output_dir,
            use_firefox_cookies=self.use_firefox_cookies_var.get(),
            event_queue=self.event_queue,
            mode=normalize_mode(self.mode_var.get()),
        )
        self.worker.start()

    def cancel_download(self) -> None:
        if self.worker and self.worker.is_alive():
            self.status_var.set("Durduruluyor...")
            self.worker.cancel()
            self.cancel_button.configure(state=tk.DISABLED)

    def _process_queue(self) -> None:
        try:
            while True:
                event_type, text = self.event_queue.get_nowait()
                if event_type.startswith("tool:"):
                    name = event_type.split(":", 1)[1]
                    self.tool_status_vars[name].set(text)
                elif event_type == "status":
                    self.status_var.set(text)
                elif event_type == "log":
                    self._append_log(text)
                elif event_type == "progress":
                    self._update_progress(text)
                elif event_type == "success":
                    self._append_log(text)
                    self.status_var.set("Tamamlandı.")
                    self.progress_var.set(100.0)
                    self.progress_text_var.set("Tamamlandı.")
                    messagebox.showinfo(APP_NAME, text)
                elif event_type == "warning":
                    self._append_log(text)
                    self.status_var.set(text)
                    self.progress_text_var.set(text)
                elif event_type == "error":
                    self._append_log(text)
                    self.status_var.set("Hata oluştu.")
                    self.progress_text_var.set("Hata oluştu.")
                    messagebox.showerror(APP_NAME, text)
                elif event_type == "done":
                    self.start_button.configure(state=tk.NORMAL)
                    self.cancel_button.configure(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.root.after(100, self._process_queue)

    def _update_progress(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return

        if payload.get("kind") == "counter":
            current = payload.get("current")
            total = payload.get("total")
            self.current_playlist_counter = f"Parça {current}/{total}"
            self.progress_var.set(0.0)
            self.progress_text_var.set(f"{self.current_playlist_counter} | MP3 hazırlanıyor...")
            return

        if payload.get("kind") == "percent":
            percent = float(payload.get("percent", 0.0))
            detail = str(payload.get("detail", "")).strip()
            self.progress_var.set(max(0.0, min(100.0, percent)))
            prefix = f"{self.current_playlist_counter} | " if self.current_playlist_counter else ""
            self.progress_text_var.set(f"{prefix}{detail}")

    def _append_log(self, text: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {text}\n")
        self.log_text.configure(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def _clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            should_close = messagebox.askyesno(
                APP_NAME,
                "MP3 indirme devam ediyor. Uygulamadan çıkılsın mı?",
            )
            if not should_close:
                return
            self.worker.cancel()
        self.root.destroy()




def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--self-test", action="store_true", help="GUI açmadan temel kontrolleri çalıştırır.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.self_test:
        return run_self_test()

    root = tk.Tk()
    Mp3DownloaderApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
