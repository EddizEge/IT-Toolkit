# Katkıda Bulunma Rehberi

IT Toolkit’e katkıda bulunduğunuz için teşekkürler. Projenin temel öncelikleri
güvenlik, anlaşılır Türkçe, akıcı arayüz ve Windows 10/11 uyumluluğudur.

## Başlamadan önce

1. Mevcut issue’ları kontrol edin.
2. Büyük özellikler için önce bir öneri issue’su açın.
3. Değişikliğin yalnızca resmi ve güvenilir kaynaklar kullandığından emin olun.
4. Sistem ayarını değiştiren işlemlerde etkiyi ve geri alma yolunu belgeleyin.

## Geliştirme ortamı

```powershell
git clone https://github.com/EddizEge/IT-Toolkit.git
cd IT-Toolkit
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main_v2.py
```

Geliştirme ve doğrulama araçları için:

```powershell
python -m pip install -r requirements-dev.txt
ruff check app_v2 tests main_v2.py
python -m unittest discover -s tests -v
```

## Kod ilkeleri

- Kullanıcıya görünen tüm metinler Türkçe olmalıdır.
- Yaklaşık 100 ms’den uzun işlemler arayüz iş parçacığında çalışmamalıdır.
- Yeni araçlar merkezi kayıt yapısına eklenmeli ve anlaşılır açıklama içermelidir.
- GPU sorguları fiziksel PCI aygıtlarını, ağ sorguları fiziksel bağdaştırıcıları
  filtrelemeye devam etmelidir.
- Parola çözme, lisans atlatma, korsan yazılım veya güvenilir olmayan indirme
  kaynakları kabul edilmez.
- Kritik işlemler açık uyarı ve uygun olduğu yerde onay istemelidir.

## Pull request kontrolü

- [ ] Uygulama `python main_v2.py` ile açılıyor.
- [ ] Değiştirilen ekran farklı pencere boyutlarında kontrol edildi.
- [ ] Uzun işlemler arayüzü kilitlemiyor.
- [ ] Yeni kullanıcı metinleri Türkçe ve anlaşılır.
- [ ] Resmi kaynak bağlantıları doğrulandı.
- [ ] `CHANGELOG.md` gerekiyorsa güncellendi.
- [ ] Ekran görüntüsü veya test notu eklendi.

## Commit mesajları

Kısa ve eylem odaklı mesajlar kullanın:

- `Görev merkezi temelini ekle`
- `Disk kartı taşmasını düzelt`
- `Office bağlantılarını güncelle`
