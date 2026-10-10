# -*- coding: utf-8 -*-
"""MP3 Cevirici cekirdek mantigi (GUI'den bagimsiz).

Bu modul hem masaustu arayuzu (mp3_cevirici.py) hem de ileride baglanacak
yardimci araclar tarafindan paylasilir. tkinter veya baska GUI bagimliliklari
icermez. Girdideki video/playlist adreslerindeki ses, yt-dlp + ffmpeg ile
MP3'e cevrilerek indirilir.

byfinega
"""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


APP_NAME = "MP3 Çevirici"
APP_VERSION = "1.0"

TOOL_FILENAMES = {
    "yt-dlp": "yt-dlp.exe",
    "ffmpeg": "ffmpeg.exe",
    "deno": "deno.exe",
}

# MP3 ses kaliteleri (kbps). Anahtar ayni zamanda secim degeridir.
AUDIO_QUALITIES = {
    "128": "128K",
    "192": "192K",
    "320": "320K",
}

AUDIO_CHOICES = ("128", "192", "320")

# Geriye uyumluluk: eski surumun kalite adiyla import eden kod bozulmasin.
QUALITY_FORMATS = {
    "128": "bestaudio/best",
    "192": "bestaudio/best",
    "320": "bestaudio/best",
    "480": "bestaudio/best",
    "720": "bestaudio/best",
    "1080": "bestaudio/best",
    "4K": "bestaudio/best",
}

QUALITY_CHOICES = AUDIO_CHOICES

DOWNLOAD_PERCENT_RE = re.compile(r"^\[download\]\s+(\d+(?:\.\d+)?)%")
PLAYLIST_COUNTER_RE = re.compile(r"^\[download\]\s+Downloading (?:item|video)\s+(\d+)\s+of\s+(\d+)")

DEFAULT_SUBDIR_NAME = "indirilenler"

# yt-dlp bu süreden daha eskiyse video sitesi değişiklikleri yüzünden
# ses akışları engellenebilir (kapaklar iner, MP3 inmez).
YT_DLP_STALE_DAYS = 60


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_default_download_dir() -> Path:
    return get_app_dir() / DEFAULT_SUBDIR_NAME


def get_creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def yt_dlp_release_date(version: str) -> Optional[date]:
    """'2026.03.17' gibi yt-dlp sürümünden tarih çıkarır, olmazsa None."""
    match = re.match(r"\s*(\d{4})\.(\d{1,2})\.(\d{1,2})", version or "")
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def yt_dlp_stale_warning(version: str) -> Optional[str]:
    """Sürüm YT_DLP_STALE_DAYS günden eskiyse uyarı metni döndürür."""
    release = yt_dlp_release_date(version)
    if release is None:
        return None
    if (date.today() - release).days > YT_DLP_STALE_DAYS:
        return (
            f"yt-dlp sürümü eski ({version.strip()}). Video siteleri ses akışlarını "
            "engelleyebilir; önce klasörde 'yt-dlp.exe -U' komutuyla güncelleyin."
        )
    return None


def build_tool_env(tool_dir: Path) -> Dict[str, str]:
    env = os.environ.copy()
    current_path = env.get("PATH", "")
    env["PATH"] = str(tool_dir) + os.pathsep + current_path
    return env


def normalize_quality(quality: str) -> str:
    if quality in AUDIO_QUALITIES:
        return quality
    # Eski surumun kalite secimleriyle gelinirse makul varsayilana dus.
    return "192"


def display_quality(quality: str) -> str:
    selected = normalize_quality(quality)
    return f"MP3 {selected} kbps"


def parse_progress_line(line: str) -> Optional[Dict[str, Any]]:
    counter_match = PLAYLIST_COUNTER_RE.match(line)
    if counter_match:
        return {
            "kind": "counter",
            "current": int(counter_match.group(1)),
            "total": int(counter_match.group(2)),
        }

    percent_match = DOWNLOAD_PERCENT_RE.match(line)
    if percent_match:
        percent = float(percent_match.group(1))
        detail = line.split("]", 1)[1].strip() if "]" in line else line
        return {"kind": "percent", "percent": percent, "detail": detail}

    return None


@dataclass(frozen=True)
class ToolStatus:
    name: str
    path: Path
    exists: bool
    version: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.exists and not self.error

    def to_dict(self) -> Dict[str, Any]:
        if not self.exists:
            text = "Eksik"
        elif self.error:
            text = self.error
        elif self.version:
            text = f"Tamam - {self.version}"
        else:
            text = "Tamam"
        return {
            "name": self.name,
            "file": self.path.name,
            "path": str(self.path),
            "exists": self.exists,
            "ok": self.ok,
            "version": self.version,
            "error": self.error,
            "text": text,
        }


