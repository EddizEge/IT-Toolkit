# IT Toolkit Sürüm Yol Haritası

Bu yol haritası bir niyet belgesidir. Güvenlik, Windows uyumluluğu ve kullanıcı
geri bildirimi öncelik sırasını değiştirebilir.

## Yayın kanalları

| Kanal | Amaç | Beklenti |
| --- | --- | --- |
| Preview | Yeni mimari ve akışların erken testi | Eksik ayrıntılar ve değişen davranışlar olabilir |
| Beta | Özellik kapsamı büyük ölçüde tamamlanmış test sürümü | Hata düzeltme ve uyumluluk önceliklidir |
| RC | Kararlı sürüm adayı | Yalnızca kritik düzeltmeler kabul edilir |
| Stable | Günlük teknisyen kullanımına hazır sürüm | Belgelenmiş ve doğrulanmış davranış |

## v0.3.0-preview.1 — Yeni temel

**Durum:** Tamamlandı — 29 Temmuz 2026

- CustomTkinter’dan PySide6 mimarisine geçiş
- Dokuz ana modülün yeni arayüze taşınması
- 64 işlem ve 32 resmi yazılım paketinin merkezi kaydı
- Yeni IT Toolkit logosu, renk sistemi ve SVG ikon seti
- Global araç arama
- Canlı sistem özeti
- Temiz ve güvenilir kaynak politikası
- Windows için tek dosyalık EXE

## v0.4.0-preview.1 — Görev Merkezi

**Durum:** Tamamlandı — 29 Temmuz 2026

**Hedef:** İşlemleri görünür, izlenebilir ve kontrol edilebilir hâle getirmek.

- [x] Çalışan işlemler için ilerleme ve canlı çıktı paneli
- [x] Uygun işlemlerde işlem ağacıyla iptal desteği
- [x] Son 100 işlem için kalıcı yerel sonuç geçmişi
- [x] Başarılı, uyarılı ve başarısız durumlar için ortak bildirim sistemi
- [x] Yüzde çıktısı bulunan uzun görevlerde otomatik ilerleme algılama
- [x] Komut çıktısını panoya kopyalama ve UTF-8 rapor olarak dışa aktarma
- [x] Yönetici görevleri için açık harici-görev güvenlik sınırı
- [x] Süreç, hata kodu, iptal ve oturum kurtarma testleri

**Çıkış ölçütü:** Tamamlandı. Görevler arayüzü kilitlemeden çalışıyor; canlı
çıktı, sonuç ve hata bilgisi tek merkezden görülebiliyor.

## v0.5.0-preview.1 — Hızlı erişim

**Durum:** Tamamlandı — 29 Temmuz 2026

**Hedef:** Günlük teknisyen işlerini daha az tıklamayla tamamlamak.

- [x] Favori araçlar
- [x] Son kullanılanlar
- [x] `Ctrl+K` komut paleti
- [x] Araç sabitleme ve kişisel sıralama
- [x] Hazır bakım akışları: “Temel kontrol”, “Ağ onarımı”, “Teslim öncesi”
- [x] `Alt+1`, `Alt+2` ve `Alt+3` hızlı gezinme kısayolları
- [x] Bozuk veya eski tercih kayıtlarını güvenle temizleyen yerel tercih servisi
- [x] Favori, geçmiş, arama sıralaması ve hazır akış testleri

**Çıkış ölçütü:** Tamamlandı. Sık kullanılan bir araç `Ctrl+K` ile klavyeden
veya Hızlı Erişim sayfasından en fazla iki tıklamayla başlatılabiliyor.

## v0.5.1-hotfix.1 — Modül güvenilirliği

**Durum:** Mevcut yayın

**Hedef:** Mevcut modüllerin komut, paket ve cihaz önkoşullarını güvenilir
sonuç üretecek biçimde düzeltmek.

