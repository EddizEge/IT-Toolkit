# AGENTS.md — IT Toolkit Geliştirici ve Agent Rehberi

Bu belge, IT Toolkit üzerinde çalışan geliştiriciler ve yapay zekâ agent’ları
için güncel teknik rehberdir. Kod değişikliğine başlamadan önce bu dosyayı,
`ROADMAP.md` ve ilgili modül dosyalarını okuyun.

## Proje özeti

- **Ürün:** IT Toolkit — Windows Yönetim Merkezi
- **Geliştirici:** Ediz Ege Mercan
- **Mevcut yayın:** `v0.6.0-beta.2`
- **Hedef sistem:** Windows 10 ve Windows 11
- **Dil:** Python 3.12+
- **Arayüz:** PySide6 / Qt Widgets
- **Paketleme:** PyInstaller ile tek dosyalık taşınabilir EXE
- **Depo:** `https://github.com/EddizEge/IT-Toolkit`

Uygulama; sistem yönetimi, tanılama, ağ sorun giderme, veri taşıma, resmi
yazılım kurulumu ve Windows destek araçlarını tek arayüzde toplar. Kullanıcıya
görünen tüm metinler Türkçedir.

## Geçerli kod tabanı

Aktif uygulama `main_v2.py` ve `app_v2/` altında bulunur. Kök dizindeki eski
`main.py`, CustomTkinter tabanlı tarihsel sürümdür; yeni özellikler oraya
eklenmemeli ve güncel mimari için kaynak kabul edilmemelidir.

```text
IT-Toolkit/
├── main_v2.py                  # Aktif uygulama giriş noktası
├── app_v2/
│   ├── __init__.py             # Uygulama sürümü
│   ├── main_window.py          # Ana pencere, gezinme ve kısayollar
│   ├── command_palette.py      # Ctrl+K araç paleti
│   ├── registry.py             # Araç, anahtar ve paket kayıtları
│   ├── widgets.py              # Ortak Qt bileşenleri
│   ├── dialogs.py              # Kurulum ve Wi-Fi QR pencereleri
│   ├── update_dialog.py        # Sürüm denetimi, indirme ve yeniden başlatma
│   ├── icons.py                # Kod içinde tutulan SVG ikonlar
│   ├── theme.py                # Renk, tipografi ve QSS tema sistemi
│   ├── pages/                  # Uygulama ekranları
│   │   └── feedback.py         # GitHub geri bildirim ve günlük önizleme ekranı
│   └── services/               # Görev, komut, tercih, sağlık ve sistem servisleri
│       ├── error_logging.py    # Dönen yerel log ve hassas veri maskeleme
│       ├── feedback_service.py # Rapor metni ve GitHub issue bağlantısı
│       └── update_service.py   # GitHub Release, SHA-256 ve EXE değiştirme
├── tests/                      # unittest tabanlı otomatik testler
├── assets/brand/               # Logo ve Windows uygulama ikonları
├── docs/                       # Marka, ekran görüntüsü ve sürüm notları
├── .github/workflows/          # Windows build ve Release otomasyonu
├── Baslat_v2.bat               # Geliştirme başlatıcısı
├── Derle_v2.bat                # Yerel EXE derleme aracı
├── requirements.txt            # Çalışma zamanı bağımlılıkları
└── requirements-dev.txt        # Test, lint ve paketleme bağımlılıkları
```

## Ana mimari

### Pencere ve gezinme

`app_v2/main_window.py` içindeki `MainWindow`, sol menüyü, üst çubuğu ve
`QStackedWidget` tabanlı sayfa geçişlerini yönetir. Sayfalar ilk açılışta
oluşturulur ve yeniden kullanılır.

Klavye kısayolları:

- `Ctrl+K`: Komut paleti
- `Alt+1`: Sistem Özeti
- `Alt+2`: Hızlı Erişim
- `Alt+3`: Görev Merkezi
- `Alt+4`: Akıllı Tanılama

Yeni bir ana sayfa eklendiğinde sayfa fabrikası, sol menü, başlık eşlemesi,
ikon kaydı ve gerekiyorsa kısayol birlikte güncellenmelidir.

### Merkezi araç kaydı

`app_v2/registry.py` bütün araç ve paketlerin tek kaynağıdır:

