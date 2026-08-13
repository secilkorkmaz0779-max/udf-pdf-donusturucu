# UDF → PDF Dönüştürücü

UYAP'tan (e-satış / icra dosyaları) indirilen **.udf** dosyalarını, tarayıcıdan tek
tıkla düzgün biçimlendirilmiş bir **PDF**'e çeviren, ücretsiz ve gayriresmî bir web
aracı.

UDF dosyaları bazı bilgisayarlarda Java hatası verip açılmıyor, telefonda ise
genellikle hiç desteklenmiyor. Bu araç, dosyanın içindeki gerçek metni ve
fotoğrafları (varsa) doğrudan okuyup UYAP'ın kendi görünümüne yakın, hizalama ve
kalın başlıkları koruyan bir PDF üretir — hiçbir ek program kurmaya gerek kalmadan.

**Canlı demo:** https://udf-pdf-donusturucu.onrender.com 

## Özellikler

- UDF içindeki metni, hizalamayı (ortalı/sağa yaslı/iki yana yaslı), kalın
  başlıkları ve madde işaretli listeleri koruyarak PDF'e aktarır
- Belgeye gömülü fotoğrafları (varsa) otomatik tespit edip PDF'e ekler
- Her sayfada tekrarlanan üst başlığı ve sayfa numarasını üretir
- Türkçe karakterleri (ı, ğ, ş, İ, ö, ü) doğru şekilde işler
- Yüklenen dosyalar sunucuda **hiçbir şekilde saklanmaz**; bellekte işlenip
  yanıt döndükten hemen sonra silinir

## Yerelde çalıştırma

```bash
git clone <bu-repo-linki>
cd <klasör-adı>
pip install -r requirements.txt
python app.py
```

Tarayıcıda `http://127.0.0.1:5000` adresini aç.

## Kullanılan teknolojiler

- [Flask](https://flask.palletsprojects.com/) — web sunucusu
- [ReportLab](https://www.reportlab.com/) — PDF üretimi
- [defusedxml](https://github.com/tiran/defusedxml) — güvenli XML ayrıştırma

## Yasal not

Bu proje, Adalet Bakanlığı veya UYAP ile **resmî bir bağı olmayan**, bağımsız bir
dönüştürme aracıdır. Üretilen PDF'ler yalnızca bilgi amaçlıdır; her zaman UYAP
üzerindeki orijinal belgeyi esas alın.

---

by SEÇİL KORKMAZ
