from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolAction:
    key: str
    title: str
    description: str
    category: str
    command: str
    admin: bool = False
    keep_open: bool = True
    risk: str = "normal"
    handler: str | None = None


@dataclass(frozen=True)
class ToggleAction:
    key: str
    title: str
    description: str
    command_on: str
    command_off: str
    risk: str = "caution"


@dataclass(frozen=True)
class PackageItem:
    name: str
    package_id: str
    default: bool = False
    source: str = "winget"


SYSTEM_ACTIONS = (
    ToolAction(
        "clean_temp",
        "Geçici dosyaları temizle",
        "Kullanıcı ve Windows geçici klasörlerindeki gereksiz dosyaları temizler.",
        "Temizlik ve Onarım",
        r'del /q /f /s "%TEMP%\*" & del /q /f /s "C:\Windows\Temp\*"',
        admin=True,
        risk="caution",
    ),
    ToolAction(
        "sfc",
        "Windows sistem dosyalarını onar",
        "Bozuk veya eksik sistem dosyalarını SFC ile tarar ve onarmaya çalışır.",
        "Temizlik ve Onarım",
        "sfc /scannow",
        admin=True,
    ),
    ToolAction(
        "spooler",
        "Yazıcı kuyruğunu sıfırla",
        "Sıkışan yazdırma görevlerini siler ve yazdırma hizmetini yeniden başlatır.",
        "Temizlik ve Onarım",
        r'net stop spooler & del /Q /F /S "%systemroot%\System32\Spool\Printers\*.*" & net start spooler',
        admin=True,
        risk="caution",
    ),
    ToolAction(
        "taskbar",
        "Görev çubuğunu onar",
        "Windows uygulama paketlerini yeniden kaydeder ve Explorer sürecini yeniler.",
        "Temizlik ve Onarım",
        r'powershell.exe -NoProfile -Command "Get-AppXPackage -AllUsers | ForEach-Object {Add-AppxPackage -DisableDevelopmentMode -Register \"$($_.InstallLocation)\AppXManifest.xml\"}" & taskkill /f /im explorer.exe & start explorer.exe',
        admin=True,
        risk="caution",
    ),
    ToolAction(
        "store",
        "Microsoft Store önbelleğini sıfırla",
        "Açılmayan veya indirme yapmayan Microsoft Store önbelleğini temizler.",
        "Temizlik ve Onarım",
        "wsreset.exe",
        keep_open=False,
    ),
    ToolAction(
        "icons",
        "Simge önbelleğini yenile",
        "Boş veya hatalı görünen Windows simgelerinin önbelleğini yeniden oluşturur.",
        "Temizlik ve Onarım",
        r'taskkill /f /im explorer.exe & del /q /a /f "%localappdata%\IconCache.db" & start explorer.exe',
        risk="caution",
    ),
    ToolAction(
        "smart",
        "Disk sağlık durumunu görüntüle",
        "Fiziksel disklerin model ve sağlık durumlarını PowerShell üzerinden listeler.",
        "Analiz ve Gelişmiş İşlemler",
        r'powershell -NoProfile -Command "Get-PhysicalDisk | Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus, Size | Format-Table -AutoSize"',
    ),
    ToolAction(
        "battery",
        "Pil yıpranma raporu oluştur",
        "Masaüstüne ayrıntılı Windows pil raporu oluşturur ve tarayıcıda açar.",
        "Analiz ve Gelişmiş İşlemler",
        r'powercfg /batteryreport /output "%USERPROFILE%\Desktop\Pil_Raporu.html" & start "" "%USERPROFILE%\Desktop\Pil_Raporu.html"',
        keep_open=False,
    ),
    ToolAction(
        "restore",
        "Geri yükleme noktası oluştur",
        "Sistem ayarlarında değişiklik yapmadan önce geri dönüş noktası oluşturur.",
        "Analiz ve Gelişmiş İşlemler",
        r'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Checkpoint-Computer -Description \"IT_Toolkit_Yedek\" -RestorePointType \"MODIFY_SETTINGS\""',
        admin=True,
        risk="caution",
    ),
    ToolAction(
        "gpupdate",
        "Grup ilkelerini güncelle",
        "Etki alanından gelen Windows ilkelerini yeniden indirip uygular.",
        "Analiz ve Gelişmiş İşlemler",
        "gpupdate /force",
        admin=True,
    ),
    ToolAction(
        "rdp",
        "Uzak Masaüstünü etkinleştir",
        "RDP bağlantılarını ve gerekli Windows Güvenlik Duvarı kuralını etkinleştirir.",
        "Analiz ve Gelişmiş İşlemler",
        r'reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f & netsh advfirewall firewall set rule group="@FirewallAPI.dll,-28752" new enable=Yes',
        admin=True,
        risk="danger",
    ),
)


