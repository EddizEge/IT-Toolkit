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

**Durum:** Tamamlandı — 29 Temmuz 2026

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

## v0.6.0-beta.1 — Akıllı tanılama temeli

**Durum:** Tamamlandı — 12 Ağustos 2026

**Hedef:** Salt araç listesinden karar destek merkezine geçmek.

- [x] Sistem sağlığı uyarıları ve önem dereceleri
- [x] Açıklanabilir 0–100 sağlık puanı
- [x] Disk alanı, fiziksel disk, bellek ve pil sağlığı kontrolleri
- [x] Windows güncelleme ve yeniden başlatma önerileri
- [x] Tek tıkla tanılama özeti
- [x] Her bulgu için kanıt, öneri ve puan etkisi
- [x] Kopyalanabilir raporda hassas veri maskeleme

**Beta.1 çıkış ölçütü:** Tamamlandı. Üretilen önerilerin ölçülen kanıtı,
gerekçesi ve puan etkisi kullanıcıya açıkça gösteriliyor.

## v0.6.0-beta.2 — Raporlama ve geri bildirim

**Durum:** Mevcut yayın — 21 Ağustos 2026

**Hedef:** Tanılama sonuçlarını teknisyen raporuna dönüştürmek ve sahadaki
kullanıcılardan güvenli, sürümle ilişkilendirilmiş geri bildirim toplamak.

- [x] Teknisyen notları
- [x] Müşteri teslim raporu şablonu ve HTML/PDF dışa aktarma
- [x] Cihaz türüne göre genişletilmiş güvenli öneriler
- [x] Dönen yerel hata günlüğü ve yakalanmayan hata kaydı
- [x] Paylaşım öncesi hassas veri maskeleme ve önizleme
- [x] Uygulama içi GitHub geri bildirim ekranı
- [x] Önceden doldurulan GitHub issue formu ve panoya güvenli rapor
- [x] Her sürüm yükseltmesinde zorunlu açık feedback kontrolü
- [x] GitHub Releases üzerinden uygulama içi güncelleme denetimi
- [x] SHA-256 doğrulamalı indirme ve onaylı yeniden başlatma akışı

**Çıkış ölçütü:** Tamamlandı. Teknisyen aynı tanılama sonucuna not ve müşteri
raporu ekleyebiliyor; kullanıcılar maskelenmiş hata/öneri raporunu GitHub
üzerinden iletebiliyor ve doğrulanmış yeni sürümü uygulama içinden kurabiliyor.

## v0.7.0-beta — Güvenli yetkili işlemler

**Durum:** Geliştiriliyor — Aşama A, B ve C tamamlandı (23 Ağustos 2026)

**Hedef:** Yönetici işlemlerini daha kontrollü ve geri alınabilir yapmak.

- [x] İşlem öncesi etki özeti ve kritik görevler için iki aşamalı onay
- [x] Gerçek hedefi ve yetkiyi taşıyan parametreye duyarlı işlem planı
- [x] `plan_id` bağlantılı, dönen ve hassas veri içermeyen denetim günlüğü
- [x] Görev Merkezi’nde denetim kimliği görünürlüğü
- [ ] Uygun görevlerde geri alma adımı
- [ ] Otomatik geri yükleme noktası seçeneği
- [ ] Ayrı, dar kapsamlı yetkili yardımcı süreç

**Çıkış ölçütü:** Yetki yükseltme yalnızca gerektiğinde yapılmalı ve kritik
değişiklikler denetlenebilir olmalı.

Ayrıntılı uygulama aşamaları ve kabul ölçütleri için
[`docs/plans/v0.7.0-beta.md`](docs/plans/v0.7.0-beta.md) belgesine bakın.

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
