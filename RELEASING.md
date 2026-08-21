# Yayın Rehberi

## Sürüm biçimi

Etiketler SemVer ön ekiyle oluşturulur:

- Ön izleme: `v0.5.0-preview.1`
- Beta: `v0.6.0-beta.1`
- Sürüm adayı: `v0.9.0-rc.1`
- Kararlı: `v1.0.0`
- Hata düzeltmesi: `v1.0.1`
- Ön izleme bakım sürümü: `v0.5.1-hotfix.1`

## Yayın kontrol listesi

1. GitHub’da açık `[Uygulama Geri Bildirimi]` issue’larını inceleyip
   sınıflandırın; kritik sorunlar açıkken yayın yapmayın.
2. `ROADMAP.md` kilometre taşını ve `CHANGELOG.md` tarihini güncelleyin.
3. `app_v2/__init__.py` içindeki sürümü etiketle eşleştirin.
4. Çözülen feedback issue numaralarını ve ertelenen bilinen sorunları sürüm
   notuna ekleyin.
5. Uygulamayı standart ve yönetici oturumunda açın.
6. Ana modülleri, global aramayı, hata günlüğünü, GitHub geri bildirim
   bağlantısını ve uzun görev yürütmeyi kontrol edin.
7. Temiz commit’i `main` dalına gönderin.
8. İmzalı etiketi oluşturup gönderin.
9. GitHub Release’i yayımlayın.
10. Windows iş akışının EXE’yi Release’e eklediğini doğrulayın.
11. EXE’yi temiz bir Windows 10/11 ortamında duman testinden geçirin.

Geri bildirim kontrol bağlantısı:
`https://github.com/EddizEge/IT-Toolkit/issues?q=is%3Aissue+is%3Aopen+%22%5BUygulama+Geri+Bildirimi%5D%22`

## Yerel komutlar

```powershell
git tag -a v0.6.0-beta.1 -m "IT Toolkit v0.6.0-beta.1"
git push origin v0.6.0-beta.1
```

Ardından GitHub üzerinde bu etiketten bir Release oluşturun. Release
yayımlandığında `.github/workflows/release.yml` Windows EXE’sini oluşturur ve
otomatik olarak yayına yükler.

## Sürüm notu düzeni

Her sürüm notu şu başlıkları kullanır:

- Öne çıkanlar
- Yeni
- İyileştirmeler
- Düzeltmeler
- Güvenlik
- Bilinen sorunlar
- Doğrulama özeti