SYSTEM_TOGGLES = (
    ToggleAction(
        "windows_update",
        "Windows Update",
        "Windows güncelleme hizmetinin çalışma biçimini yönetir.",
        r'sc config wuauserv start= demand & net start wuauserv & reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoUpdate /f',
        r'net stop wuauserv & sc config wuauserv start= disabled & reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoUpdate /t REG_DWORD /d 1 /f',
    ),
    ToggleAction(
        "hibernation",
        "Hazırda bekletme",
        "Hızlı başlatmada da kullanılan hiberfil.sys dosyasını etkinleştirir veya kaldırır.",
        "powercfg -h on",
        "powercfg -h off",
    ),
)


NETWORK_ACTIONS = (
    ToolAction(
        "network_reset",
        "İnternet bağlantısını sıfırla",
        "IP kiralamasını, DNS önbelleğini ve Winsock kataloğunu yeniler.",
        "Temel Ağ İşlemleri",
        "ipconfig /release & ipconfig /renew & ipconfig /flushdns & netsh winsock reset",
        admin=True,
        risk="caution",
    ),
    ToolAction(
        "ip_mac",
        "IP ve MAC adreslerini göster",
        "Etkin ağ bağdaştırıcılarının ayrıntılı IP ve fiziksel adres bilgilerini listeler.",
        "Temel Ağ İşlemleri",
        "ipconfig /all",
    ),
    ToolAction(
        "netstat",
        "Dinlenen portları görüntüle",
        "Cihazda bağlantı bekleyen TCP ve UDP portlarını işlem kimlikleriyle listeler.",
        "Temel Ağ İşlemleri",
        "netstat -ano | findstr LISTENING",
        admin=True,
    ),
    ToolAction(
        "ping",
        "Sürekli ping testi başlat",
        "Google DNS adresine sürekli paket göndererek gecikme ve paket kaybını gösterir.",
        "Temel Ağ İşlemleri",
        "ping 8.8.8.8 -t",
    ),
    ToolAction(
        "ip_scan",
        "Yerel ağı tara",
        "Mevcut IPv4 alt ağındaki yanıt veren cihazları tarar ve listeler.",
        "Temel Ağ İşlemleri",
        r"""powershell -NoProfile -Command "$ip=(Get-NetIPAddress -AddressFamily IPv4|Where-Object {$_.IPAddress -notlike '169.254*' -and $_.IPAddress -notlike '127.*'}|Select-Object -First 1 -ExpandProperty IPAddress);if(-not $ip){Write-Host 'Etkin IPv4 adresi bulunamadı';exit 1};$base=$ip.Substring(0,$ip.LastIndexOf('.'));1..254|ForEach-Object{$target=$base+'.'+$_;if(Test-Connection $target -Count 1 -Quiet -TimeoutSeconds 1){Write-Host ('AKTİF: '+$target) -ForegroundColor Green}}""",
    ),
    ToolAction(
        "wifi_profiles",
        "Kayıtlı Wi-Fi profillerini listele",
        "Bilgisayarın daha önce bağlandığı kablosuz ağ adlarını listeler; parolaları göstermez.",
        "Kablosuz Ağ ve Paylaşım",
        "netsh wlan show profiles",
    ),
    ToolAction(
        "wifi_qr",
        "Wi-Fi QR kodu oluştur",
        "Girdiğiniz ağ adı ve paroladan, veriyi internete göndermeden yerel QR kod üretir.",
        "Kablosuz Ağ ve Paylaşım",
        "",
        handler="wifi_qr",
    ),
    ToolAction(
        "hosts",
        "Hosts dosyasını düzenle",
        "Windows Hosts dosyasını Not Defteri ile yönetici yetkisinde açar.",
        "Kablosuz Ağ ve Paylaşım",
        r'notepad.exe C:\Windows\System32\drivers\etc\hosts',
        admin=True,
        keep_open=False,
        risk="caution",
    ),
    ToolAction(
        "smb_sessions",
        "Ağ paylaşımı oturumlarını temizle",
        "Açık SMB bağlantılarını kapatarak sonraki erişimde yeniden kimlik doğrulama sağlar.",
        "Kablosuz Ağ ve Paylaşım",
        "net use * /delete /y",
        risk="caution",
    ),
    ToolAction(
        "firewall_reset",
        "Güvenlik Duvarını sıfırla",
        "Tüm özel Windows Güvenlik Duvarı kurallarını varsayılan ayarlara döndürür.",
        "Kablosuz Ağ ve Paylaşım",
        "netsh advfirewall reset",
        admin=True,
        risk="danger",
    ),
)


