# Kurulum ve Derleme Kılavuzu

Bu belge, MP3 Çevirici'yi kaynak koddan çalıştırmayı, gerekli araçları
temin etmeyi ve exe olarak derleyip Release paketi hazırlamayı anlatır.

## 1. Gereksinimler

- Windows 10/11
- Python 3.10 veya üzeri (https://www.python.org/downloads/)
  - Kurulumda **"Add python.exe to PATH"** seçeneğini işaretleyin.
- İnternet bağlantısı (araçları indirmek için)

Kontrol:

```bat
py --version
```

## 2. Kaynak koddan çalıştırma

Proje klasöründe:

```bat
py mp3_cevirici.py
```

Kurulumu arayüz açmadan doğrulayın:

```bat
py mp3_cevirici.py --self-test
```

Beklenen çıktı: üç araç için de `OK` ve `Command check: OK`.
Ek Python paketi gerekmez (`tkinter` Python ile birlikte gelir).

## 3. Araç exe'lerinin temini (önemli)

Uygulama, aşağıdaki araçların **uygulama exe'si ile aynı klasörde**
olmasını bekler. Bu dosyalar repoda yer almaz; resmi kaynaklardan alınır:

| Dosya | Kaynak | Not |
|---|---|---|
| `yt-dlp.exe` | https://github.com/yt-dlp/yt-dlp/releases | `yt-dlp.exe` adlı dosyayı indirin |
| `ffmpeg.exe` | https://www.gyan.dev/ffmpeg/builds/ | `ffmpeg-release-essentials.zip` içinden `bin\ffmpeg.exe` çıkarılır |
| `deno.exe` | https://github.com/denoland/deno/releases | `deno-x86_64-pc-windows-msvc.zip` içindeki `deno.exe` |

Sürümleri doğrulayın:

```bat
yt-dlp.exe --version
ffmpeg.exe -version
deno.exe --version
```

Not: Uygulama, `yt-dlp` 60 günden eskiyse uyarı verir. Güncellemek için:

```bat
yt-dlp.exe -U
```

## 4. Exe olarak derleme

Derleme için önce araç kurulur (tek seferlik):

```bat
py -m pip install -r requirements-build.txt
```

Sonra:

```bat
build.bat
```

Çıktı: `dist\MP3Cevirici.exe`.

`build.bat` şunları yapar:

1. `requirements-build.txt` içindeki derleme bağımlılıklarını kurar.
2. PyInstaller ile tek dosyalık, penceresiz (`--windowed`) exe üretir.
3. Çıktı yolunu ekrana yazar.

## 5. Release paketi hazırlama

`dist\MP3Cevirici.exe` üretildikten sonra yeni bir klasöre şunları koyun:

```
MP3Cevirici.exe
yt-dlp.exe
ffmpeg.exe
deno.exe
README.md
THIRD_PARTY_LICENSES.txt
COPYING.GPLv3.txt
LICENSE.yt-dlp.txt
LICENSE.deno.md
LICENSE
```

Bu klasörü zipleyip GitHub'da **Releases** bölümüne yükleyin.
Zip'e kesinlikle `indirilenler/` içeriğini (indirilen MP3'leri) koymayın.

Sürümleme önerisi: Git etiketi kullanın (`v1.0.0`, `v1.1.0` ...).

## 6. Sorun giderme

- **"Eksik araç" hatası:** 3 exe'nin de uygulama exe'si ile aynı klasörde
  olduğunu kontrol edin.
- **"yt-dlp sürümü eski" uyarısı:** `yt-dlp.exe -U` ile güncelleyin.
- **Giriş isteyen video hata veriyor:** *Firefox çerezlerini kullan* kutusunu
  işaretleyip Firefox kapalıyken tekrar deneyin.
- **Derleme hatası:** `py -m pip install --upgrade pyinstaller` sonrası
  `build.bat`'i tekrar çalıştırın.
