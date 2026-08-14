# StuHub — Kullanım Kılavuzu

StuHub, üniversite dersleriniz için **tamamen yerel** çalışan bir ders notu ve quiz uygulamasıdır.
Ders kitaplarınızı (PDF) ve hoca sunumlarınızı yükler; yapay zeka ile **atıflı notlar**, **bölüm quizleri** ve **ders geneli quizler** üretir. Tüm veriniz bilgisayarınızda kalır (`data/` klasörü).

---

## 1. Kurulum (tek seferlik)

Gereksinimler: **Python 3.12 + uv**, **Node ≥ 20 + npm**, **git**, ve bir **DeepSeek API anahtarı**.

```bash
# 1) Bağımlılıklar
cd apps/backend && uv sync
cd ../frontend && npm install

# 2) API anahtarı
# .env.example dosyasını .env olarak kopyalayıp DEEPSEEK_API_KEY değerini doldurun
# (veya uygulama içi Ayarlar sayfasından girin)
```

> 💡 **İsteğe bağlı:** Sunum slide'larının pop-up'ta tam PDF sayfası olarak görünmesi için
> [LibreOffice](https://www.libreoffice.org/download/) kurabilirsiniz. Kurulmazsa pop-up'lar
> metin alıntısı gösterir (uygulama sorunsuz çalışır).

## 2. Başlatma

İki terminal:

```bash
# Terminal 1 — backend (8000)
cd apps/backend
uv run uvicorn src.main:app --port 8000

# Terminal 2 — frontend (5173, geliştirme modu)
cd apps/frontend
npm run dev
```

Tarayıcıda **http://localhost:5173** açılır. Backend kapalıysa üstte uyarı görürsünüz.

> **Tek komut (üretim):** `cd apps/frontend && npm run build` yapıp yalnızca backend'i
> çalıştırırsanız, FastAPI inşa edilmiş arayüzü **http://127.0.0.1:8000** adresinde kendisi sunar.

## 3. İlk adımlar — uçtan uca akış

1. **Ayarlar → DeepSeek API anahtarı** — anahtarı girin, **modeli** seçin
   (`deepseek-chat` varsayılan; `deepseek-reasoner` daha derin muhakeme için). Anahtar yalnızca
   bu cihazda saklanır; yanıtlarda maskelenir.
2. **Dönemler** sayfasından bir dönem oluşturun (örn. "2026 Bahar") → içine **ders** ekleyin.
3. **Ders sayfası:**
   - **Materyaller** bölümünden ders kitabını PDF yükleyin → **İndeksle**'ye basın
     (yerel vektör veritabanı kurulur; ilerleme çubuğu gösterilir).
   - **Chapter ekleyin** (örn. "Bağlı Listeler").
4. **Chapter sayfası:**
   - **Guide Slides**'a hocanın sunumunu yükleyin (PDF/PPTX) — slide'lar otomatik çıkarılır.
   - **Not Oluştur** — sunumdaki konuları rehber alıp kitaptan atıflı not üretir (canlı akış).
   - Notta **`[1]`, `[2]`** atıfları tıklanabilir; kaynak parça pop-up'ta açılır.
   - **Quiz Oluştur** — her konu için 5 çoktan seçmeli soru; cevap verince anında açıklamalı geri bildirim.
5. **Ders sayfası → Genel Quiz Oluştur** — tüm chapter notlarından **50 soru**
   (15 çoktan seçmeli + 15 doğru-yanlış + 15 boşluk doldurma + 5 açık uçlu), karışık sırayla.
   - Açık uçlu cevaplar gönderildiğinde **0-10 arası otomatik puanlanır**; doğru/eksik/yanlış/gereksiz
     bölümleri ve **ideal cevap** gösterilir.

## 4. Maliyet

Not/quiz üretimi DeepSeek API'sini kullanır (kendi anahtarınız). Tüm çağrılar
`generation_logs` tablosunda izlenir (tür, model, token sayısı). Örnek: tek chapter notu +
bölüm quizi ≈ **10-30 bin token** (kuruş mertebesinde). Açık uçlu puanlama quiz başına 5 küçük çağrı ekler.

## 5. Güvenlik & Gizlilik

- **Hesap yok, telemetri yok, analitik yok.** Tüm veri yerel (`data/` — SQLite, LanceDB, dosyalar).
- API anahtarı `.env` veya `settings` tablosunda; **asla loglanmaz/yanıtlanmaz** (gitleaks hook'u korur).
- API'ye yalnızca üretim için gerekli kaynak parçaları gider; embedding tamamen yereldir (bge-m3).
- Yedekleme: `data/` klasörünü kopyalamanız yeterli.

## 6. Sorun Giderme

| Sorun | Çözüm |
|-------|-------|
| "API anahtarı ayarlanmadı" | Ayarlar sayfasından anahtarı girin veya `.env`'e yazın |
| "API kotası aşıldı" | Birazdan tekrar deneyin (üstel bekleme uygulanır) |
| Not üretimi atıf hatası veriyor | Kitabın indekslendiğinden emin olun; tekrar deneyin |
| Slide pop-up metin gösteriyor | LibreOffice kurulmamış — metin alıntısı normaldir |
| Backend banner'ı | `uvicorn`'un çalıştığını kontrol edin |
