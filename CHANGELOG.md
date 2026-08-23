# Değişiklik Günlüğü

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) yaklaşımını
izler ve proje [SemVer](https://semver.org/) kullanır.

## [Yayınlanmadı]

### Eklendi

- v0.7 için merkezi `OperationImpact` güvenlik politikası ve ayrıntılı teknik
  uygulama planı
- Seçilen klasör, sürücü, süre ve paketleri değişmez biçimde taşıyan
  `ExecutionPlan` modeli
- Yönetici yetkisi isteyen işlemlerde etki, hedef, UAC, kesinti ve geri alma
  bilgisini gösteren ortak onay penceresi
- Kritik işlemlerde `ONAYLA` yazılmasını gerektiren ikinci son onay aşaması
- Kritik araçlar ve SMBv1 yön değişiklikleri için açık etki/geri alma bilgileri
- `%LOCALAPPDATA%\IT Toolkit\audit\` altında boyut sınırında dönen, maskelenmiş
  ve yapılandırılmış JSONL işlem denetim günlüğü
- Her satır için ayrı `event_id` ve işlem yaşam döngüsünü birleştiren ortak
  `plan_id` korelasyonu
- Görev Merkezi ayrıntısında kısa, araç ipucu ve dışa aktarılan görev raporunda
  tam denetim kimliği görünürlüğü
- Uzak Masaüstü ve SMBv1 açma işlemleri için kullanıcı tercihli, yeni nokta
  kimliği ve sıra numarasıyla doğrulanan Windows geri yükleme noktası akışı
- Windows Update, hazırda bekletme, SMBv1 ve USB yazma korumasında doğrulanmış
  önceki duruma; zamanlı kapatmada kayıtlı iptal eylemine dayanan güvenli geri
  alma planları
- Görev Merkezi'nde yalnız uygun başarılı görevlerde etkinleşen “Değişikliği
  geri al” düğmesi ile geri yükleme ve geri alma durum görünürlüğü

### Değiştirildi

- Sistem Yönetimi, diğer araç sayfaları ve teknisyen hazır akışları aynı
  merkezi güvenlik kapısını kullanıyor
- `normal` düzeyinde olsa bile yönetici isteyen işlemler artık UAC açılmadan önce
  kullanıcıya etki özeti gösteriyor
- SMBv1 açma işlemi kritik, kapatma işlemi dikkat düzeyinde değerlendiriliyor
- Sahiplik, boş alan temizleme, zamanlı kapatma ve toplu kurulum akışları
  parametreleri önce topluyor; gerçek hedef merkezi onayda gösteriliyor
- Araç, temel ayar ve teknisyen hazır akışları hazırlama, onay, başlangıç, iptal,
  UAC devri ve sonuç olaylarını aynı `plan_id` ile ilişkilendiriyor
- Bozuk tek bir görev geçmişi veya denetim günlüğü satırı artık diğer geçerli
  kayıtların yüklenmesini engellemiyor
- Geçici sonuç yazma hataları sınırlı artan aralıklarla, aynı oturumda ve
  kapanışta yeniden deneniyor; denetim sonucu bekleyen görevler temizleme ve
  geçmiş sınırlandırması sırasında korunuyor
- Eski görev geçmişi doğrulanmış terminal denetim sonucuyla uzlaştırılıyor
- Geri yükleme ve geri alma çocuk işlemleri yeni `plan_id` ile oluşturuluyor ve
  `parent_plan_id` üzerinden ana işleme bağlanıyor
- Klasör sahipliği yerel Yöneticiler grubunu locale bağımsız SID ile hedefliyor;
  sürücü, UNC paylaşım ve Windows sistem kökleri toplu değişiklikten korunuyor
- Güvenli Mod başlatma akışı kalıcı BCD zorlaması yerine Windows'un tek açılışlık
  Başlangıç Ayarları seçimine taşındı

### Güvenlik

- Kritik işlemler iki onay tamamlanmadan görev yöneticisine veya UAC akışına
  ulaşamıyor
- İptal varsayılan seçim olarak korunuyor; kritik başlatma düğmesi doğru yazılı
  onaya kadar devre dışı kalıyor
- Winget paketi içeren dinamik kurulumlar çözümlenmiş yönetici gereksinimiyle UAC
  öncesi etki özetine giriyor; onay iptalinde paket veya bağlantı açılmıyor
- Kayıtlı bir yönetici işleminin yetki gereksinimi işlem planında düşürülemiyor
- Denetim günlüğüne komut, görev çıktısı, URL veya gerçek hedef yazılmıyor;
  izin verilen metin alanları ortak hassas veri maskelemesinden geçiriliyor
- Zorunlu denetim kaydı yazılamayan yetkili veya riskli işlem güvenli biçimde
  engelleniyor ve kullanıcıya izleyebileceği sonraki adım gösteriliyor
- Olay/durum birleşimleri, görev kimlikleri ve hassas veri içerebilecek işlem
  anahtarları sıkı şema doğrulamasından geçiriliyor
- Access/refresh token, client secret, Basic/Bearer kimlik doğrulaması, URI
  kullanıcı bilgisi, IPv6 ve UNC yolları ortak paylaşım filtresinde maskeleniyor
- Geri yükleme noktası yalnız yeni ve tam eşleşen kayıt görüldüğünde başarılı
  sayılıyor; doğrulama başarısızlığında ana işlem varsayılan olarak duruyor
- Geri alma yalnız yerelde doğrulanmış başarıdan sonra ve güncel ayar durumu
  değişmemişse çalışıyor; harici UAC devri hiçbir zaman başarı sayılmıyor
- Geri alma çocuk planı merkezi kayıtla eylem, komut, yetki, başarı kodu ve etki
  düzeyinde birebir doğrulanıyor; normal görev API'si üst işlem bağı kabul etmiyor
- Restore, korumalı RDP/SMB ve geri alma yürütücüleri PowerShell ile yerel
  Windows araçlarını doğrulanmış mutlak System32 yollarından başlatıyor; bu
  akışlarda geçici komut dosyası veya PATH çözümlemesi kullanılmıyor. Genel
  görev kabuğu ve süreç ağacı temizleyicisi de mutlak `cmd.exe` ve
  `taskkill.exe` yollarını kullanıyor
- Toggle geri alma önkoşulları yükseltilmiş çocuk süreçte ilk değişiklikten
  hemen önce yeniden doğrulanıyor; sorgu hatası, zaman aşımı veya durum
  uyuşmazlığı yan etki oluşturmadan görevi durduruyor
- Daha önce yürütülmüş plan kimlikleri yeniden kullanılamıyor; bozuk geçmişteki
  yinelenen kök plan kimliklerinin geri alma durumu güvenli biçimde `unknown`
  yapılıyor
- Restore cmdlet'leri doğrulanmış `Microsoft.PowerShell.Management`
  manifestinden tam modül adıyla çağrılıyor
- Çöken doğrulayıcı süreç başarı kodu döndürse bile geri yükleme noktası başarılı
  sayılmıyor; uygulama kapanırken bekleyen ana işlemler iptal ediliyor
- Sistem Koruması, geri yükleme sıklığı, kurum politikası ve VBS ayarları
  uygulama tarafından sessizce değiştirilmiyor

### Kalite

- Güvenlik politikası, onay pencereleri, araç/toggle ve hazır akış geçişleri
  için regresyon testleri eklendi
- Hedef seçimi, seçim/onay iptali, dinamik Winget yetkisi ve son kullanılanlar
  davranışı için uçtan uca sayfa testleri eklendi
- Paketlenmiş geliştirme EXE’sinde iki aşamalı onay akışı görsel olarak
  ve dinamik Winget paket planı doğrulandı; test sırasında hiçbir Windows ayarı
  veya paketi değiştirilmedi
- Toplam 178 otomatik test başarıyla tamamlandı
- JSONL alan izin listesi, maskeleme, dosya döndürme, eşzamanlı yazma, bozuk
  satır dayanıklılığı ve görev korelasyonu için Aşama C regresyon testleri eklendi
- Restore doğrulaması, ikinci onay, parent/child korelasyonu, tek kullanımlık
  geri alma, durum kayması, yeniden açılış ve Task Center görünürlüğü için Aşama
  D regresyon testleri eklendi; gerçek Windows ayarı değiştirilmedi

## [0.6.0-beta.2] - 2026-08-21

### Eklendi

- GitHub Releases üzerinden beta ve kararlı sürümleri denetleyen güncelleme
  penceresi
- GitHub Release varlığındaki SHA-256 özetini zorunlu doğrulayan indirme akışı
- Taşınabilir EXE için kullanıcı onaylı değiştirme, yedekleme ve yeniden
  başlatma mekanizması
- Akıllı Tanılama sonucuna bağlı teknisyen notları
- Cihaz türüne özel güvenli kullanım önerileri
- Maskelenmiş teknisyen notları ve bulgular içeren HTML/PDF müşteri teslim
  raporu
- Uygulama başlangıcı, kapanışı, yakalanmayan hatalar ve başarısız görevler için
  dönen yerel hata günlüğü
- Uygulama içi Geri Bildirim ve Hata Günlüğü ekranı
- Kategori, açıklama, yeniden üretme adımları ve tanılama verileriyle önceden
  doldurulan GitHub issue formu
- Geri bildirim raporunu panoya kopyalama ve yerel günlük klasörünü açma

### Değiştirildi

- Geliştirici ve agent rehberi güncel PySide6 mimarisi, güvenlik sınırları,
  doğrulama komutları ve yayın süreciyle eşleştirildi
- README yayın kanalı rozeti mevcut beta aşamasını gösterecek şekilde düzeltildi
- Her sürüm yükseltmesinden önce açık uygulama geri bildirimlerinin incelenmesi
  zorunlu yayın adımı yapıldı
- Güncelleme denetimi açılıştan sonra arayüzü engellemeden çalışıyor; yeni sürüm
  olduğunda sol menüde görünür bildirim gösteriliyor

### Güvenlik

- Paylaşılan hata kayıtlarında kullanıcı yolu, e-posta, IP, MAC adresi, ürün
  anahtarı ve yaygın gizli anahtar alanları otomatik maskeleniyor
- GitHub erişim anahtarı uygulamaya gömülmüyor; son gönderim kullanıcının kendi
  GitHub oturumunda açık onayla yapılıyor
- Kaynaktan çalıştırma modunda otomatik dosya değiştirme yapılmıyor
- İndirilen EXE, beklenen SHA-256 özeti eşleşmeden çalıştırılmıyor

### Kalite

- Sürüm karşılaştırma, yayın seçimi, doğru varlık seçimi, SHA-256 doğrulaması ve
  değiştirme betiği için 7 güncelleme regresyon testi eklendi
- Cihaz profili ve maskelenmiş müşteri raporu senaryoları test edildi
- Toplam 44 otomatik test; 1080×700 arayüz ve iki sayfalık A4 PDF görsel
  doğrulaması tamamlandı

## [0.6.0-beta.1] - 2026-08-12

### Eklendi

- Disk, bellek, pil, Windows Update ve yeniden başlatma durumunu değerlendiren
  yeni Akıllı Tanılama modülü
- Uyarıların ağırlığına göre hesaplanan açıklanabilir 0–100 sağlık puanı
- Kritik, uyarı, bilgi ve iyi seviyelerinde sıralanmış tanılama bulguları
- Her bulgu için ölçülen kanıt, güvenli öneri ve puan etkisi
- Tek tıkla yeniden tarama ve tanılama raporunu panoya kopyalama
- Tanılama sonucunu Görev Merkezi geçmişine kaydetme
- Akıllı Tanılama için yeni sol menü ikonu ve `Alt+4` kısayolu

### Değiştirildi

- Disk doluluk değerlendirmesi yalnızca yüzdeye değil kullanılabilir mutlak boş
  alana da bakıyor; büyük disklerde yanıltıcı kritik uyarılar önleniyor
- Sistem özeti disk sorgusundaki PowerShell null filtrelemesi düzeltildi
- Sol menü sürüm alanı beta kanalını ve Akıllı Tanılama odağını gösteriyor

### Güvenlik

- Tanılama yalnızca salt okunur yerel Windows ve donanım sorguları kullanıyor
- Kopyalanabilir sağlık raporu kullanıcı adı ve IP adresi içermiyor
- Sağlık önerileri sistem ayarlarını otomatik değiştirmiyor

### Kalite

- Sağlıklı, uyarılı, kritik, eksik veri ve tek kayıt senaryoları için sağlık
  motoru testleri eklendi
- Toplam 29 otomatik test, gerçek Windows veri toplama ve masaüstü arayüz
  doğrulaması tamamlandı

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

[Yayınlanmadı]: https://github.com/EddizEge/IT-Toolkit/compare/v0.6.0-beta.2...HEAD
[0.6.0-beta.2]: https://github.com/EddizEge/IT-Toolkit/compare/v0.6.0-beta.1...v0.6.0-beta.2
[0.6.0-beta.1]: https://github.com/EddizEge/IT-Toolkit/compare/v0.5.1-hotfix.1...v0.6.0-beta.1
[0.5.1-hotfix.1]: https://github.com/EddizEge/IT-Toolkit/compare/v0.5.0-preview.1...v0.5.1-hotfix.1
[0.5.0-preview.1]: https://github.com/EddizEge/IT-Toolkit/compare/v0.4.0-preview.1...v0.5.0-preview.1
[0.4.0-preview.1]: https://github.com/EddizEge/IT-Toolkit/compare/v0.3.0-preview.1...v0.4.0-preview.1
[0.3.0-preview.1]: https://github.com/EddizEge/IT-Toolkit/releases/tag/v0.3.0-preview.1