- `ToolAction`: Çalıştırılabilir araç veya komut
- `ToggleAction`: Durumu okunup açılıp kapatılabilen Windows ayarı
- `PackageItem`: Winget paketi veya resmi üretici bağlantısı
- `PAGE_ACTIONS`: Arama ve sayfaların kullandığı merkezi eylem eşlemesi

Yeni araçlar doğrudan sayfa içine gömülmemeli; merkezi kayda eklenmelidir.
Her kayıt benzersiz bir anahtar, anlaşılır Türkçe başlık, açıklama, kategori,
yetki gereksinimi ve doğru risk seviyesi içermelidir.

### Görev yürütme

`app_v2/services/task_manager.py`, uzun süren standart görevleri `QProcess`
üzerinden çalıştırır; canlı çıktı, ilerleme, iptal ve yerel geçmiş üretir.
`command_runner.py` komut dosyası oluşturma, yükseltilmiş görev ve geçici dosya
temizliğini yönetir. PowerShell komutları için `command_builder.py` içindeki
yardımcılar kullanılmalıdır.

- Yaklaşık 100 ms’den uzun iş ana arayüz iş parçacığında çalıştırılmamalıdır.
- Uygun görevler Görev Merkezi’ne bağlanmalıdır.
- Çok adımlı komutlarda gerçek hata kodu korunmalıdır.
- Geçici komut dosyaları başarı, hata ve iptal sonunda temizlenmelidir.
- UAC ile ayrı sürece devredilen görevlerin canlı çıktısının yakalanamadığı
  arayüzde açıkça belirtilmelidir.

### Sistem izleme ve akıllı tanılama

`system_monitor.py`, CPU, RAM, disk ve donanım sorgularını `QThreadPool`
üzerinden toplar. `health_service.py`, salt okunur Windows verilerinden
açıklanabilir 0–100 sağlık puanı ve önem seviyeli bulgular üretir.

- GPU sorguları fiziksel PCI aygıtlarını filtrelemeye devam etmelidir.
- Ağ bağdaştırıcılarında sanal cihazlar dışarıda bırakılmalıdır.
- Eksik veya erişilemeyen veri sağlıklı kabul edilmemelidir; “bilinmiyor”
  olarak güvenli biçimde ele alınmalıdır.
- Her sağlık bulgusu kanıt, öneri ve puan etkisini açıklamalıdır.
- Dışa aktarılan raporlarda kullanıcı adı, IP ve benzeri hassas veriler
  maskelenmelidir.
- Müşteri raporu HTML ve PDF olarak aynı güvenli içerikten üretilmeli; kartlar
  sayfalar arasında bölünmemeli ve teknisyen notları da maskelenmelidir.

### Yerel kullanıcı verileri