NETWORK_TOGGLES = (
    ToggleAction(
        "smb1",
        "SMBv1 eski ağ protokolü",
        "Yalnızca eski NAS ve yazıcılar zorunlu kılıyorsa açın; güvenlik riski taşır.",
        r'powershell.exe -NoProfile -Command "Enable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -All -NoRestart"',
        r'powershell.exe -NoProfile -Command "Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart"',
        risk="danger",
    ),
)


QUICK_ACTIONS = (
    ToolAction("device_manager", "Aygıt Yöneticisi", "Donanım ve sürücüleri yönetir.", "Windows Yönetim Konsolları", "start devmgmt.msc", keep_open=False),
    ToolAction("registry_editor", "Kayıt Defteri Düzenleyicisi", "Windows kayıt defterini yönetici yetkisiyle açar.", "Windows Yönetim Konsolları", "regedit.exe", admin=True, keep_open=False, risk="caution"),
    ToolAction("services", "Hizmetler", "Windows arka plan hizmetlerini yönetir.", "Windows Yönetim Konsolları", "start services.msc", keep_open=False),
    ToolAction("event_viewer", "Olay Görüntüleyici", "Sistem ve uygulama günlüklerini açar.", "Windows Yönetim Konsolları", "start eventvwr.msc", keep_open=False),
    ToolAction("computer_management", "Bilgisayar Yönetimi", "Disk, kullanıcı ve görev yönetimi konsolunu açar.", "Windows Yönetim Konsolları", "compmgmt.msc", admin=True, keep_open=False),
    ToolAction("programs_features", "Programlar ve Özellikler", "Klasik program kaldırma menüsünü açar.", "Windows Yönetim Konsolları", "start appwiz.cpl", keep_open=False),
    ToolAction("control_panel", "Denetim Masası", "Klasik Windows Denetim Masasını açar.", "Windows Yönetim Konsolları", "start control", keep_open=False),
    ToolAction("uac_settings", "UAC bildirim ayarlarını aç", "Yönetici izni bildirim düzeyini Windows arayüzünden değiştirmenizi sağlar.", "Windows Yönetim Konsolları", "UserAccountControlSettings.exe", keep_open=False),
    ToolAction("minidump", "Mavi ekran günlüklerini aç", "Windows Minidump klasörünü Dosya Gezgini'nde açar.", "Tanılama ve Kurtarma", r'start "" explorer.exe C:\Windows\Minidump', keep_open=False),
    ToolAction("windbg", "WinDbg aracını kur", "Microsoft'un resmi hata ayıklama aracını Winget ile kurar.", "Tanılama ve Kurtarma", "winget install --id Microsoft.WinDbg -e --accept-package-agreements --accept-source-agreements", admin=True),
    ToolAction("task_manager_unlock", "Görev Yöneticisi engelini kaldır", "DisableTaskMgr ilke değerini kaldırır.", "Tanılama ve Kurtarma", r'reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\System" /v DisableTaskMgr /f', admin=True, risk="caution"),
    ToolAction("kill_hung", "Yanıt vermeyen uygulamaları kapat", "Yanıt vermiyor durumundaki uygulamaları zorla sonlandırır.", "Tanılama ve Kurtarma", r'taskkill /f /fi "status eq not responding"', admin=True, risk="danger"),
    ToolAction("shutdown_schedule", "Zamanlı kapatma ayarla", "Belirleyeceğiniz dakika sonunda bilgisayarı kapatır.", "Güç ve Güvenli Mod", "", handler="shutdown_schedule", risk="caution"),
    ToolAction("shutdown_cancel", "Zamanlı kapatmayı iptal et", "Bekleyen Windows kapatma zamanlayıcısını iptal eder.", "Güç ve Güvenli Mod", "shutdown -a", keep_open=False),
    ToolAction("safe_mode_on", "Sonraki açılışı Güvenli Mod yap", "Windows'un sonraki açılışını ağ destekli Güvenli Mod olarak ayarlar.", "Güç ve Güvenli Mod", r"bcdedit /set {default} safeboot network", admin=True, risk="danger"),
    ToolAction("safe_mode_off", "Güvenli Mod zorlamasını kaldır", "Zorunlu Güvenli Mod açılış ayarını kaldırır.", "Güç ve Güvenli Mod", r"bcdedit /deletevalue {default} safeboot", admin=True, risk="caution"),
)


