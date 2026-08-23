from __future__ import annotations

from dataclasses import dataclass

from app_v2.services.command_builder import (
    aggregate_sequence,
    powershell_command,
)


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
    impact: str = ""
    interruption: str = ""
    rollback: str = ""
    restore_point_policy: str = "none"
    undo_key: str = ""


@dataclass(frozen=True)
class ToggleAction:
    key: str
    title: str
    description: str
    command_on: str
    command_off: str
    risk: str = "caution"
    risk_on: str = ""
    risk_off: str = ""
    impact_on: str = ""
    impact_off: str = ""
    interruption: str = ""
    rollback: str = ""
    restore_point_policy: str = "none"


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
        powershell_command(
            "Get-PhysicalDisk | Select-Object FriendlyName, MediaType, "
            "HealthStatus, OperationalStatus, Size | Format-Table -AutoSize"
        ),
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
        "",
        admin=True,
        risk="caution",
        handler="restore_point",
        impact=(
            "Windows sistem ayarları için yeni bir geri yükleme noktası "
            "oluşturulup sonuç doğrulanacak."
        ),
        interruption="Kısa süreli disk ve Sistem Koruması etkinliği oluşabilir.",
        rollback=(
            "Oluşturulan nokta Windows Sistem Geri Yükleme aracından seçilebilir. "
            "Bu işlem kişisel dosyaların yedeğini oluşturmaz."
        ),
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
        impact=(
            "Uzak Masaüstü bağlantıları kabul edilecek ve ilgili Windows "
            "Güvenlik Duvarı kuralları etkinleştirilecek."
        ),
        interruption="Ağ erişim yüzeyi değişir; yeniden başlatma beklenmez.",
        rollback=(
            "RDP bağlantılarını yeniden kapatıp ilgili güvenlik duvarı "
            "kurallarını devre dışı bırakın."
        ),
        restore_point_policy="optional",
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
        aggregate_sequence(
            (
                "ipconfig /release",
                "ipconfig /renew",
                "ipconfig /flushdns",
                "netsh winsock reset",
            )
        ),
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
        powershell_command(
            "$ip=(Get-NetIPAddress -AddressFamily IPv4 | "
            "Where-Object {$_.IPAddress -notlike '169.254*' -and "
            "$_.IPAddress -notlike '127.*'} | "
            "Select-Object -First 1 -ExpandProperty IPAddress);"
            "if(-not $ip){Write-Output 'Etkin IPv4 adresi bulunamadı';exit 1};"
            "$base=$ip.Substring(0,$ip.LastIndexOf('.'));"
            "$probes=@(1..254 | ForEach-Object {"
            "$target=$base+'.'+$_;"
            "try{"
            "$ping=New-Object System.Net.NetworkInformation.Ping;"
            "$task=$ping.SendPingAsync($target,750);"
            "[PSCustomObject]@{Target=$target;Ping=$ping;Task=$task}"
            "}catch{}"
            "});"
            "$tasks=@($probes | ForEach-Object {$_.Task});"
            "if($tasks.Count){"
            "[System.Threading.Tasks.Task]::WaitAll("
            "[System.Threading.Tasks.Task[]]$tasks)"
            "};"
            "$probes | ForEach-Object {"
            "try{"
            "if($_.Task.Result.Status -eq 'Success'){"
            "Write-Output ('AKTİF: '+$_.Target)"
            "}"
            "}finally{$_.Ping.Dispose()}"
            "}"
        ),
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
        impact=(
            "Tüm özel Windows Güvenlik Duvarı kuralları silinerek varsayılan "
            "kurallara dönülecek."
        ),
        interruption="Özel ağ erişimleri ve uygulama bağlantıları kesilebilir.",
        rollback=(
            "Önceden dışa aktarılmış bir güvenlik duvarı politikası yoksa "
            "özel kurallar otomatik geri getirilemez."
        ),
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
        risk_on="danger",
        risk_off="caution",
        impact_on=(
            "Güvenliği zayıf ve eski SMBv1 protokolü Windows özelliği olarak "
            "etkinleştirilecek."
        ),
        impact_off="Eski SMBv1 protokolü devre dışı bırakılacak.",
        interruption="Değişikliğin tamamlanması için yeniden başlatma gerekebilir.",
        rollback="Ayar ters yönde değiştirilerek önceki duruma döndürülebilir.",
        restore_point_policy="optional",
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
    ToolAction(
        "minidump",
        "Mavi ekran günlüklerini aç",
        "Windows Minidump klasörünü denetler ve varsa Dosya Gezgini'nde açar.",
        "Tanılama ve Kurtarma",
        powershell_command(
            "$path=Join-Path $env:WINDIR 'Minidump';"
            "if(Test-Path -LiteralPath $path){"
            "Start-Process explorer.exe -ArgumentList $path;"
            "Write-Output ('Klasör açıldı: '+$path)"
            "}else{"
            "Write-Output 'Henüz bir mavi ekran minidump kaydı bulunmuyor.'"
            "}"
        ),
        keep_open=False,
    ),
    ToolAction("windbg", "WinDbg aracını kur", "Microsoft'un resmi hata ayıklama aracını Winget ile kurar.", "Tanılama ve Kurtarma", "winget install --id Microsoft.WinDbg -e --accept-package-agreements --accept-source-agreements", admin=True),
    ToolAction("task_manager_unlock", "Görev Yöneticisi engelini kaldır", "DisableTaskMgr ilke değerini kaldırır.", "Tanılama ve Kurtarma", r'reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\System" /v DisableTaskMgr /f', admin=True, risk="caution"),
    ToolAction(
        "kill_hung",
        "Yanıt vermeyen uygulamaları kapat",
        "Yanıt vermiyor durumundaki uygulamaları zorla sonlandırır.",
        "Tanılama ve Kurtarma",
        r'taskkill /f /fi "status eq not responding"',
        admin=True,
        risk="danger",
        impact="Yanıt vermeyen bütün uygulamalar zorla sonlandırılacak.",
        interruption="Etkilenen uygulamalar hemen kapanır.",
        rollback="Kaydedilmemiş uygulama verileri geri getirilemez.",
    ),
    ToolAction(
        "shutdown_schedule",
        "Zamanlı kapatma ayarla",
        "Belirleyeceğiniz dakika sonunda bilgisayarı kapatır.",
        "Güç ve Güvenli Mod",
        "",
        handler="shutdown_schedule",
        risk="caution",
        rollback=(
            "Görev Merkezi'ndeki “Değişikliği geri al” düğmesi bekleyen "
            "Windows kapatma zamanlayıcısını iptal eder."
        ),
        undo_key="shutdown_cancel",
    ),
    ToolAction("shutdown_cancel", "Zamanlı kapatmayı iptal et", "Bekleyen Windows kapatma zamanlayıcısını iptal eder.", "Güç ve Güvenli Mod", "shutdown -a", keep_open=False),
    ToolAction(
        "safe_mode_on",
        "Gelişmiş başlangıç seçeneklerini aç",
        (
            "Windows'u kurtarma ortamında yeniden başlatır; Başlangıç "
            "Ayarları ekranından Güvenli Modu tek açılış için seçebilirsiniz."
        ),
        "Güç ve Güvenli Mod",
        "shutdown /r /o /t 0",
        admin=True,
        risk="danger",
        impact=(
            "Bilgisayar hemen Windows kurtarma ortamında yeniden başlatılacak. "
            "Güvenli Mod seçimi Başlangıç Ayarları ekranında size bırakılacak."
        ),
        interruption=(
            "Açık uygulamalar kapanır; kaydedilmemiş çalışmalar kaybolabilir."
        ),
        rollback=(
            "Kalıcı bir Güvenli Mod zorlaması eklenmez. Kurtarma ekranında "
            "Devam seçilerek normal Windows açılışına dönülebilir."
        ),
    ),
    ToolAction(
        "safe_mode_off",
        "Eski Güvenli Mod zorlamasını kaldır",
        "Geçerli Windows açılışındaki kalıcı safeboot değerini kaldırır.",
        "Güç ve Güvenli Mod",
        r"bcdedit /deletevalue {current} safeboot",
        admin=True,
        risk="caution",
    ),
)


