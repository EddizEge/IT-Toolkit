# Değişiklik Günlüğü

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) yaklaşımını
izler ve proje [SemVer](https://semver.org/) kullanır.

## [Yayınlanmadı]

### Planlanan

- Açıklanabilir sistem sağlık puanı ve tanılama özeti
- Güvenli geri alma ve otomatik geri yükleme noktası akışları

## [0.5.1-hotfix.1] - 2026-07-29

### Düzeltildi

- PowerShell komutlarının çalışmak yerine Görev Merkezi’ne düz metin olarak
  yazılmasına yol açan Windows tırnaklama hatası giderildi
- Alt ağ taraması ve Office lisans tanılama komutlarının eksik tırnakları,
  kodlanmış PowerShell komutlarıyla kalıcı olarak düzeltildi
- Çok adımlı kurulum, profil yedekleme, envanter ve hazır akışlarda önceki bir
  hatanın sonraki başarılı komut tarafından gizlenmesi önlendi
- AnyDesk, Google Drive, NVIDIA App ve HP Smart için güncel Winget kimlikleri
  kullanıldı
- Winget kataloğunda bulunmayan RustDesk, FileZilla ve MailStore Home,
  geliştiricilerin resmi indirme sayfalarına yönlendirildi
- Minidump klasörü bulunmayan cihazlarda geçersiz klasör açmak yerine açıklayıcı
  sonuç gösteriliyor
- Dinlenen portlar görevi gereksiz yönetici yetkisi istemeden çalışıyor

### Değiştirildi

- Her görev benzersiz bir geçici komut dosyası üzerinden çalıştırılıyor; görev
  bittiğinde veya iptal edildiğinde dosya otomatik temizleniyor
- TikTok, Candy Crush ve McAfee temizliği artık yalnızca eşleşen Microsoft Store
  paketlerini tespit ederek kaldırıyor

### Kalite

- Gerçek PowerShell yürütme, çok adımlı hata aktarımı, geçici dosya temizliği,
  paket kimliği ve araç kayıt bütünlüğü testleri eklendi
- Toplam 23 otomatik test ve güvenli canlı görev denetimi başarıyla tamamlandı

## [0.5.0-preview.1] - 2026-07-29

### Eklendi

- Favorileri, son kullanılanları ve hazır akışları birleştiren Hızlı Erişim sayfası
- Bütün 64 araç kartında favoriye ekleme ve kaldırma düğmesi
- Favorileri yukarı/aşağı taşıyarak kişisel sıralama
- En son kullanılan 12 aracı cihazda saklayan yerel geçmiş
- Başlık, kategori ve açıklamada arama yapan `Ctrl+K` komut paleti
- Favorileri arama sonuçlarında öne çıkaran komut sıralaması
- `Alt+1` Sistem Özeti, `Alt+2` Hızlı Erişim ve `Alt+3` Görev Merkezi kısayolları
- Temel sistem kontrolü, ağ onarımı ve teslim öncesi cihaz özeti hazır akışları
- Tercih, komut sıralaması ve hazır akışlar için 10 yeni otomatik test

### Değiştirildi

- Sol menü yeni Hızlı Erişim modülü için daha kompakt hâle getirildi
- Üst çubuğa komut paleti düğmesi ve kısayol ipucu eklendi
- Araç çalıştırma geçmişi bütün modüllerde ortak tercih servisine bağlandı

### Güvenlik

- Tercihler yalnızca `%LOCALAPPDATA%\IT Toolkit\preferences.json` içinde tutuluyor
- Tanınmayan, yinelenen veya bozuk tercih kayıtları yükleme sırasında yok sayılıyor
- Ağ onarımı hazır akışı yönetici yetkisi ve kullanıcı onayı gerektiriyor

## [0.4.0-preview.1] - 2026-07-29

### Eklendi

- Çalışan, başarılı ve sorunlu işlemleri özetleyen Görev Merkezi
- Standart ve mevcut yönetici oturumundaki komutlar için canlı çıktı
- Yüzde içeren komut çıktılarında otomatik ilerleme algılama
- Sürekli ping gibi uygun görevleri işlem ağacıyla iptal etme
- En fazla 100 kayıt tutan yerel JSON görev geçmişi
- Önceki oturumda yarım kalan görevleri algılama
- Görev çıktısını panoya kopyalama
- UTF-8 görev raporu dışa aktarma
- Başarı, uyarı ve hata bildirimleri
- Beş süreç yaşam döngüsü testi

### Değiştirildi

- Normal komutlar harici konsol yerine yönetilen arka plan süreçlerinde çalışıyor
- Robocopy’nin 0–7 çıkış kodları başarılı sonuç olarak yorumlanıyor
- Alt ağ taraması ve Office lisans tanılama çıktısı Görev Merkezi’ne uyarlandı
- GitHub build ve Release akışları paketlemeden önce testleri çalıştırıyor

### Güvenlik

- UAC ile ayrı yönetici penceresine devredilen görevlerin çıktısı yakalanmıyor;
  bu sınır arayüzde açıkça belirtiliyor
- Görev geçmişi yalnızca yerel kullanıcı verisi alanında saklanıyor

## [0.3.0-preview.1] - 2026-07-29

### Eklendi

- PySide6 tabanlı yeni uygulama mimarisi
- Dokuz ana modül ve merkezi araç kayıt sistemi
- 64 sistem/destek işlemi
- 32 resmi yazılım ve üretici kaynağı
- Canlı sistem özeti
- Global araç arama
- Özgün logo, renk paleti ve SVG ikon sistemi
- Wi-Fi QR kodunu çevrimdışı üretme
- Windows için tek dosyalık PyInstaller paketi
- GitHub Actions build ve Release otomasyonu

### Değiştirildi

- Menü, kartlar, tipografi ve durum bildirimleri baştan tasarlandı
- Uzun işlemler arka plan yürütücüsüne taşındı
- Yazılım bağlantıları resmi kaynaklarla sınırlandırıldı

### Güvenlik

- Lisans atlatma, korsan yazılım ve parola çözme işlevleri yeni sürümden
  çıkarıldı
- Güvenilir olmayan indirme bağlantıları kaldırıldı

[Yayınlanmadı]: https://github.com/EddizEge/IT-Toolkit/compare/v0.5.1-hotfix.1...HEAD
[0.5.1-hotfix.1]: https://github.com/EddizEge/IT-Toolkit/compare/v0.5.0-preview.1...v0.5.1-hotfix.1
[0.5.0-preview.1]: https://github.com/EddizEge/IT-Toolkit/compare/v0.4.0-preview.1...v0.5.0-preview.1
[0.4.0-preview.1]: https://github.com/EddizEge/IT-Toolkit/compare/v0.3.0-preview.1...v0.4.0-preview.1
[0.3.0-preview.1]: https://github.com/EddizEge/IT-Toolkit/releases/tag/v0.3.0-preview.1
