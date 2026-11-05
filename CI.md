# GitHub Actions

`main` dal?na g?nderimde, pull request a??ld???nda veya Actions > Build add-on > Run workflow ile paket olu?turulur. Paket ve SHA-256 dosyas? ?al??man?n `nvda-addon` artifact b?l?m?nden indirilir.

S?r?m haz?rlarken manifest s?r?m?n? (Media Converter i?in buildVars.py) ve de?i?iklik notlar?n? g?ncelleyin. Ard?ndan ayn? s?r?mle `vX.Y.Z` etiketi g?nderin. Ba?ar?l? derleme paketi bir **taslak Release** i?ine ekler; ger?ek NVDA testlerinden sonra GitHub ?zerinden yay?mlay?n. Mevcut Release dosyalar?n?n ?zerine yaz?lmaz.

Kaynak depoda bulunmayan binary dosyalar? scripts/ci_build.py i?inde belirtilen mevcut Release paketinden al?n?r ve sabit SHA-256 ile do?rulan?r. Binary s?r?mlerini de?i?tirmek i?in bu kaynak ve hash a??k?a g?ncellenmelidir. ?? ak??? bu ara?lar? ?al??t?rmaz.

Bu i? ak??? kullan?c?lar?n kurulu eklentilerini g?ncellemez ve NVDA Add-on Store ba?vurusu g?ndermez. NVDA kurulum, y?kseltme ve eri?ilebilirlik testleri ayr?ca yap?lmal?d?r. Eklenti s?r?m?, NVDA uyumlulu?u ve k?sayollar bu CI de?i?ikli?iyle de?i?tirilmemi?tir.
