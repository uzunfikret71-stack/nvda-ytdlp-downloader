# Üçüncü taraf bileşenler

Bu eklenti, kullanıcı kurulumu kolay olsun diye bazı komut satırı araçlarını paket içinde taşır.

## yt-dlp

- Dosya: `bin/yt-dlp.exe`
- Proje: https://github.com/yt-dlp/yt-dlp
- Paketlenen sürüm: `2026.08.19`
- Lisans: The Unlicense
- Lisans metni: `thirdPartyLicenses/yt-dlp-Unlicense.txt`
- Not: Pencere açılışında en fazla 24 saatte bir sürüm denetimi yapılır. Otomatik denetim veya elle güncelleme sonucunda yalnızca kullanıcı onay verirse `yt-dlp.exe -U` çalıştırılır.

## FFmpeg

- Dosya: `bin/ffmpeg.exe`
- Proje: https://ffmpeg.org/
- Paketlenen yapı: `N-124279-g0f6ba39122-20260430`
- Lisans: GPL sürüm 3 veya sonrası. Paketlenen çalıştırılabilir dosyanın `-L` çıktısı bu lisansı ve `-version` çıktısı yapılandırma seçeneklerini gösterir.
- Lisans metni: `thirdPartyLicenses/FFmpeg-GPL-3.0.txt`
- Karşılık gelen FFmpeg kaynak sürümü: https://github.com/FFmpeg/FFmpeg/archive/0f6ba39122.zip

### ffprobe

- Dosya: `bin/ffprobe.exe`
- Paketlenen yapı: `N-124278-gcc3ca17127`, FFmpeg ile aynı tarihli (2026-04-30) bağımsız araç.
- Derleme: https://github.com/BtbN/FFmpeg-Builds/releases/tag/autobuild-2026-04-30-13-44
- Arşiv: `ffmpeg-N-124278-gcc3ca17127-win64-gpl.zip`; indirme sırasında yayımlanan SHA256 listesiyle doğrulanmıştır.
- Lisans: GPL sürüm 3 veya sonrası; `thirdPartyLicenses/FFmpeg-GPL-3.0.txt`.
- Kaynak: https://github.com/FFmpeg/FFmpeg/archive/cc3ca17127.zip

## Deno

- Dosya: `bin/deno.exe`
- Proje: https://deno.com/
- Paketlenen sürüm: `2.7.14`
- Lisans: MIT
- Lisans metni: `thirdPartyLicenses/Deno-MIT.txt`
- Not: Bazı yt-dlp çıkarıcıları JavaScript çalıştırma desteği için Deno kullanabilir. Bu nedenle paket bağımlılığı olarak tutulur.
