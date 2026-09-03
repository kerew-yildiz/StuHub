# StuHub — Kullanım Kılavuzu

StuHub, üniversite dersleriniz için **tamamen yerel** çalışan bir ders notu ve quiz uygulamasıdır.
Ders kitaplarınızı (PDF) ve hoca sunumlarınızı yükler; yapay zeka ile **atıflı notlar**, **bölüm quizleri** ve **ders geneli quizler** üretir. Tüm veriniz bilgisayarınızda kalır (`data/` klasörü).

---

## 1. Kurulum (tek seferlik)

Gereksinimler: **Python 3.12 + uv**, **Node ≥ 20 + npm**, **git**, ve en az bir **ücretsiz LLM sağlayıcı anahtarı** (Google Gemini önerilir).

```bash
# 1) Bağımlılıklar
cd apps/backend && uv sync
cd ../frontend && npm install

# 2) API anahtarı
# .env.example dosyasını .env olarak kopyalayıp en az bir sağlayıcı anahtarını doldurun
# (GOOGLE_API_KEY önerilir — https://aistudio.google.com/apikey; veya uygulama içi Ayarlar sayfasından girin)
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

1. **Ayarlar → LLM sağlayıcı anahtarları** — en az bir tanesini girin (Google Gemini önerilir,
   en geniş kota). Birden fazla anahtar girilirse hepsi sırayla yedek olarak kullanılır: biri
   günlük kota sınırına ulaşınca otomatik olarak sıradakine geçilir. Anahtarlar yalnızca bu
   cihazda saklanır; yanıtlarda maskelenir.
2. **Dönemler** sayfasından bir dönem oluşturun (örn. "2026 Bahar") → içine **ders** ekleyin.
3. **Ders sayfası:**
   - **Materyaller** bölümünden ders kitabını PDF yükleyin → **İndeksle**'ye basın
     (yerel vektör veritabanı kurulur; ilerleme çubuğu gösterilir).
   - **Chapter ekleyin** (örn. "Bağlı Listeler").
4. **Chapter sayfası:**
   - **Guide Slides**'a hocanın sunumunu yükleyin (PDF/PPTX/PPT — eski .ppt otomatik çevrilir) — slide'lar otomatik çıkarılır.
   - **Not Oluştur** — sunumdaki konuları rehber alıp kitaptan atıflı not üretir (canlı akış).
   - Notta **`[1]`, `[2]`** atıfları tıklanabilir; kaynak parça pop-up'ta açılır.
   - **Quiz Oluştur** — her konu için 5 çoktan seçmeli soru; cevap verince anında açıklamalı geri bildirim.
5. **Ders sayfası → Genel Quiz Oluştur** — tüm chapter notlarından **55 soru**
   (20 çoktan seçmeli + 15 doğru-yanlış + 15 boşluk doldurma + 5 açık uçlu), karışık sırayla.
   - Puanlama: açık uçlu 5 × 10 puan + kapalı uçlu 50 × 1 puan = **100 puan**.
   - Açık uçlu cevaplar gönderildiğinde **0-10 arası otomatik puanlanır**; doğru/eksik/yanlış/gereksiz
     bölümleri ve **ideal cevap** gösterilir.

## 3b. v2 Özellikleri (Niş Analizi Entegrasyonu)

**Flashcard + uzamsal tekrar:**
- Chapter sayfası **Kartlar** sekmesi → **Kart Oluştur** (not + quizden atıflı kart üretir).
- Kartı çevirmek için tıklayın; arka yüzde **Again / Hard / Good / Easy** — yerel SM-2 algoritması
  her kartın bir sonraki tekrar gününü hesaplar (veri yalnız cihazınızda).
- Ders sayfası **Bugünün Kartları** — günün tekrar kuyruğu (vadesi geçenler önce).

**Materyale Sor (atıflı sohbet):**
- Ders sayfası **Materyale Sor** sekmesi → soru sorun; yanıtlar **zorunlu kaynak atıflı** gelir
  (tıklayınca kaynak parça açılır). Modlar: **Doğrudan** / **Sokratik** (cevap yerine ipucu) /
  **Sınav Modu** (soruyu AI sorar, cevabınızı atıflı değerlendirir).

**Medya alımı (yeni girdiler):**
- Ders sayfası materyal yükleme artık şunları kabul eder: **DOCX, EPUB, görsel (OCR),
  ses kaydı (mp3/m4a/wav/ogg)** — ses otomatik transkribe edilir (yerel faster-whisper;
  ilk kullanımda model indirilir, ücretsiz) ve ardından otomatik indekslenir.
- **YouTube** ve **metin yapıştırma** ders sayfasındaki medya bölümünden eklenir; YouTube
  önce altyazı (tr→en) dener, yoksa sesi yerel olarak çevirir.

**Çalışma rehberi:**
- Chapter/ders **Rehber** sekmesi → **Özet Üret** (özet + anahtar terimler + sınav odakları)
  ve **Kavram Haritası** (nottaki kavramların yönlü haritası).

**Ödev değerlendirici:**
- Ders sayfası **Ödev Değerlendir** sekmesi → talimat + (opsiyonel) ölçütler + ödev metni →
  **0–100 rubrikli puan**, ölçüt kırılımı, güçlü/zayıf yönler ve alıntılı yorumlar.

**Export & arşiv:**
- Not: **PDF İndir** + **MD İndir**. Kartlar: set başına **Anki (.apkg)** + **CSV**;
  ders sayfasından tüm kartları tek Anki paketinde indirin (deck adı `StuHub::{Ders}`).
- Dönem sayfası → **Dönem Arşivi İndir** (zip; "materyal dosyalarıyla" seçeneği).
  Dönemler sayfası → **Arşiv İçe Aktar** (zip seçin) — yeni dönem olarak eklenir
  (mevcut veri asla silinmez; çakışan isme "(içe aktarıldı)" eklenir). Çok cihaz
  taşımanın yerel yolu budur.

**Alışkanlıklar ve mobil:**
- Dönemler sayfasında **streak halkası** (günlük hedef: Ayarlar'dan değiştirilebilir).
- İlk açılışta **3 adımlı onboarding** dönem + derslerinizi kurar.
- Üretim modunda uygulama **PWA** olarak kurulabilir; telefonda aynı ağdan
  `http://<bilgisayar-ip>:8000` ile erişin (veri yine bilgisayarda kalır).

**Çok dilli üretim:** `.env`'e `STUHUB_NOT_DILI=en` (veya `auto`) ekleyin — not/quiz/
flashcard/rehber üretim dili değişir (varsayılan: Türkçe).

## 4. Maliyet

Not/quiz üretimi ücretsiz LLM sağlayıcı zincirini kullanır (Gemini → OpenRouter → Groq →
GitHub Models; geçici çözüm — bkz. `README.md`). Tüm çağrılar `generation_logs` tablosunda
izlenir (tür, model, sağlayıcı, token sayısı). Sağlayıcıların günlük ücretsiz kotaları vardır;
biri tükenince otomatik sıradakine geçilir, hepsi tükenirse ertesi gün sıfırlanana kadar
beklenir. **Embedding, transkripsiyon ve OCR ücretsiz ve yereldir — API kotası harcamaz.**

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
