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
│   ├── action_confirmation.py  # Ortak etki özeti ve kritik son onay
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
│       ├── action_safety.py    # Risk politikası, etki ve değişmez işlem planı
│       ├── audit_log.py        # Dönen, maskeli JSONL işlem denetim günlüğü
│       ├── recovery.py         # Doğrulamalı, izin listeli geri yükleme noktası
│       ├── undo_execution.py   # Dosyasız geri alma ve korumalı eylem yürütücüsü
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

### İşlem güvenliği

`app_v2/services/action_safety.py`, araç, ayar ve hazır akış kayıtlarını
`OperationImpact` modeline dönüştürür; çözümlenmiş hedef ve yetki bilgisiyle
değişmez `ExecutionPlan` üretir. `app_v2/action_confirmation.py`, bütün
sayfaların kullandığı ortak etki özeti ve kritik son onay pencerelerini yönetir.

- Yönetici isteyen `normal` işlemler ve tüm `caution` işlemler tek aşamalı etki
  özeti kullanmalıdır.
- `danger` işlemler etki özeti ile `ONAYLA` yazılı son onaydan geçmelidir.
- UAC, görev başlatma ve son kullanılan kaydı gerekli onaylardan önce
  oluşmamalıdır.
- Hedef, süre veya paket seçen özel araçlarda handler önce parametreleri
  toplamalı ve `ExecutionPlan | None` döndürmelidir; seçim iptali `None` ile
  sonuçlanmalıdır.
- Yalnızca sistem durumunu değiştirmeyen pencere/önizleme akışları
  `ui_handlers` kullanmalıdır; bu akışlar da callback çağrısından önce merkezi
  etki politikasından geçmelidir.
- Sayfa alt sınıfları doğrudan yönetici komutu başlatmamalı; çözümlenmiş plan
  `ToolsPage` içindeki tek yürütme kapısından geçmelidir.
- Kayıtta gerekli olan yönetici yetkisi planda düşürülemez. Dinamik olarak
  yönetici isteyen kurulumlar gerçek planda `admin_required=True` olmalıdır.
- Aynı plandaki tarayıcı bağlantıları da onay tamamlanmadan açılmamalıdır.
- Kritik kayıtlar açık `impact`, `interruption` ve `rollback` bilgisi
  taşımalıdır; genel varsayılan metne bırakılmamalıdır.
- Sayfalara doğrudan `QMessageBox` tabanlı risk onayı eklenmemeli;
  `confirm_operation` kullanılmalıdır.
- Hedef veya süre seçen özel akışlar, parametreleri topladıktan sonra hedefi
  görünen değişmez bir işlem planı üretmelidir.

v0.7 geliştirme aşamaları ve tamamlanma ölçütleri için
`docs/plans/v0.7.0-beta.md` izlenmelidir.

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

### İşlem denetim günlüğü

`app_v2/services/audit_log.py`, v0.7 işlem planlarının yaşam döngüsünü
`%LOCALAPPDATA%\IT Toolkit\audit\operations.jsonl` altında dönen yerel JSONL
kayıtlarıyla izler. `ExecutionPlan.plan_id`, hazırlama aşamasından görev
sonucuna kadar bütün olayların ortak korelasyon kimliğidir; her JSONL satırı
ayrıca kendi benzersiz `event_id` değerini taşır.

- Hazırlama, kullanıcı vazgeçmesi, onay, görev başlangıcı, iptal isteği, UAC
  devri ve sonuç olayları aynı `plan_id` ile ilişkilendirilmelidir.
- Denetim kayıtları yalnızca izin verilen yapılandırılmış alanları içermeli;
  komut, görev çıktısı, URL veya gerçek hedef hiçbir koşulda yazılmamalıdır.
- Başlık ve kategori gibi kullanıcıya görünen alanlar yazılmadan önce ortak
  hassas veri maskelemesinden geçmelidir.