DATA_ACTIONS = (
    ToolAction("profile_backup", "Kullanıcı profilini yedekle", "Masaüstü, Belgeler, İndirilenler ve Resimler klasörlerini seçtiğiniz hedefe kopyalar.", "Dosya ve Profil Transferi", "", handler="profile_backup"),
    ToolAction("credential_backup", "Windows kimlik bilgilerini yedekle", "Windows'un yerleşik Kimlik Bilgisi Yedekleme sihirbazını açar.", "Dosya ve Profil Transferi", "start credwiz.exe", keep_open=False),
    ToolAction("take_ownership", "Klasör sahipliğini al", "Seçilen klasörün sahipliğini yerel yöneticiler grubuna verir.", "Dosya ve Profil Transferi", "", admin=True, risk="danger", handler="take_ownership"),
    ToolAction("inventory", "PC envanter raporu oluştur", "Sistem bilgileri ve yüklü uygulama listesini Masaüstündeki metin raporuna yazar.", "Dosya ve Profil Transferi", r'systeminfo > "%USERPROFILE%\Desktop\PC_Rapor.txt" & winget list >> "%USERPROFILE%\Desktop\PC_Rapor.txt" & start "" notepad.exe "%USERPROFILE%\Desktop\PC_Rapor.txt"', keep_open=False),
    ToolAction("aomei", "AOMEI Backupper Standard kur", "Resmi Winget paketinden disk yedekleme ve klonlama aracını kurar.", "Disk ve Yedekleme", "winget install --id AOMEI.Backupper.Standard -e --accept-package-agreements --accept-source-agreements", admin=True),
    ToolAction("wipe_free_space", "Boş disk alanını güvenli temizle", "Seçilen sürücünün yalnızca boş alanını üzerine yazarak eski silinmiş verilerin kurtarılmasını zorlaştırır.", "Disk ve Yedekleme", "", admin=True, risk="danger", handler="wipe_free_space"),
)


DATA_TOGGLES = (
    ToggleAction(
        "usb_write_protect",
        "USB bellek yazma koruması",
        "USB depolama aygıtlarına yazmayı engeller veya yeniden etkinleştirir.",
        r'reg add "HKLM\System\CurrentControlSet\Control\StorageDevicePolicies" /v WriteProtect /t REG_DWORD /d 1 /f',
        r'reg delete "HKLM\System\CurrentControlSet\Control\StorageDevicePolicies" /v WriteProtect /f',
    ),
)


PROGRAM_ACTIONS = (
    ToolAction("basic_installer", "Temel uygulama paketini seç", "Tarayıcı, arşiv, medya ve IT araçlarını toplu Winget kurulumu için seçmenizi sağlar.", "Otomatik Kurulum", "", handler="basic_installer"),
    ToolAction("driver_installer", "Sürücü ve üretici araçlarını seç", "Resmi sürücü uygulamalarını ve üretici destek sayfalarını listeler.", "Otomatik Kurulum", "", handler="driver_installer"),
    ToolAction(
        "debloat",
        "Seçili gereksiz uygulamaları kaldır",
        "McAfee, TikTok ve Candy Crush paketlerini varsa Winget üzerinden kaldırır.",
        "Sistem Temizliği",
        "winget uninstall -e --id McAfee.McAfeeSecurity --silent & winget uninstall -e --id ByteDance.TikTok --silent & winget uninstall -e --id King.CandyCrushSaga --silent",
        admin=True,
        risk="danger",
    ),
    ToolAction("winget_update", "Winget kaynaklarını güncelle", "Paket yöneticisinin uygulama kaynaklarını yeniler.", "Sistem Temizliği", "winget source update", admin=True),
)