Tercihler ve görev geçmişi `%LOCALAPPDATA%\IT Toolkit\` altında saklanır.
Bozuk, eski veya tanınmayan kayıtlar uygulamanın açılmasını engellememelidir.
Depoya kullanıcıya ait yerel veri veya tanılama çıktısı eklenmemelidir.

### Hata günlüğü ve geri bildirim

`error_logging.py`, uygulama başlangıcı/kapanışı, yakalanmayan Python hataları
ve başarısız görev bildirimleri için dönen yerel günlük tutar. Günlükler
`%LOCALAPPDATA%\IT Toolkit\logs\` altındadır; kaynak depoya yazılmaz.
`feedback_service.py`, paylaşılacak metni maskeleyip GitHub issue formunu
önceden doldurur. Depoya erişim anahtarı veya kullanıcı kimlik bilgisi
gömülmemelidir.

- Ham günlük otomatik yüklenmemeli; kullanıcı önizleme ve açık onay vermelidir.
- Kullanıcı yolu, e-posta, IP, MAC, ürün anahtarı ve gizli anahtar alanları
  paylaşım öncesi maskelenmelidir.
- Bağlantı uzunluğu sınırlanmalı; tam güvenli rapor panoya kopyalanmalıdır.
- Güvenlik açıkları herkese açık issue yerine `SECURITY.md` kanalına
  yönlendirilmelidir.
- Geri bildirim ekranı hata oluşmasa da üst çubuktan erişilebilir kalmalıdır.

### Uygulama güncellemeleri

`update_service.py`, resmi GitHub Releases API’sinden yayın listesini alır;
çalışan beta sürümleri yeni ön sürümleri, kararlı sürümler yalnızca kararlı
yayınları görür. `update_dialog.py` durum, sürüm notu, indirme ilerlemesi ve
kullanıcı onayını yönetir.

- Güncelleme kaynağı yalnızca `EddizEge/IT-Toolkit` GitHub Release varlıklarıdır.
- Dosya adı etikete tam uymalıdır: `IT_Toolkit_<etiket>.exe`.
- Release varlığında `sha256:` özeti veya eşleşen `.sha256` dosyası yoksa
  güncelleme reddedilmelidir.
- SHA-256 doğrulaması geçmeden EXE çalıştırılmamalı veya mevcut dosyanın yerine
  geçirilmemelidir.
- Değiştirme işlemi mevcut EXE’nin yedeğini almalı ve hata durumunda geri
  yüklemelidir.
- Otomatik denetim arayüzü engellememeli; indirme ve yeniden başlatma kullanıcı
  onayı olmadan yapılmamalıdır.
- Kaynaktan çalıştırırken Python kaynakları otomatik değiştirilmemelidir.
- GitHub erişim anahtarı veya kimlik bilgisi uygulamaya gömülmemelidir.

## Ekranlar

| Ekran | Sorumluluk |
| --- | --- |
| Sistem Özeti | Canlı CPU, RAM, disk, donanım ve işletim sistemi özeti |
| Akıllı Tanılama | Sağlık puanı, bulgular, öneriler ve müşteri raporu |
| Hızlı Erişim | Favoriler, son kullanılanlar ve hazır akışlar |
| Görev Merkezi | Canlı çıktı, iptal, sonuç ve son 100 işlem |
| Sistem Yönetimi | Temizlik, onarım, SMART, yazıcı ve geri yükleme |
| Ağ ve İnternet | IP/DNS, bağlantı analizi, Wi-Fi QR ve ağ araçları |
| Hızlı Başlat | Windows yönetim konsolları ve kurtarma araçları |
| Veri Taşıma | Profil yedekleme, envanter, sahiplik ve disk işlemleri |
| Program Kurulumu | Resmi Winget paketleri ve üretici kaynakları |
| Microsoft Office | Resmi kurulum, onarım, güvenli mod ve lisans tanılama |
| E-Posta / Outlook | Profil, güvenli mod, arşiv ve resmi destek |
| Windows ISO / USB | Resmi ISO, Rufus/Fido ve lisans durumu |
| Geri Bildirim | Maskelenmiş hata günlüğü, rapor önizleme ve GitHub issue akışı |
| Güncellemeler | GitHub sürüm denetimi, doğrulanmış indirme ve yeniden başlatma |

## Tasarım ve kullanıcı deneyimi kuralları

- Kullanıcıya görünen bütün metinler doğal ve anlaşılır Türkçe olmalıdır.
- Renk ve tipografi için `app_v2/theme.py`, ikonlar için `app_v2/icons.py`
  kullanılmalıdır; sayfalara rastgele renk veya emoji eklenmemelidir.
- Ortak kart, eylem ve bildirimler `app_v2/widgets.py` üzerinden tekrar
  kullanılmalıdır.
- Arayüz en az `1080x700` boyutunda, farklı DPI değerlerinde ve uzun Türkçe
  metinlerle kontrol edilmelidir.
- Kritik işlemden önce etki açıkça anlatılmalı ve kullanıcı onayı alınmalıdır.
- Hata mesajı yalnızca “başarısız” dememeli; güvenli bir sonraki adımı da
  belirtmelidir.

## Güvenlik politikası

- Yalnızca yerleşik Windows araçları, Winget ve resmi üretici kaynakları
  kullanılabilir.
- Korsan yazılım, lisans atlatma, parola çözme, güvenlik ürünü etkisizleştirme
  veya güvenilir olmayan indirme kaynağı eklenemez.
- Salt okunur tanılama mümkünse yönetici yetkisi istememelidir.
- Ayar değiştiren eylemler en dar yetkiyle çalışmalı; `admin=True` yalnızca
  gerçekten gerekli olduğunda kullanılmalıdır.
- Veri silme, sahiplik ve açılış yapılandırması gibi işlemler `danger`; önemli
  sistem değişiklikleri en az `caution` risk seviyesinde olmalıdır.
- Uygun işlemlerde geri alma yolu veya geri yükleme noktası önerilmelidir.

## Geliştirme ve doğrulama

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python main_v2.py
```