DATA_ACTIONS = (
    ToolAction("profile_backup", "Kullanıcı profilini yedekle", "Masaüstü, Belgeler, İndirilenler ve Resimler klasörlerini seçtiğiniz hedefe kopyalar.", "Dosya ve Profil Transferi", "", handler="profile_backup"),
    ToolAction("credential_backup", "Windows kimlik bilgilerini yedekle", "Windows'un yerleşik Kimlik Bilgisi Yedekleme sihirbazını açar.", "Dosya ve Profil Transferi", "start credwiz.exe", keep_open=False),
    ToolAction(
        "take_ownership",
        "Klasör sahipliğini al",
        "Seçilen klasörün sahipliğini yerel yöneticiler grubuna verir.",
        "Dosya ve Profil Transferi",
        "",
        admin=True,
        risk="danger",
        handler="take_ownership",
        impact=(
            "Seçilen klasör ve alt öğelerinin sahibi değiştirilecek; yerel "
            "yöneticilere tam erişim verilecek."
        ),
        interruption="Mevcut dosya izinleri ve uygulama erişimleri etkilenebilir.",
        rollback=(
            "Önceki sahip ve ACL bilgileri kaydedilmediyse otomatik geri alma "
            "yoktur."
        ),
    ),
    ToolAction(
        "inventory",
        "PC envanter raporu oluştur",
        "Sistem bilgileri ve yüklü uygulama listesini Masaüstündeki metin raporuna yazar.",
        "Dosya ve Profil Transferi",
        aggregate_sequence(
            (
                r'systeminfo > "%USERPROFILE%\Desktop\PC_Rapor.txt"',
                r'winget list >> "%USERPROFILE%\Desktop\PC_Rapor.txt"',
                r'start "" notepad.exe "%USERPROFILE%\Desktop\PC_Rapor.txt"',
            )
        ),
        keep_open=False,
    ),
    ToolAction("aomei", "AOMEI Backupper Standard kur", "Resmi Winget paketinden disk yedekleme ve klonlama aracını kurar.", "Disk ve Yedekleme", "winget install --id AOMEI.Backupper.Standard -e --accept-package-agreements --accept-source-agreements", admin=True),
    ToolAction(
        "wipe_free_space",
        "Boş disk alanını güvenli temizle",
        "Seçilen sürücünün yalnızca boş alanını üzerine yazarak eski silinmiş verilerin kurtarılmasını zorlaştırır.",
        "Disk ve Yedekleme",
        "",
        admin=True,
        risk="danger",
        handler="wipe_free_space",
        impact=(
            "Seçilen sürücünün boş alanı üzerine yazılacak; daha önce silinmiş "
            "verilerin kurtarılması zorlaşacak."
        ),
        interruption="Uzun sürebilir ve yoğun disk kullanımı oluşturur.",
        rollback="Üzerine yazılan eski silinmiş veriler geri getirilemez.",
    ),
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
        "Seçili gereksiz Store uygulamalarını kaldır",
        "TikTok, Candy Crush ve McAfee Store paketlerini bulursa kaldırır; diğer uygulamalara dokunmaz.",
        "Sistem Temizliği",
        powershell_command(
            "$pattern='TikTok|CandyCrush|McAfee';"
            "$packages=Get-AppxPackage -AllUsers | "
            "Where-Object {$_.Name -match $pattern};"
            "if(-not $packages){"
            "Write-Output 'Hedeflenen Store uygulamalarından hiçbiri yüklü değil.';"
            "exit 0};"
            "$failed=$false;"
            "foreach($package in $packages){"
            "try{"
            "Remove-AppxPackage -Package $package.PackageFullName "
            "-AllUsers -ErrorAction Stop;"
            "Write-Output ('Kaldırıldı: '+$package.Name)"
            "}catch{"
            "$failed=$true;"
            "Write-Error ('Kaldırılamadı: '+$package.Name+' - '+$_.Exception.Message)"
            "}};"
            "if($failed){exit 1}"
        ),
        admin=True,
        risk="danger",
        impact=(
            "Bulunursa yalnızca TikTok, Candy Crush ve McAfee Store "
            "paketleri bütün kullanıcılardan kaldırılacak."
        ),
        interruption="Kaldırılan uygulamalar açık ise kapanabilir.",
        rollback="Gerekli uygulamalar Microsoft Store üzerinden yeniden kurulabilir.",
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
        powershell_command(
            "$roots=@($env:ProgramFiles,${env:ProgramFiles(x86)}) | "
            "Where-Object {$_};"
            "$path=Get-ChildItem $roots -Filter OSPP.VBS -Recurse "
            "-ErrorAction SilentlyContinue | Select-Object -First 1;"
            "if($path){"
            "cscript.exe //nologo $path.FullName /dstatus;"
            "exit $LASTEXITCODE"
            "}else{"
            "Write-Output 'OSPP.VBS bulunamadı';"
            "exit 1"
            "}"
        ),
    ),
)