- [x] PowerShell ve boşluklu yol tırnaklamasını merkezi görev motorunda düzeltme
- [x] Çok adımlı görevlerde gerçek hata kodunu koruma
- [x] SMART, Office lisansı, hazır akış ve dinlenen portlar canlı doğrulaması
- [x] Güncel Winget kimlikleri ve resmi indirme sayfası yedekleri
- [x] Minidump klasörü bulunmayan cihazlar için açıklayıcı önkoşul sonucu
- [x] Geçici görev dosyalarını başarı, hata ve iptal sonunda temizleme
- [x] 23 otomatik regresyon testi

**Çıkış ölçütü:** Tamamlandı. Kritik salt okunur görevler gerçek çıktı üretiyor,
önceki komut hataları gizlenmiyor ve görev dosyaları geride kalmıyor.

## v0.6.0-beta — Akıllı tanılama

**Hedef:** Salt araç listesinden karar destek merkezine geçmek.

- Sistem sağlığı uyarıları ve önem dereceleri
- Disk alanı, pil sağlığı, güncelleme ve yeniden başlatma önerileri
- Tek tıkla tanılama özeti
- Teknisyen notları ve müşteri teslim raporu
- Cihaz profiline göre güvenli öneriler
- Tanılama sonuçlarında hassas veri maskeleme

**Çıkış ölçütü:** Üretilen önerilerin kaynağı ve gerekçesi kullanıcıya açıkça
gösterilmeli.

## v0.7.0-beta — Güvenli yetkili işlemler

**Hedef:** Yönetici işlemlerini daha kontrollü ve geri alınabilir yapmak.

- Ayrı, dar kapsamlı yetkili yardımcı süreç
- İşlem öncesi etki özeti
- Uygun görevlerde geri alma adımı
- Otomatik geri yükleme noktası seçeneği
- Denetim günlüğü
- Kritik görevler için iki aşamalı onay

**Çıkış ölçütü:** Yetki yükseltme yalnızca gerektiğinde yapılmalı ve kritik
değişiklikler denetlenebilir olmalı.

## v0.8.0-beta — Kalite ve uyumluluk

**Hedef:** Farklı Windows cihazlarında güvenilir davranış.

- Otomatik birim ve arayüz testleri
- Windows 10/11 uyumluluk matrisi
- Çoklu ekran ve yüksek DPI iyileştirmeleri
- Erişilebilirlik kontrolü
- Yapılandırılmış yerel hata kayıtları
- Performans ve açılış süresi optimizasyonu

**Çıkış ölçütü:** Ana akışlar temiz bir Windows test ortamında otomatik olarak
doğrulanmalı.

## v0.9.0-rc.1 — Dağıtım adayı

**Hedef:** v1.0 öncesi özellik dondurma ve dağıtım hazırlığı.

- Uygulama içi güncelleme denetimi
- Taşınabilir ve kurulumlu paket seçenekleri
- Kod imzalama altyapısı
- Eksiksiz kullanıcı ve teknisyen belgeleri
- İlk açılış ve güvenlik bilgilendirmesi
- Kalan arayüz ve performans düzeltmeleri

**Çıkış ölçütü:** Kritik açık hata bulunmamalı; yükseltme ve temiz kurulum
senaryoları doğrulanmalı.

## v1.0.0 — Kararlı sürüm

**Hedef:** Günlük kullanım için güvenilir ve belgelenmiş ürün.

- İmzalı Windows paketleri
- Kararlı güncelleme kanalı
- Tam görev geçmişi ve raporlama
- Onaylanmış güvenli araç kataloğu
- Kullanıcı, katkı ve güvenlik belgeleri
- Sürüm notları ve desteklenen Windows sürümleri

## Sürüm arası bakım

- Kritik güvenlik düzeltmesi: mümkün olan en kısa sürede `PATCH`
- Normal hata düzeltmesi: ilgili kilometre taşının bakım sürümü
- Yeni özellik: bir sonraki `MINOR` sürüm
- Geriye uyumsuz değişiklik: v1.0 sonrasında `MAJOR` sürüm