Her anlamlı değişiklikten sonra çalıştırın:

```powershell
ruff check app_v2 tests main_v2.py
python -m compileall -q app_v2 main_v2.py
python -m unittest discover -s tests -v
```

Yeni davranış için ilgili `tests/test_*.py` dosyasına regresyon testi ekleyin.
Arayüz değişikliklerini uygulamayı gerçekten açarak doğrulayın. Windows ayarı
değiştiren canlı testleri güvenli bir test cihazı veya sanal makine olmadan
çalıştırmayın.

## Derleme ve yayın

Yerel EXE:

```powershell
.\Derle_v2.bat
```

Çıktı `dist/IT_Toolkit_<sürüm>.exe` olur. `main` dalına gönderilen kod GitHub
Actions üzerinde lint, test, derleme ve artifact kontrollerinden geçer. GitHub
Release yayımlandığında `.github/workflows/release.yml`, etiket ile
`app_v2/__init__.py` sürümünü karşılaştırır; EXE ve SHA-256 dosyasını yayına
ekler.

Bir sürüm tamamlanırken birlikte güncellenmesi gerekenler:

1. `app_v2/__init__.py`
2. `ROADMAP.md`
3. `CHANGELOG.md`
4. `README.md` sürüm ve kanal rozetleri
5. `docs/releases/<sürüm>.md`
6. `Derle_v2.bat` varsayılan sürümü
7. Git etiketi ve GitHub Release

Ayrıntılı yayın akışı için `RELEASING.md` izlenmelidir.

Release varlıkları yüklendikten sonra bir önceki sürüm numarasıyla güncelleme
denetimi çalıştırılmalı; yeni etiketin seçildiği, EXE’nin indirildiği ve
SHA-256 doğrulamasının başarılı olduğu ayrıca doğrulanmalıdır.

### Zorunlu GitHub geri bildirim kontrolü

Her sürüm numarası yükseltme çalışmasının başında ve GitHub Release
yayımlanmadan hemen önce agent şu görevi tamamlamalıdır:

1. `is:issue is:open "[Uygulama Geri Bildirimi]"` aramasıyla açık uygulama
   geri bildirimlerini kontrol et.
2. Her bildirimi yeniden üretildi, bilgi bekleniyor, yinelenen, planlandı veya
   düzeltildi şeklinde sınıflandır.
3. Kritik veri kaybı, güvenlik veya uygulamanın açılmaması sorunları çözülmeden
   yeni sürümü yayımlama.
4. Çözülen issue numaralarını sürüm notuna; ertelenen doğrulanmış sorunları
   “Bilinen sorunlar” bölümüne ekle.
5. Sürüm yükseltme tesliminde kaç açık geri bildirimin incelendiğini ve hangi
   issue’ların sürümü etkilediğini kullanıcıya bildir.

Bu kontrol atlanabilir bir öneri değil, yayın kontrol listesinin zorunlu
parçasıdır.

## Değişiklik kontrol listesi

- [ ] Değişiklik aktif `app_v2` mimarisinde yapıldı.
- [ ] Kullanıcı metinleri Türkçe ve anlaşılır.
- [ ] Uzun işlemler arayüz iş parçacığını engellemiyor.
- [ ] Yeni araç merkezi kayda ve global aramaya bağlı.
- [ ] Yetki ve risk seviyesi doğru.
- [ ] Yalnızca güvenilir/resmi kaynaklar kullanılıyor.
- [ ] Testler ve lint başarılı.
- [ ] Yeni hata yolları yerel günlüğe güvenli biçimde yansıyor.
- [ ] Açık GitHub uygulama geri bildirimleri kontrol edildi.
- [ ] Güncelleme varlık adı ve SHA-256 doğrulaması kontrol edildi.
- [ ] İlgili belge ve sürüm notları güncel.
- [ ] Çalışma alanındaki ilgisiz kullanıcı değişiklikleri korunuyor.