OFFICE_ACTIONS = (
    ToolAction("office_installer", "Office sürümünü seç", "Resmi Microsoft indirme bağlantılarından lisansınıza uygun Office sürümünü seçmenizi sağlar.", "Kurulum ve Onarım", "", handler="office_installer"),
    ToolAction("office_repair", "Office onarım ve kaldırma menüsü", "Programlar ve Özellikler üzerinden Office değiştirme veya kaldırma ekranını açar.", "Kurulum ve Onarım", "start appwiz.cpl", keep_open=False),
    ToolAction("office_account", "Microsoft hizmetleri sayfasını aç", "Microsoft hesabınızdaki lisans ve abonelikleri resmi web sayfasında açar.", "Kurulum ve Onarım", 'start "" "https://account.microsoft.com/services"', keep_open=False),
    ToolAction("word_safe", "Word'ü Güvenli Modda başlat", "Word'ü eklentiler devre dışı olarak açar.", "Tanılama", "start winword.exe /safe", keep_open=False),
    ToolAction("excel_safe", "Excel'i Güvenli Modda başlat", "Excel'i eklentiler devre dışı olarak açar.", "Tanılama", "start excel.exe /safe", keep_open=False),
    ToolAction(
        "office_license",
        "Office lisans durumunu görüntüle",
        "Yüklü Office sürümünün OSPP lisans ayrıntılarını yerel olarak gösterir.",
        "Tanılama",
        r"""powershell -NoProfile -Command "$roots=@($env:ProgramFiles,${env:ProgramFiles(x86)})|Where-Object {$_};$p=Get-ChildItem $roots -Filter OSPP.VBS -Recurse -ErrorAction SilentlyContinue|Select-Object -First 1;if($p){cscript.exe //nologo $p.FullName /dstatus}else{Write-Host 'OSPP.VBS bulunamadı';exit 1}""",
    ),
)


MAIL_ACTIONS = (
    ToolAction("mail_control", "Outlook profil yönetimini aç", "Klasik Outlook posta profillerini düzenleyen Denetim Masası bileşenini açar.", "Sorun Giderme", "start control mlcfg32.cpl", keep_open=False),
    ToolAction("outlook_safe", "Outlook'u Güvenli Modda başlat", "Outlook'u eklentiler kapalı olarak açar.", "Sorun Giderme", "start outlook.exe /safe", keep_open=False),
    ToolAction("outlook_cache", "Otomatik tamamlama önbelleğini temizle", "Outlook'un alıcı önerileri önbelleğini temizleyerek uygulamayı başlatır.", "Sorun Giderme", "start outlook.exe /cleanautocompletecache", keep_open=False, risk="caution"),
    ToolAction("pst_backup", "PST ve OST dosyalarını yedekle", "Klasik Outlook veri dosyalarını seçtiğiniz hedef klasöre kopyalar.", "Yedekleme ve Arşivleme", "", handler="pst_backup"),
    ToolAction("mailstore", "MailStore Home kur", "Ücretsiz e-posta arşivleme aracını resmi Winget paketinden kurar.", "Yedekleme ve Arşivleme", "winget install -e --id MailStore.MailStoreHome --accept-package-agreements --accept-source-agreements", admin=True),
    ToolAction("outlook_support", "Microsoft Outlook desteğini aç", "Resmi Microsoft Outlook yardım ve sorun giderme sayfasını açar.", "Yedekleme ve Arşivleme", 'start "" "https://support.microsoft.com/outlook"', keep_open=False),
)


ISO_ACTIONS = (
    ToolAction("windows_10", "Windows 10 indirme sayfası", "Microsoft'un resmi Windows 10 indirme ve medya oluşturma sayfasını açar.", "Windows Kurulum Medyası", 'start "" "https://www.microsoft.com/tr-tr/software-download/windows10"', keep_open=False),
    ToolAction("windows_11", "Windows 11 indirme sayfası", "Microsoft'un resmi Windows 11 ISO ve medya oluşturma sayfasını açar.", "Windows Kurulum Medyası", 'start "" "https://www.microsoft.com/tr-tr/software-download/windows11"', keep_open=False),
    ToolAction("fido", "Fido ISO aracının resmi sayfası", "Rufus geliştiricisinin açık kaynaklı Fido projesini GitHub üzerinde açar.", "Windows Kurulum Medyası", 'start "" "https://github.com/pbatard/Fido"', keep_open=False),
    ToolAction("rufus", "Rufus kur", "Önyüklenebilir USB hazırlama aracını resmi Winget paketinden kurar.", "USB Hazırlama Araçları", "winget install -e --id Rufus.Rufus --accept-package-agreements --accept-source-agreements", admin=True),
    ToolAction("ventoy", "Ventoy kur", "Bir USB üzerinde birden çok ISO kullanmayı sağlayan Ventoy'u Winget üzerinden kurar.", "USB Hazırlama Araçları", "winget install -e --id Ventoy.Ventoy --accept-package-agreements --accept-source-agreements", admin=True),
)