MAIL_ACTIONS = (
    ToolAction("mail_control", "Outlook profil yönetimini aç", "Klasik Outlook posta profillerini düzenleyen Denetim Masası bileşenini açar.", "Sorun Giderme", "start control mlcfg32.cpl", keep_open=False),
    ToolAction("outlook_safe", "Outlook'u Güvenli Modda başlat", "Outlook'u eklentiler kapalı olarak açar.", "Sorun Giderme", "start outlook.exe /safe", keep_open=False),
    ToolAction("outlook_cache", "Otomatik tamamlama önbelleğini temizle", "Outlook'un alıcı önerileri önbelleğini temizleyerek uygulamayı başlatır.", "Sorun Giderme", "start outlook.exe /cleanautocompletecache", keep_open=False, risk="caution"),
    ToolAction("pst_backup", "PST ve OST dosyalarını yedekle", "Klasik Outlook veri dosyalarını seçtiğiniz hedef klasöre kopyalar.", "Yedekleme ve Arşivleme", "", handler="pst_backup"),
    ToolAction(
        "mailstore",
        "MailStore Home indirme sayfası",
        "Ücretsiz ev sürümünün resmi indirme sayfasını tarayıcıda açar.",
        "Yedekleme ve Arşivleme",
        'start "" "https://www.mailstore.com/en/products/mailstore-home/"',
        keep_open=False,
    ),
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
    PackageItem("AnyDesk", "AnyDesk.AnyDesk", True),
    PackageItem("TeamViewer", "TeamViewer.TeamViewer"),
    PackageItem("RustDesk resmi indirme sayfası", "https://rustdesk.com/", source="url"),
    PackageItem("Notepad++", "Notepad++.Notepad++", True),
    PackageItem("WinDirStat", "WinDirStat.WinDirStat", True),
    PackageItem("Everything", "voidtools.Everything"),
    PackageItem("TeraCopy", "CodeSector.TeraCopy"),
    PackageItem("PuTTY", "PuTTY.PuTTY"),
    PackageItem(
        "FileZilla resmi indirme sayfası",
        "https://filezilla-project.org/download.php?type=client",
        source="url",
    ),
    PackageItem("Zoom", "Zoom.Zoom"),
    PackageItem("Microsoft Teams", "Microsoft.Teams"),
    PackageItem("Mozilla Thunderbird", "Mozilla.Thunderbird"),
    PackageItem("Google Drive", "Google.GoogleDrive"),
    PackageItem("Dropbox", "Dropbox.Dropbox"),
    PackageItem("Steam", "Valve.Steam"),
)


DRIVER_PACKAGES = (
    PackageItem("NVIDIA App", "XP8CLZL93F5Z4P"),
    PackageItem("HP Smart", "9WZDNCRFHWLH"),
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

TOGGLE_LOOKUP = {
    toggle.key: toggle
    for toggle in SYSTEM_TOGGLES + NETWORK_TOGGLES + DATA_TOGGLES
}


def find_action(action_key: str) -> tuple[str, ToolAction] | None:
    return ACTION_LOOKUP.get(action_key)