class ToolManager:
    def __init__(self, app_dir: Path):
        self.app_dir = Path(app_dir)

    def path_for(self, name: str) -> Path:
        return self.app_dir / TOOL_FILENAMES[name]

    def check(self, include_versions: bool = False) -> Dict[str, ToolStatus]:
        statuses: Dict[str, ToolStatus] = {}
        for name in TOOL_FILENAMES:
            path = self.path_for(name)
            if not path.exists():
                statuses[name] = ToolStatus(
                    name=name,
                    path=path,
                    exists=False,
                    error=f"{path.name} uygulama klasöründe bulunamadı.",
                )
                continue

            if include_versions:
                version, error = self._read_version(name, path)
                statuses[name] = ToolStatus(
                    name=name,
                    path=path,
                    exists=True,
                    version=version,
                    error=error,
                )
            else:
                statuses[name] = ToolStatus(name=name, path=path, exists=True)
        return statuses

    def all_required_available(self) -> bool:
        return all(status.ok for status in self.check(include_versions=False).values())

    def read_version(self, name: str) -> str:
        """Aracın sürüm yazısını döndürür; okunamazsa boş string."""
        path = self.path_for(name)
        if not path.exists():
            return ""
        version, _error = self._read_version(name, path)
        return version

    def _read_version(self, name: str, path: Path) -> Tuple[str, str]:
        args = {
            "yt-dlp": [str(path), "--version"],
            "ffmpeg": [str(path), "-version"],
            "deno": [str(path), "--version"],
        }[name]

        try:
            result = subprocess.run(
                args,
                cwd=str(self.app_dir),
                env=build_tool_env(self.app_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=12,
                creationflags=get_creation_flags(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "", f"Sürüm okunamadı: {exc}"

        first_line = (result.stdout or "").splitlines()[0:1]
        version = first_line[0].strip() if first_line else ""
        if result.returncode != 0:
            return version, f"Sürüm komutu hata verdi: {result.returncode}"
        return version, ""


# İndirme modları: tek parça ya da listenin tamamı.
DOWNLOAD_MODES = ("tekli", "playlist")

# Mod bazında hedef alt klasör ve arşiv dosyası adları.
MODE_SUBDIRS = {
    "tekli": "tekli",
    "playlist": "playlist",
}

MODE_ARCHIVES = {
    "tekli": "mp3_arsiv_tekli.txt",
    "playlist": "mp3_arsiv_playlist.txt",
}


def normalize_mode(mode: str) -> str:
    if mode in DOWNLOAD_MODES:
        return mode
    return "tekli"


def display_mode(mode: str) -> str:
    return "Playlist" if normalize_mode(mode) == "playlist" else "Tek parça"


def build_download_command(
    *,
    tool_manager: ToolManager,
    url: str,
    quality: str,
    output_dir: Path,
    use_firefox_cookies: bool,
    mode: str = "tekli",
) -> List[str]:
    """Video/muzik adresindeki sesi MP3'e ceviren yt-dlp komutunu kurar.

    tekli: yalnız yapıştırılan müzik iner (liste bağlantısı olsa bile),
    hedef klasör ``<indirilenler>/tekli``.
    playlist: listenin tamamı iner, hedef ``<indirilenler>/playlist``.
    """
    selected_quality = normalize_quality(quality)
    selected_mode = normalize_mode(mode)
    bitrate = AUDIO_QUALITIES[selected_quality]
    base_dir = output_dir / MODE_SUBDIRS[selected_mode]
    if selected_mode == "playlist":
        output_template = base_dir / "%(playlist_title|Liste)s" / "%(playlist_index|000)s - %(title)s.%(ext)s"
    else:
        output_template = base_dir / "%(title)s.%(ext)s"
    archive_file = output_dir / MODE_ARCHIVES[selected_mode]

    command = [
        str(tool_manager.path_for("yt-dlp")),
        "--newline",
        "--no-color",
        "--windows-filenames",
        "--trim-filenames",
        "180",
        "--ffmpeg-location",
        str(tool_manager.app_dir),
        "--js-runtimes",
        "deno",
        "--no-playlist" if selected_mode == "tekli" else "--yes-playlist",
        "--ignore-errors",
        "--download-archive",
        str(archive_file),
        "-f",
        "bestaudio/best",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        bitrate,
        "--add-metadata",
        "-o",
        str(output_template),
        url,
    ]

    if use_firefox_cookies:
        command[1:1] = ["--cookies-from-browser", "firefox"]

    return command


class DownloadWorker(threading.Thread):
    def __init__(
        self,
        *,
        tool_manager: ToolManager,
        url: str,
        quality: str,
        output_dir: Path,
        use_firefox_cookies: bool,
        event_queue: "queue.Queue[Tuple[str, Any]]",
        mode: str = "tekli",
    ):
        super().__init__(daemon=True)
        self.tool_manager = tool_manager
        self.url = url
        self.quality = quality
        self.output_dir = Path(output_dir)
        self.use_firefox_cookies = use_firefox_cookies
        self.event_queue = event_queue
        self.mode = normalize_mode(mode)
        self.cancel_requested = threading.Event()
        self.process: Optional[subprocess.Popen] = None

    def cancel(self) -> None:
        self.cancel_requested.set()
        process = self.process
        if process and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def emit(self, event_type: str, payload: Any) -> None:
        self.event_queue.put((event_type, payload))

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:  # noqa: BLE001 - UI'ya güvenli hata dönmek için.
            self.emit("error", f"Beklenmeyen hata: {exc}")
        finally:
            self.emit("done", "finished")

    def _run(self) -> None:
        statuses = self.tool_manager.check(include_versions=False)
        missing = list(iter_missing_tools(statuses))
        if missing:
            self.emit("error", missing_tools_message(missing))
            return

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.emit("error", f"İndirme klasörü oluşturulamadı: {exc}")
            return

        command = build_download_command(
            tool_manager=self.tool_manager,
            url=self.url,
            quality=self.quality,
            output_dir=self.output_dir,
            use_firefox_cookies=self.use_firefox_cookies,
            mode=self.mode,
        )

        self.emit("log", f"İndirme klasörü: {self.output_dir / MODE_SUBDIRS[self.mode]}")
        self.emit("log", f"Mod: {display_mode(self.mode)}")
        self.emit("log", f"MP3 kalitesi: {display_quality(self.quality)}")
        stale = yt_dlp_stale_warning(self.tool_manager.read_version("yt-dlp"))
        if stale:
            self.emit("warning", stale)
        if self.use_firefox_cookies:
            self.emit("log", "Firefox çerezleri kullanılacak. Uygulama çerez kaydetmez.")
        self.emit("log", "yt-dlp başlatılıyor (MP3'e çevriliyor)...")

        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(self.output_dir),
                env=build_tool_env(self.tool_manager.app_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=get_creation_flags(),
            )
        except OSError as exc:
            self.emit("error", f"yt-dlp başlatılamadı: {exc}")
            return

        assert self.process.stdout is not None
        recent_lines: List[str] = []
        for line in self.process.stdout:
            if self.cancel_requested.is_set():
                break
            clean_line = line.rstrip()
            if clean_line:
                progress = parse_progress_line(clean_line)
                if progress:
                    self.emit("progress", progress)
                else:
                    self.emit("log", clean_line)
                    recent_lines.append(clean_line)
                    del recent_lines[:-30]

        return_code = self.process.wait()
        if self.cancel_requested.is_set():
            self.emit("warning", "İndirme kullanıcı tarafından durduruldu.")
            return

        if return_code == 0:
            self.emit("success", "MP3 indirme tamamlandı.")
            return

        if self.use_firefox_cookies:
            self.emit(
                "warning",
                "Not: Firefox çerezleri okunamadıysa Firefox'u kapatıp tekrar deneyin.",
            )
        error_detail = "\n".join(
            line for line in recent_lines[-8:] if "ERROR" in line or "hata" in line.lower()
        )
        message = f"İndirme tamamlanamadı. yt-dlp çıkış kodu: {return_code}"
        if error_detail:
            message += f"\n\nOlası sebep:\n{error_detail}"
        else:
            message += "\n\nAyrıntı için yukarıdaki işlem günlüğüne bakın."
        self.emit("error", message)



def iter_missing_tools(statuses: Dict[str, ToolStatus]) -> Iterable[ToolStatus]:
    for status in statuses.values():
        if not status.ok:
            yield status


def missing_tools_message(missing: List[ToolStatus]) -> str:
    lines = ["Eksik araç dosyası bulundu:"]
    lines.extend(f"- {status.path.name}" for status in missing)
    lines.append("Bu dosyalar uygulama exe'si ile aynı klasörde olmalıdır.")
    return "\n".join(lines)


def validate_url(url: str) -> Optional[str]:
    """Gecerli bir http/https adresi degilse hata metnini dondurur."""
    cleaned = (url or "").strip()
    if not cleaned:
        return "Müzik veya playlist bağlantısı girin."
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        return "Geçerli bir http veya https linki girin."
    return None
