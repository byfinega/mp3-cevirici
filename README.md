# MP3 Çevirici | byfinega

Video ve playlist adreslerindeki sesi **MP3'e çevirip indiren** Türkçe masaüstü uygulaması.

> **English summary:** A Turkish desktop app that downloads audio from video / playlist page URLs and converts it to MP3 (via yt-dlp + ffmpeg). See `docs/kurulum.md` (Turkish) for setup.

## Özellikler

- Tek parça veya playlist'in tamamını indirme
- MP3 kalite seçimi: 128 / 192 / 320 kbps
- MP3'lere başlık bilgisi otomatik gömülür (kapak resmi gömülmez)
- Tekrar indirilen bağlantılar arşiv dosyaları sayesinde atlanır
- Giriş isteyen içerikler için Firefox (önerilen) çerez desteği

## Gereksinimler

Uygulama exe'si ile **aynı klasörde** şu araçlar bulunmalıdır:

| Dosya | Nereden alınır |
|---|---|
| `yt-dlp.exe` | https://github.com/yt-dlp/yt-dlp/releases |
| `ffmpeg.exe` | https://www.gyan.dev/ffmpeg/builds/ (`essentials` yapımı yeterli) |
| `deno.exe` | https://github.com/denoland/deno/releases |

Lisans bilgileri: `THIRD_PARTY_LICENSES.txt`, `COPYING.GPLv3.txt`, `LICENSE.yt-dlp.txt`, `LICENSE.deno.md`.

## Hızlı başlangıç (kaynak koddan)

```bat
py mp3_cevirici.py
```

Kurulumu doğrulamak için (arayüz açılmaz):

```bat
py mp3_cevirici.py --self-test
```

Python 3.10+ gerekir. Ek paket gerekmez (yalnızca standart kütüphane: `tkinter`).

## Hazır paket (önerilen)

`Releases` bölümündeki zip'i indirip bir klasöre çıkarın. Klasörde şunlar olur:

```
MP3Cevirici.exe
yt-dlp.exe
ffmpeg.exe
deno.exe
README.md
THIRD_PARTY_LICENSES.txt + lisans metinleri
```

`indirilenler/` klasörü ilk indirmede otomatik oluşur.

## Derleme

```bat
build.bat
```

Çıktı: `dist\MP3Cevirici.exe`. Derleme araçları: `requirements-build.txt`. Ayrıntı: `docs/kurulum.md`.

## Kullanım

1. Video/müzik/playlist bağlantısını üstteki kutuya yapıştırın.
2. İndirme türünü seçin: **Tek parça** veya **Playlist**.
3. MP3 kalitesini seçin (önerilen: 192 kbps).
4. İndirme klasörünü seçin (varsayılan: `indirilenler/`).
5. **MP3 Olarak İndir**'e basın.

Tek parçalar `indirilenler/tekli/`, listeler `indirilenler/playlist/` klasörüne kaydedilir.

## Dosya yapısı

```
mp3_cevirici.py       masaüstü arayüz
mp3_core.py           çekirdek mantık (yt-dlp komutu, araç kontrolü)
docs/kurulum.md       ayrıntılı kurulum ve derleme kılavuzu
build.bat             exe derleme betiği
requirements-build.txt derleme bağımlılıkları
```

## Yasal uyarı

Bu uygulamayı yalnızca **haklarına sahip olduğunuz veya indirme izni verilen** içerikler için kullanın. Telifli eserleri izinsiz indirmek hukuki sorumluluk doğurabilir.

## Lisans

Bu projenin kaynak kodu MIT lisansı ile paylaşılır (`LICENSE`). Birlikte dağıtılan üçüncü taraf araçlar kendi lisanslarına tabidir (`THIRD_PARTY_LICENSES.txt`).
