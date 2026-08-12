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

1. `ROADMAP.md` kilometre taşını ve `CHANGELOG.md` tarihini güncelleyin.
2. `app_v2/__init__.py` içindeki sürümü etiketle eşleştirin.
3. Uygulamayı standart ve yönetici oturumunda açın.
4. Ana modülleri, global aramayı ve uzun görev yürütmeyi kontrol edin.
5. Temiz commit’i `main` dalına gönderin.
6. İmzalı etiketi oluşturup gönderin.
7. GitHub Release’i yayımlayın.
8. Windows iş akışının EXE’yi Release’e eklediğini doğrulayın.
9. EXE’yi temiz bir Windows 10/11 ortamında duman testinden geçirin.

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
