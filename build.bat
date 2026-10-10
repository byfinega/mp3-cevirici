@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo [1/3] Derleme araclari kuruluyor...
py -m pip install -r requirements-build.txt
if errorlevel 1 (
  echo HATA: pip kurulumu basarisiz oldu.
  exit /b 1
)

echo [2/3] Exe derleniyor...
py -m PyInstaller --noconfirm --clean --onefile --windowed --name MP3Cevirici mp3_cevirici.py
if errorlevel 1 (
  echo HATA: PyInstaller derlemesi basarisiz oldu.
  exit /b 1
)

echo [3/3] Tamamlandi.
echo Cikti: dist\MP3Cevirici.exe
echo.
echo Release paketi icin dist\MP3Cevirici.exe dosyasinin yanina sunlari kopyalayin:
echo   yt-dlp.exe, ffmpeg.exe, deno.exe
echo   README.md, LICENSE, THIRD_PARTY_LICENSES.txt
echo   COPYING.GPLv3.txt, LICENSE.yt-dlp.txt, LICENSE.deno.md
echo.
echo indirilenler/ klasorunun icindekileri pakete KOYMAYIN.