- Olay ve durum alanları birbiriyle uyumlu olmalı; plan bağlantılı görev
  kimlikleri uygulamanın ürettiği 32 karakterli küçük hexadecimal biçimden
  sapmamalıdır.
- Yönetici isteyen veya risk seviyesi `normal` olmayan işlem, zorunlu hazırlama
  ya da onay kaydı yazılamıyorsa güvenli biçimde başlatılmamalıdır.
- Geçici sonuç yazma hataları sınırlı artan aralıklarla aynı oturumda ve
  kapanışta yeniden denenmeli; sonucu henüz yazılamayan görevler geçmiş
  temizliği veya sınırlandırması sırasında korunmalıdır.
- Geçmiş ile günlük çelişirse doğrulanmış terminal günlük sonucu kullanılmalıdır.
- Genel komut yolunda UAC'ye devredilen ve sonucu yakalanamayan görev
  `delegated` olarak kaydedilmeli; harici sürecin gerçek tamamlanma sonucu
  yakalanmış gibi gösterilmemelidir. `recovery.py` ve `undo_execution.py`
  içindeki dosyasız sarmallar yükseltilmiş alt süreci bekleyip gerçek çıkış
  kodunu aktarır; bu akışlar `delegated` olarak işaretlenmemelidir.
- `TaskRecord.plan_id` eski görev geçmişleriyle geriye uyumludur. Bozuk bir
  kayıt bütün görev geçmişinin yüklenmesini engellememelidir.
- Görev Merkezi listesi kimlikle kalabalıklaştırılmamalı; seçili görevde kısa
  denetim kimliği, araç ipucunda ve dışa aktarılan raporda tam kimlik
  gösterilmelidir.

### Geri yükleme noktası ve güvenli geri alma

`app_v2/services/recovery.py`, yalnız merkezi politikada izin verilen eylemler
için Windows geri yükleme noktası oluşturur. `RecoveryPolicy`, ana ve geri alma
işlemlerinin uygunluğunu belirler; çocuk planlar yeni `plan_id` alır ve ana
işleme `parent_plan_id` ile bağlanır.

- Geri yükleme noktası başarısı yalnız cmdlet çağrısına veya sıfır çıkış koduna
  dayandırılmamalı; işlem öncesinden daha yüksek `SequenceNumber` ve plana özel
  tam açıklama eşleşmesi görülmelidir.
- Restore primitive'i serbest komut, başlık, hedef veya kullanıcı metni kabul
  etmemeli; yeni eylemler açık izin listesi ve politika incelemesi olmadan
  eklenmemelidir.
- Restore cmdlet'leri otomatik modül çözümlemesine bırakılmamalı;
  `$PSHOME\Modules` altındaki doğrulanmış `Microsoft.PowerShell.Management`
  manifestinden yüklenip tam modül adıyla çağrılmalıdır.
- Aynı anda tek restore görevi çalışmalı. UAC iptali, sorgu hatası, 24 saat
  sınırı veya zaman aşımı başarı sayılmamalıdır.
- Restore başarısızsa ana işlem varsayılan olarak durmalıdır. Korumasız devam
  ancak ikinci açık onay ve `recovery_override` denetim olayıyla mümkündür.
- Uygulama Sistem Korumasını, `SystemRestorePointCreationFrequency` değerini,
  kurum politikasını veya VBS ayarını sessizce değiştirmemelidir.
- Otomatik geri alma yalnız işlem öncesi ayar durumu okunmuş, ana görev yerelde
  `succeeded` olmuş ve mevcut durum değişmemişse sunulmalıdır. `delegated`,
  `failed`, `cancelled` veya `interrupted` sonuç geri alınabilir başarı değildir.
- Geri alma düğmesi ham komut taşımamalı; yalnız görev kimliği yayınlamalı ve
  merkezi allowlist yeni, değişmez bir çocuk plan üretmelidir.