BASIC_PACKAGES = (
    PackageItem("Google Chrome", "Google.Chrome", True),
    PackageItem("Mozilla Firefox", "Mozilla.Firefox"),
    PackageItem("Opera Browser", "Opera.Opera"),
    PackageItem("7-Zip", "7zip.7zip", True),
    PackageItem("WinRAR", "RARLab.WinRAR"),
    PackageItem("VLC Media Player", "VideoLAN.VLC", True),
    PackageItem("Adobe Acrobat Reader", "Adobe.Acrobat.Reader.64-bit", True),
    PackageItem("AnyDesk", "AnyDeskSoftwareGmbH.AnyDesk", True),
    PackageItem("TeamViewer", "TeamViewer.TeamViewer"),
    PackageItem("RustDesk", "RustDesk.RustDesk"),
    PackageItem("Notepad++", "Notepad++.Notepad++", True),
    PackageItem("WinDirStat", "WinDirStat.WinDirStat", True),
    PackageItem("Everything", "voidtools.Everything"),
    PackageItem("TeraCopy", "CodeSector.TeraCopy"),
    PackageItem("PuTTY", "PuTTY.PuTTY"),
    PackageItem("FileZilla", "TimKosse.FileZillaClient"),
    PackageItem("Zoom", "Zoom.Zoom"),
    PackageItem("Microsoft Teams", "Microsoft.Teams"),
    PackageItem("Mozilla Thunderbird", "Mozilla.Thunderbird"),
    PackageItem("Google Drive", "Google.Drive"),
    PackageItem("Dropbox", "Dropbox.Dropbox"),
    PackageItem("Steam", "Valve.Steam"),
)


DRIVER_PACKAGES = (
    PackageItem("NVIDIA App", "Nvidia.NVIDIAapp"),
    PackageItem("HP Smart", "9WZDNCRFHWL0"),
    PackageItem("Canon destek sayfası", "https://www.canon-europe.com/support/", source="url"),
    PackageItem("HP sürücü destek sayfası", "https://support.hp.com/drivers", source="url"),
    PackageItem("Epson destek sayfası", "https://www.epson.eu/support", source="url"),
)


OFFICE_PACKAGES = (
    PackageItem(
        "Microsoft 365 İş",
        "https://c2rsetup.officeapps.live.com/c2r/download.aspx?ProductreleaseID=O365BusinessRetail&platform=x64&language=tr-tr&version=O16GA",
        source="url",
    ),
    PackageItem(
        "Office Ev ve İş 2024",
        "https://c2rsetup.officeapps.live.com/c2r/download.aspx?ProductreleaseID=HomeBusiness2024Retail&platform=x64&language=tr-tr&version=O16GA",
        source="url",
    ),
    PackageItem(
        "Office Ev ve İş 2021",
        "https://c2rsetup.officeapps.live.com/c2r/download.aspx?ProductreleaseID=HomeBusiness2021Retail&platform=x64&language=tr-tr&version=O16GA",
        source="url",
    ),
    PackageItem(
        "Office Ev ve İş 2019",
        "https://c2rsetup.officeapps.live.com/c2r/download.aspx?ProductreleaseID=HomeBusiness2019Retail&platform=x64&language=tr-tr&version=O16GA",
        source="url",
    ),
    PackageItem(
        "Office Ev ve İş 2016",
        "https://c2rsetup.officeapps.live.com/c2r/download.aspx?ProductreleaseID=HomeBusinessRetail&platform=x64&language=tr-tr&version=O16GA",
        source="url",
    ),
)


PAGE_ACTIONS = {
    "system": SYSTEM_ACTIONS,
    "network": NETWORK_ACTIONS,
    "quick": QUICK_ACTIONS,
    "data": DATA_ACTIONS,
    "programs": PROGRAM_ACTIONS,
    "office": OFFICE_ACTIONS,
    "mail": MAIL_ACTIONS,
    "iso": ISO_ACTIONS,
}

ACTION_LOOKUP = {
    action.key: (page_key, action)
    for page_key, actions in PAGE_ACTIONS.items()
    for action in actions
}


def find_action(action_key: str) -> tuple[str, ToolAction] | None:
    return ACTION_LOOKUP.get(action_key)
