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

**Durum:** Mevcut yayın

- CustomTkinter’dan PySide6 mimarisine geçiş
- Dokuz ana modülün yeni arayüze taşınması
- 64 işlem ve 32 resmi yazılım paketinin merkezi kaydı
- Yeni IT Toolkit logosu, renk sistemi ve SVG ikon seti
- Global araç arama
- Canlı sistem özeti
- Temiz ve güvenilir kaynak politikası
- Windows için tek dosyalık EXE

## v0.4.0-preview — Görev Merkezi

**Hedef:** İşlemleri görünür, izlenebilir ve kontrol edilebilir hâle getirmek.

- Çalışan işlemler için ilerleme ve canlı çıktı paneli
- Uygun işlemlerde iptal desteği
- Son işlemler ve sonuç geçmişi
- Başarılı, uyarılı ve başarısız durumlar için ortak bildirim sistemi
- Uzun görevlerde tahmini durum bilgisi
- Komut çıktısını panoya kopyalama ve rapor olarak dışa aktarma

**Çıkış ölçütü:** Bir işlem çalışırken kullanıcı arayüzü akıcı kalmalı; sonuç ve
hata bilgisi tek bir merkezden görülebilmeli.

## v0.5.0-preview — Hızlı erişim

**Hedef:** Günlük teknisyen işlerini daha az tıklamayla tamamlamak.

- Favori araçlar
- Son kullanılanlar
- `Ctrl+K` komut paleti
- Araç sabitleme ve kişisel sıralama
- Hazır bakım paketleri: “Temel kontrol”, “Ağ onarımı”, “Teslim öncesi”
- Klavye ile tam gezinme

**Çıkış ölçütü:** Sık kullanılan bir araç klavyeyle veya en fazla iki tıklamayla
başlatılabilmeli.

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