- Çocuk geri alma planı başlatılmadan önce kayıtlı ana işlemden yeniden üretilen
  kanonik planla eylem, komut, yetki, başarı kodu ve etki alanlarında birebir
  eşleşmelidir. Genel görev ve sonuç API'leri `parent_plan_id` kabul etmemelidir.
- Geri alma ile korumalı RDP ve SMBv1 işlemleri `undo_execution.py` içindeki
  sabit izin listesinden üretilmeli; genel görev/sonuç API'leri bu eylem
  anahtarlarını kabul etmemeli ve genel komut dosyası yoluna düşülmemelidir.
- Bu akışlarda geçici `.cmd` dosyası veya serbest komut metni bulunmamalıdır.
  Windows PowerShell ile `reg.exe`, `sc.exe`, `net.exe`, `dism.exe`,
  `powercfg.exe`, `shutdown.exe` ve `netsh.exe` yalnız `GetSystemDirectoryW`
  sonucundan türetilen mutlak yollarla çalıştırılmalıdır.
- Toggle geri alma önkoşulu UAC sonrasında, yükseltilmiş çocuk süreçte ilk yan
  etkiden hemen önce yeniden okunmalıdır. Kayıt defteri değer türü ve beklenen
  tam durum eşleşmeli; SMB sorgusu sınırlı sürede bitmelidir. Sorgu hatası,
  zaman aşımı veya durum uyuşmazlığı hiçbir değişiklik başlatmadan durmalıdır.
- Aynı parent için ikinci geri alma, zincirleme geri alma ve durum kayması
  güvenli biçimde reddedilmelidir. Sonucu yakalanamayan geri alma `unknown`
  kalmalı, tamamlanmış gibi gösterilmemelidir.
- Daha önce görev geçmişinde veya `started`, `delegated`, `result` denetim
  olayında kullanılmış `plan_id` yeniden yürütülmemelidir. Geçmişte yinelenen
  kök `plan_id` görülürse ilgili geri almalar `unknown` durumuna alınmalıdır.
- Genel görev kabuğu ve süreç ağacı temizleyicisi de PATH yerine
  `GetSystemDirectoryW` ile doğrulanan mutlak `cmd.exe` ve `taskkill.exe`
  yollarını kullanmalı; yol çözülemezse görev yan etki üretmeden kapanmalıdır.
- `CrashExit`, sıfır çıkış koduyla gelse bile başarı değildir. Uygulama kapanışı
  yeni görevleri kapatmalı ve doğrulama sonrası bekleyen ana planları iptal
  olayıyla temizlemelidir.
- Sistem Geri Yükleme kişisel dosya veya ACL yedeği olarak anlatılmamalıdır.
  Sahiplik, boş alan temizleme ve zorla uygulama kapatma gibi işlemlerde sahte
  otomatik geri alma sunulmamalıdır.
- Klasör sahipliği Yöneticiler grubunu `/A` ve `*S-1-5-32-544` ile hedeflemeli;
  sürücü, UNC paylaşım ve Windows sistem kökleri toplu değişiklikten
  korunmalıdır.
- Güvenli Mod için kalıcı `bcdedit /set ... safeboot` zorlaması eklenmemeli;
  Windows Başlangıç Ayarları üzerinden tek açılışlık kullanıcı seçimi
  kullanılmalıdır.

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
- [ ] Yetkili ve riskli işlemlerin `plan_id` bağlantılı denetim olayları
      hassas veri içermeden kaydediliyor.
- [ ] Restore ve geri alma yalnız izinli eylemler, doğrulanmış sonuç ve güncel
      durumla çalışıyor; harici UAC devri başarı sayılmıyor.
- [ ] Açık GitHub uygulama geri bildirimleri kontrol edildi.
- [ ] Güncelleme varlık adı ve SHA-256 doğrulaması kontrol edildi.
- [ ] İlgili belge ve sürüm notları güncel.
- [ ] Çalışma alanındaki ilgisiz kullanıcı değişiklikleri korunuyor.
