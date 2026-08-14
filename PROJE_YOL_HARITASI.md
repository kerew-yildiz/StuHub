# PROJE YOL HARİTASI — StuHub DS (v4.2)

> **BELKEMİK BELGESİ** — Bu dosya projenin tek kaynak doğrusudur. Her session başlangıcında bu belge context'e alınır ve ancak ondan sonra işe devam edilir. Tüm ajanlar ve session'lar bu belgeyi referans alır. Belgeyi yalnızca Ana Ajan koordinasyonunda ve Ücretsizlik Ajanı (Teknoloji Envanteri + Değişiklik Günlüğü) düzenleyebilir; her değişiklik Sürüm Geçmişi'ne işlenir.
>
> **Kaynak:** Bu belge v1.0 planı (yerel `.hermes/plans` kaynağı) temel alınarak StuHub DS workspace'ine taşınmıştır. v2.0'da platform ve LLM kararları, v3.0'da mimari denetim raporundaki 17 düzeltme, v4.0'da DeepSeek Harness kazısı (DSH_ARASTIRMA_RAPORU.md + SİSTEM_YETENEKLERİ.md), v4.1'de DSH kataloğu ince ayarı, v4.2'de LLM çıkarımı istisnasının genişletilmesi uygulanmıştır (bkz. Bölüm 15).

---

## 0. Proje Özeti

**Amaç:** Üniversite öğrencileri için yerel web uygulaması (localhost). Öğrenci ders dönemlerini klasörler, her dönemde dersler açar, her ders için notebook oluşturur (metadata + PDF kitaplar), dersin sunumlarını "guide slides" olarak yükler ve chapter'lar oluşturur. Her chapter'da AI destekli **not oluşturma**, **bölüm quizi** ve dersin tamamını kapsayan **genel quiz** mevcuttur. Tüm AI çıktısı materyallere **atıflıdır** ve interaktif atıf pop-up'ları ile kaynaklandırılır.

**Yaklaşım:** Local-first web uygulaması. Veriler, kitaplar, sunumlar ve vektör indeksleri tamamen yerel diskte saklanır (SQLite + LanceDB + dosya deposu). Yapay zeka çıkarımı **kullanıcının kendi DeepSeek API anahtarı** ile yapılır — kullanıcı kararıyla **yerel LLM çalıştırılmaz** ve LLM gerektiren görevlerde ücretli API kullanımına izin verilir (tek istisna ailesi; bkz. Bölüm 7). Bunun dışındaki tüm araçlar ücretsiz ve açık kaynaktır; embedding modeli LLM değildir ve tamamen yerel çalışır. Uygulamada hesap, telemetri veya analitik yoktur.

**Ürün dili:** Türkçe (UI, prompt'lar, dokümantasyon).

**Geliştirme katmanı:** Proje, DeepSeek Harness (DSH, MIT — ücretsiz) üzerinde geliştirilir. DSH yalnızca geliştirme/orkestrasyon katmanıdır; ürün kodu (FastAPI/React) DSH plugin'i değildir (sınır: `SİSTEM_YETENEKLERİ.md` Bölüm 7). Her session başında `PROJE_YOL_HARITASI.md`'den sonra ikinci zorunlu okuma `SİSTEM_YETENEKLERİ.md`'dir; DSH davranışında şüphede yerel DSH checkout'unun `docs\` dizini canlı otoritedir.

---

## 1. Ürün Akışı (User Flow)

```
1) Ana ekran → Dönem klasörleri (örn: "2026 Bahar", "2026 Yaz")
2) Dönem seç → Ders listesi
3) Ders oluştur penceresi → Ad, hocası, metadata + PDF kitap yükle
4) Ders notebook sayfası açılır → "Yeni Chapter Ekle" butonu
5) Chapter oluştur: ad + guide slides (PPTX/PDF, hocanın sunumları)
6) Chapter aç → [Not Oluştur] [Quiz] [Genel Quiz] butonları
```

### 1.1 Chapter İçi Özellikler

#### 1.1.1 Not Oluştur
- Sistem, chapter'ın **guide slides** içeriğini **rehber** olarak alır
- Dersin PDF kitaplarını **tarar** (RAG: chunk + embed + hibrit retrieve)
- Guide slides'taki **tüm konuları eksiksiz** içerecek şekilde öğrenci için not hazırlar (kapsama doğrulamalı, map-reduce)
- Her bilgi parçası **inline atıflıdır** (örn: [1], [2]) ve atıf kaynağı (PDF sayfa / PPTX slide) kayıtlıdır
- Üretim süreci **stream edilir**, kullanıcı ilerlemeyi görür
- Ajan zinciri: [Ana Ajan → Indexer Ajan (RAG hazır) → Not Üretici Ajan → Kalite Kontrol Ajan]

#### 1.1.2 Bölüm Quizi
- Oluşturulan notları tarar, konuları saptar (başlıklar)
- Her konu için **5 çoktan seçmeli soru** üretir
- Cevap interaksiyonunda **anında geri bildirim**: doğru/yanlış
- Yanlışsa: doğru cevabı **materyallere atıfta bulunarak** açıklar (örn: "[1] slide 3")
- Atıflar **interaktif**: atıfa tıklandığında pop-up'ta o kaynağın ilgili kısmı gösterilir (PDF sayfası veya PPTX slide içeriği)
- Ajan zinciri: [Not Üretici çıktısı → Chapter Quiz Ajan → Kalite Kontrol Ajan]

#### 1.1.3 Genel Quiz
- **50 soru**, ders seviyesinde, **bütün chapter'lar karışık sırayla**
- Dağılım: **15 çoktan seçmeli + 15 doğru-yanlış + 15 boşluk doldurma + 5 açık uçlu**
- İlk 3 kategori (MCQ/TF/FIB): bölüm quizzesi ile aynı interaktif feedback sistemi
- Açık uçlu sorularda:
  - Sistem kullanıcı cevabını analiz eder
  - **10 üzerinden objektif puanlama**
  - **Doğru, eksik, yanlış, gereksiz** cevap bölümlerini kullanıcıya bildirir ve açıklar
  - Açıklamanın ardından **ideal cevap** örneği hazırlar (atıflı)
- Ajan zinciri: [Tüm notlar → Overall Quiz Ajan → (açık uçlu cevap gönderimi → Essay Grader Ajan) → Kalite Kontrol Ajan]

---

## 2. Mimari Genel Bakış

```
┌────────────────────────────────────────────────────────────────┐
│               Tarayıcı (localhost Web Uygulaması)               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐    │
│  │  React UI   │  │  State Yntm │  │  API + SSE Client    │    │
│  │ (TypeScript)│  │  (Zustand)  │  │ (fetch, EventSource) │    │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬───────────┘    │
└─────────┼────────────────┼─────────────────────┼───────────────┘
          │  (Vite dev proxy veya aynı kök sunucu)  │
          ▼                ▼                     ▼
┌────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                     │
│  ┌────────────┐ ┌────────────┐ ┌───────────────────────────┐   │
│  │ Medya Gir. │ │  SQLite    │ │  AI Pipeline Servisleri   │   │
│  │(PDF/PPTX/  │ │ (metadata) │ │  (not, quiz, puanlama,    │   │
│  │ YouTube/ses│ │            │ │   chat, kart, rehber,     │   │
│  │ DOCX/EPUB/ │ │            │ │   essay, arşiv)           │   │
│  │ OCR)       │ │            │ │                           │   │
│  └────────────┘ └────────────┘ └───────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
                   │                        │
        ┌──────────┼──────────┐             ▼
        ▼          ▼          ▼      DeepSeek API (chat, stream)
 ┌──────────┐ ┌──────────┐ ┌──────────────┐        ▲
 │ LanceDB  │ │ sentence-│ │  File Store  │        │ (OpenAI uyumlu,
 │(vektörler)│ │transformer│ │(materyal+    │        │  kullanıcı anahtarı)
 └──────────┘ │(embedding)│ │ PDF render) │        │
              └──────────┘ └──────────────┘        │
 Yerel STT (faster-whisper) · Yerel OCR (rapidocr) · yt-dlp (altyazı)
```

### 2.1 Teknoloji Kararları

| Katman | Seçim | Lisans | Gerekçe |
|--------|-------|--------|---------|
| Platform | Localhost web (tarayıcı) | — | Kullanıcı kararı; kurulum yok, her ortamda çalışır |
| Geliştirme/Orkestrasyon | DeepSeek Harness (dsh) | MIT | Ücretsiz; 15 ajan ve orkestrasyon bu çalışma zamanında koşar (`SİSTEM_YETENEKLERİ.md`) |
| Frontend | React 18 + TypeScript + Vite | MIT | Standart, tip-güvenli, iyi dev deneyimi |
| Stil | Tailwind CSS + CSS Variables | MIT | Design tokens, dark-mode, minimal CSS (bkz. `YETENEKLER/07-stil-rehberi.md`) |
| State | Zustand | MIT | Sade, TypeScript dostu |
| Backend API | FastAPI (Python) | MIT | Async, OpenAPI, AI/ML ekosistemi güçlü |
| Veritabanı | SQLite + aiosqlite | Public Domain | Yerel, zero-config, güvenilir |
| Vektör DB | LanceDB (embedded) | Apache-2.0 | Server yok, hızlı, yerel |
| LLM | DeepSeek chat API (`deepseek-chat`) | Ücretli (kullanıcı onaylı istisna) | OpenAI uyumlu, Türkçe güçlü, stream destekli, düşük maliyet |
| LLM SDK | openai (Python) | Apache-2.0 | DeepSeek'in resmi uyumluluk yolu |
| Embedding | sentence-transformers + bge-m3 (öncelik) / multilingual-e5-small | MIT/Apache-2.0 | Yerel, ücretsiz, Türkçe/çok dilli; DeepSeek embedding sunmaz ([issue #806](https://github.com/deepseek-ai/DeepSeek-V3/issues/806)) |
| PDF Metin | pymupdf + marker-pdf (OCR yedek) | AGPL-3.0 / GPL-3.0 | Hızlı + taranmış fallback; copyleft uyarısı: kişisel yerel kullanımda kabul; dağıtım hedeflenirse pdfplumber (MIT) / Tesseract (Apache-2.0) ile değiştir (Ücretsizlik Ajanı denetimi) |
| PPTX | python-pptx | MIT | Standart, güvenilir |
| Slide render | LibreOffice headless (PPTX→PDF) + pdfjs | MPL-2.0 / Apache-2.0 | Pop-up'ta slide gösterimi; LibreOffice yoksa metin alıntısı fallback |
| Atıflama | citations_ledger + doğrulama adımı | — | Her üretimde kanıt tabanlı doğrulama (bkz. `YETENEKLER/06-atif-sistemi.md`) |
| CI/CD | GitHub Actions | Ücretsiz tier | Entegre, ücretsiz |
| Paket Yönetimi | pnpm + uv (Python) | MIT/PSF | Hızlı, modern |
| Kod QA (backend) | ruff + pyright + pytest | MIT | Lint + tip + test |
| Kod QA (frontend) | eslint + tsc + vitest + playwright | MIT | Lint + tip + test + E2E |
| Güvenlik SAST | bandit, pip-audit, pnpm audit, semgrep | MIT/Apache | Çok-katmanlı tarama |
| Sırlar tarama | trufflehog / gitleaks | MIT | API anahtarı sızıntısı engeli |

### 2.2 Frontend ↔ Backend İletişimi

1. **Geliştirme:** Vite dev server (`http://localhost:5173`) API isteklerini `http://127.0.0.1:8000`'e proxy'ler.
2. **Üretim/tek komut:** FastAPI, inşa edilmiş frontend'i (`apps/frontend/dist`) kendisi servis eder; tek adreste çalışır (DevOps Ajan sorumluluğu).
3. **Tüm API çağrıları:** `fetch(http://localhost:<port>/api/...)`; dosya erişimi `/api/materials/{id}/file` üzerinden Range destekli olur (pdfjs sayfa render'ı için zorunlu).
4. **Health check:** `GET /health` — frontend 5 saniyede bir yoklar; backend kapalıysa banner gösterir.
5. **Streaming:** Not üretimi `POST /api/chapters/{id}/notes` SSE ile akar (DeepSeek stream modu); frontend ilerleme göstergesi çizer.
6. **Graceful shutdown:** Backend, kullanıcı tarafından kapatılınca aktif üretim işini `indexing_jobs`/`generation_logs` üzerinden işaretler, devam edilebilir bırakır.

#### Hata Yönetimi
- **LLM kesintisi/429:** Üstel backoff (1s, 2s, 4s, ...), 5 hata sonrası 30s circuit breaker; kullanıcıya net Türkçe mesaj + iş durumu kaydı; tamamlanan kısımlar kaybolmaz.
- **İstek timeout:** Varsayılan 30s, LLM üretimi için 300s (batch başına).
- **İdempotent GET'ler:** Retry güvenli; üretim POST'ları job tabanlıdır (tekrar tetiklenebilir, çift iş çalışmaz).

### 2.3 Veri Akışı: Not Oluşturma

```
1) Kullanıcı "Not Oluştur" tıklar
       │ ▼
2) Frontend → POST /api/chapters/{id}/notes  (SSE stream başlar)
       │ ▼
3) FastAPI: slides tablosundan guide slide içeriğini yükle
       │ ▼
4) LLM: slide'lardan konu listesi çıkar (konu + anahtar terimler)
       │ ▼
5) Her konu için hibrit retrieval: LanceDB vektör top-k + konu terimi keyword boost
       │ ▼
6) Konu başına (map-reduce): context + not üretim prompt'u → DeepSeek (stream)
       │ ▼
7) Kapsama doğrulama: konu kontrol listesi ↔ üretilen not (eksikte max 3 iterasyon)
       │ ▼
8) Atıf doğrulama: her [n] → chunk metni fuzzy eşleşme (sınırda LLM onayı)
       │ ▼
9) notes tablosuna kaydet (content_md + citations_json + topics_json), generation_logs yaz
       │ ▼
10) Frontend: NoteViewer + CitationPopup bileşenleriyle render
```

### 2.4 Veri Akışı: Quiz Üretimi

```
Bölüm Quizi:
1) "Quiz" tıkla → POST /api/chapters/{id}/quiz
2) Notlar + atıfları yükle → konuları saptar (başlıklar + topics_json)
3) Her konu için 5 MCQ üret (LLM, json_schema enforced, atıf zorunlu)
4) Tüm atıflar resolve + doğrulanır → kaydet → dön
5) Frontend: QuizPlayer, her cevap interaksiyonunda anında feedback

Genel Quiz:
1) "Genel Quiz" tıkla → POST /api/courses/{id}/overall-quiz
2) TÜM chapter notları + atıfları yükle; konuları chapter'lar boyunca stratize et
3) Batch üretim: kategori bazlı 5–10 soru/batch → 15 MCQ + 15 TF + 15 FIB + 5 açık uçlu
4) Her batch JSON şema doğrulaması → seed'li karıştırma ile birleştir
5) Dağılım + atıfları doğrula → kaydet → dön
6) Frontend: QuizPlayer, tip-bazlı render (FIB: normalize edilmiş eşleştirme; kabul listesi üretim anında genişletilir — interaksiyonda LLM çağrısı yok)
7) Açık uçlu gönderim → Essay Grader Ajanı → 0-10 + breakdown + ideal cevap (güven kontrolü dahil)
```

### 2.5 API Yapılandırması

- Anahtar: kullanıcı **Ayarlar sayfasından** girer → `settings` tablosunda yerelde saklanır; geliştirme sırasında `.env` (`DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`) kullanılır. **Anahtar asla commit edilmez, kodda asla görünmez.**
- Model: yapılandırılabilir (`deepseek-chat` varsayılan); Ayarlar'dan değiştirilebilir.
- Maliyet gözetimi: her LLM çağrısı `generation_logs`'a yazılır (kind, model, prompt/completion token). Ücretsizlik Ajanı bu log'u denetler; israf tespitinde prompt optimizasyonu başlatır.
- Yerel model (Ollama/GGUF) desteği: yok (kullanıcı kararı — yerel LLM çalıştırılmaz); alternatif OpenAI uyumlu sağlayıcıya geçiş Bölüm 13'tedir.

---

## 3. Veri Şeması (SQLite)

```sql
terms (id, name, start_date, end_date, created_at)
courses (id, term_id, name, instructor, metadata_json, created_at)
materials (
  id, course_id, type,             -- 'textbook' | 'slides' | 'youtube' | 'audio' | 'docx' | 'epub' | 'image' | 'text' (v2)
  filepath, extracted_text,
  page_count,                      -- render + chunk offset için
  vector_ns,                       -- LanceDB namespace (course_{id}_chunks)
  created_at
)
chapters (id, course_id, title, created_at)
slides (                            -- slide bazlı atıf için granülarite
  id, chapter_id, material_id, slide_no, content_text
)
notes (id, chapter_id, content_md, citations_json, topics_json, generated_at, model_used)
quizzes (id, chapter_id, questions_json, created_at)
quiz_attempts (id, quiz_id, user_answers_json, score, feedback_json, created_at)
overall_quizzes (id, course_id, questions_json, created_at)
overall_attempts (id, overall_quiz_id, answers_json, score_json, created_at)
indexing_jobs (id, course_id, material_id, status, progress, error, kind, created_at, updated_at)
                                                        -- v2: kind = 'index' | 'transcribe'
citations_ledger (id, chunk_id, text, source_type, source_id, page, slide)
generation_logs (id, kind, course_id, chapter_id, model, prompt_tokens, completion_tokens, created_at)
settings (key, value)               -- API anahtarı, model adı vb. (yerel, commit dışı)
-- ── v2 tabloları (Bölüm 17; migration 0001/0002 — sql/schema.sql tek doğruluk kaynağı) ──
flashcard_sets (id, course_id, chapter_id, cards_json, created_at, model_used)
card_reviews (id, set_id, card_index, ease_factor, interval_days, repetitions, due_at, last_rating, reviewed_at)
chat_messages (id, course_id, role, content, citations_json, mode, created_at)   -- mode: direct|socratic|quiz
study_guides (id, course_id, chapter_id, kind, content_json, created_at, model_used)  -- kind: summary|concept_map
essay_submissions (id, course_id, chapter_id, prompt, user_text, grade_json, created_at)
activity_log (id, date, kind, count, course_id)          -- kind: note|quiz|flashcard|chat
schema_migrations (version, name, applied_at)
```

LanceDB chunk satırı: `{ chunk_id, course_id, material_id, page, slide, text, vector }` — `page/slide` offset'leri atıf pop-up'ının doğru bölümü açmasını sağlar.

**Not:** Sorular `questions_json` içinde kasıtlı denormalize tutulur (kişisel uygulama ölçeği). Atıf doğrulama bu blob'u ayrıştırıp `citations_ledger` ile eşleştirir. `models` tablosu (v1.0'dan) kaldırılmıştır; yerel LLM kullanıcı kararıyla kapsam dışıdır, alternatif sağlayıcı geçişi Bölüm 13'tedir.

**v2 migration runner (Bölüm 17):** `init_db`, `schema.sql`'i uyguladıktan sonra `sql/migrations/NNN_*.sql` dosyalarını sırayla işler ve `schema_migrations`'a kaydeder; migration dosyaları idempotenttir (politika: `sql/migrations/README.md`).

---

## 4. Ajan Mimarisi

> **Rol ayrımı:** Üretim ajanlarının (04–08) md dosyaları hem DSH üzerindeki geliştirme rolünü hem de uygulamanın çalışma anı (runtime) pipeline sözleşmesini tanımlar. DSH ajanları ürünü **geliştirir**; ürün çalışırken aynı sözleşmeyi `apps/backend/src/agents/` altındaki FastAPI servisleri yürütür (Bölüm 14). İki katman birbirinin yerine geçmez.

### 4.1 Ajan Kataloğu (20 ajan)

| # | Ajan | Dosya | Rol | Tetik | Effort |
|---|------|-------|-----|-------|--------|
| 0 | **Ana Ajan (Main Orchestrator)** | `AJANLAR/00-ana-ajan.md` | orchestrator | Session başı, faz geçişi, "Başla" | **V4 Pro — SABİT** |
| 1 | **Kalite Kontrol Ajanı** | `AJANLAR/01-kalite-kontrol-ajani.md` | leaf | Her deliverable sonrası, pre-merge | Flash (yükseltilebilir) |
| 2 | **Stil Ajanı** | `AJANLAR/02-stil-ajani.md` | leaf | UI değişikliği, yeni bileşen | Flash (yükseltilebilir) |
| 3 | **Ücretsizlik Ajanı** | `AJANLAR/03-ucretsizlik-ajani.md` | leaf | Yeni bağımlılık, periyodik denetim, maliyet log'u | Flash (yükseltilebilir) |
| 4 | **Indexer Ajan** | `AJANLAR/04-indexer-ajani.md` | leaf | Yükleme sonrası, arka plan job | Flash (yükseltilebilir) |
| 5 | **Not Üretici Ajan** | `AJANLAR/05-not-uretici-ajani.md` | leaf | "Not Oluştur" butonu | Flash (yükseltilebilir) |
| 6 | **Chapter Quiz Ajan** | `AJANLAR/06-chapter-quiz-ajani.md` | leaf | "Quiz" butonu | Flash (yükseltilebilir) |
| 7 | **Overall Quiz Ajan** | `AJANLAR/07-overall-quiz-ajani.md` | leaf | "Genel Quiz" butonu | Flash; Ana Ajan genellikle **V4 Pro'ya yükseltir** (en karmaşık üretim) |
| 8 | **Essay Grader Ajan** | `AJANLAR/08-essay-grader-ajani.md` | leaf | Açık uçlu cevap gönderimi | Flash (yükseltilebilir) |
| 9 | **Değerlendirme Ajanı** | `AJANLAR/09-degerlendirme-ajani.md` | leaf | Faz sonu, kalite kapısı öncesi | Flash (yükseltilebilir) |
| 10 | **Test Mühendisi Ajan** | `AJANLAR/10-test-muhendisi-ajani.md` | leaf | Yeni özellik, coverage eksiği | Flash (yükseltilebilir) |
| 11 | **DevOps Ajan** | `AJANLAR/11-devops-ajani.md` | leaf | CI/CD, build, dokümantasyon | Flash (yükseltilebilir) |
| 12 | **Güvenlik Denetim Ajanı** | `AJANLAR/12-guvenlik-denetim-ajani.md` | leaf | Pre-release, gizlilik değişikliği | Flash; pre-release denetimlerde **V4 Pro'ya yükseltilir** |
| 13 | **Frontend Geliştirici Ajan** | `AJANLAR/13-frontend-gelistirici-ajani.md` | leaf | Faz 0–6 + v2 UI işleri, yeni sayfa/bileşen | Flash (yükseltilebilir) |
| 14 | **Backend Geliştirici Ajan** | `AJANLAR/14-backend-gelistirici-ajani.md` | leaf | Faz 0–6 + v2 API/servis/şema işleri | Flash (yükseltilebilir) |
| 15 | **Flashcard Ajan** | `AJANLAR/15-flashcard-ajani.md` | leaf | "Flashcard Oluştur" butonu, V2.2 işleri | Flash (yükseltilebilir) |
| 16 | **Materyale Sor Ajan** | `AJANLAR/16-materyal-sor-ajani.md` | leaf | Chat mesajı, V2.1 işleri | Flash (yükseltilebilir) |
| 17 | **Medya Alım Ajan** | `AJANLAR/17-medya-alim-ajani.md` | leaf | Medya yükleme (YouTube/ses/doküman), V2.6 işleri | Flash (yükseltilebilir) |
| 18 | **İhracat Ajan** | `AJANLAR/18-ihracat-ajani.md` | leaf | Export/import aksiyonları, V2.3 işleri | Flash (yükseltilebilir) |
| 19 | **Çalışma Rehberi Ajan** | `AJANLAR/19-calisma-rehberi-ajani.md` | leaf | "Rehber" sekmesi, V2.7 işleri | Flash (yükseltilebilir) |

### 4.2 Effort Kuralı (Kullanıcı Kararı)

- **Ana Ajan: her zaman V4 Pro (max).** Bu seviye hiçbir koşulda düşürülmez.
- **Diğer tüm ajanlar: varsayılan V4 Flash.** Ana Ajan, görevin zorluk seviyesine göre (belirsiz gereksinim, mimari/tasarım kararı, karmaşık prompt mühendisliği, güvenlik kritik iş) ilgili ajanı **V4 Pro'ya yükseltir**.
- Uygulama: model seviyesi workflow faz bazında `provider`/`model` override'ı ile belirlenir (`phases[].provider/model` ve `agent()` opts). Tekil subagent delegasyonlarında varsayılan seviye (V4 Flash) geçerlidir; yükseltme gerektiren görevler workflow üzerinden veya Settings → Models kalıcı rotalarıyla çalıştırılır. Prompt metnine seviye yazmak çalışma modelini değiştirmez.

### 4.3 Yürütme Akışı

```
Kullanıcı Aksiyonu
    │ ▼
Ana Ajan (V4 Pro: analiz eder, parçalar, effort atar, delegate eder)
    │
    ├─► Indexer Ajan (arka plan, indexing job'ları)
    │
    ├─► Not Üretici Ajan
    │       │ ▼
    │   Kalite Kontrol → Stil Ajanı (UI ise)
    │
    ├─► Chapter Quiz Ajan [chapter başına paralel]
    │       │ ▼
    │   Kalite Kontrol
    │
    ├─► Overall Quiz Ajan (V4 Pro'ya yükseltilir)
    │       │ ▼
    │   Kalite Kontrol
    │       │ ▼
    │   Essay Grader Ajan [açık uçlu soru başına paralel]
    │       │ ▼
    │   Kalite Kontrol
    │
    ├─► Flashcard Ajan [not+quiz sonrası; chapter başına paralel]
    │
    ├─► Materyale Sor Ajan [kullanıcı mesajıyla; yanıt atıf zorunlu]
    │
    ├─► Medya Alım Ajan [yükleme sonrası; transkripsiyon arka planda]
    │
    ├─► İhracat Ajan [export/import aksiyonuyla]
    │
    ├─► Çalışma Rehberi Ajan [rehber sekmesiyle]
    │
    ├─► Değerlendirme Ajan (faz sonu ölçüm → Kalite Kontrol'e kanıt)
    ├─► Backend Geliştirici Ajan [API/servis/şema — modül başına]
    ├─► Frontend Geliştirici Ajan [UI — Stil Ajanı denetiminde]
    ├─► Test Mühendisi Ajan [TDD tüm yeni kod]
    ├─► DevOps Ajan [CI/CD, build, dokümantasyon]
    ├─► Güvenlik Denetim Ajanı [pre-release]
    └─► Ücretsizlik Ajan (sürekli denetim + maliyet bekçisi; blokaj yapabilir)
```

### 4.4 Paralellik Kuralları

- **Indexer:** Her zaman arka planda (bekleyen `indexing_jobs` işlenir)
- **Medya Alım/Transkripsiyon:** Her zaman arka planda (`indexing_jobs.kind='transcribe'` → otomatik `'index'` zinciri)
- **Flashcard Üretimi:** Chapter başına paralel (o chapter'ın notu + quiz'i hazır olduktan sonra)
- **Materyale Sor:** Kullanıcı mesajları eş zamanlı; yanıt üretimi diğer üretimleri bloklamaz
- **Çalışma Rehberi:** Chapter bazında paralel; ders seviyesi rehber, chapter rehberlerinin birleşimidir
- **Not Üretimi → Chapter Quiz:** Sıralı (quiz notlara ihtiyaç duyar)
- **Tüm Chapter Quizleri:** Chapter başına paralel
- **Overall Quiz:** Tüm chapter notları bittikten sonra; kategori batch'leri paralel üretilebilir
- **Essay Grader:** Açık uçlu soru başına paralel
- **Kalite Kontrol / Değerlendirme:** Her deliverable/faz için paralel çalışabilir
- **Stil Ajanı:** UI bileşeni başına paralel
- **Test Mühendisi:** Modül başına paralel (TDD)
- **Backend/Frontend Geliştirici:** API sözleşmesi sabitlendikten sonra modül başına paralel; iki uç sözleşme üzerinden eş zamanlı ilerleyebilir
- **DevOps:** Pipeline aşaması başına sıralı
- **Güvenlik:** On-demand (pre-release, major change)
- **Ücretsizlik Ajanı:** Sürekli; ücretli araç veya kontrolsüz maliyet tespitinde bloklar

### 4.5 Session Yaşam Döngüsü

```
Session Başlangıcı
    │ ▼
PROJE_YOL_HARITASI.md context'e yüklenir (bu belge)
    │ ▼
SİSTEM_YETENEKLERİ.md context'e yüklenir (DSH yetenek kataloğu; derin kazı: DSH_ARASTIRMA_RAPORU.md)
    │ ▼
Ana Ajan (V4 Pro): mevcut durumu okur, sonraki görev batch'ini tanımlar, effort atar
    │ ▼
Ajanlara delegate eder (mümkün olduğunca paralel). Delegasyon prompt'u kendi kendine yeterlidir:
    hedef ajanın AJANLAR/ + ilgili YETENEKLER/ dosya YOLLARI + SİSTEM_YETENEKLERİ.md'nin ilgili
    bölümü + görev + bitirme kriteri verilir; alt ajan dosya içeriklerini read aracıyla kendisi açar
    (Ana Ajan context tasarrufu — içerikleri prompt'a gömme zorunluluğu yoktur)
    │ ▼
Bitiş bildirimlerini bekle (busy-poll yasak); final cevaptan önce ilgili tüm işleri job_output ile topla
    │ ▼
Kalite kapıları (o faz için uygulanabilir kapılar geçmeli; Bölüm 12)
    │ ▼
Yol haritası durumunu güncelle → checkpoint commit
    │ ▼
Session Sonu (state persist)
```

#### Başlatma (Kickoff) Protokolü — kullanıcı "Başla" dediğinde

1. Ana Ajan `PROJE_YOL_HARITASI.md` → `SİSTEM_YETENEKLERİ.md` sırasıyla okur; uzun soluklu teslimat hedefi oluşturur (`create_goal` — yalnızca doğrudan insan isteğiyle) ve hedefi teslimata kadar sürdürür. Session resume/fork sonrası goal disarm edilmişse `update_goal` action: resume ile yeniden silahlanır; `complete` yalnızca hedef gerçekten bittiğinde verilir.
2. Mevcut durumu denetler; Faz 0.0 ön koşullarını tek tek doğrular: git init + `.gitignore` (`data/`, `.env`) + gitleaks pre-commit; Python ≥ 3.11 + uv ve Node ≥ 20 + pnpm sürümleri; DSH çalışır durumda. DeepSeek API anahtarı Faz 3'ten önce temin edilecek şekilde planlanır (anahtar eksikse Faz 0–2 bloklanmaz). Eksik araç/kurulum varsa kullanıcıya bildirir (`ask_user_question`).
3. Faz 0'dan başlayarak faz faz ilerler: her faz için görevleri parçalar → paralel/sıralı plan → delegasyon → kalite kapıları → faz raporu.
4. Gerektiğinde yeni session'lar ve alt ajanlar açar; durumu her checkpoint'te yol haritasına ve git geçmişine işler.
5. Ürün, Bölüm 12 kalite kapılarının tamamından geçtiğinde teslim raporu sunar.
6. Kullanıcıya soru sorma hakkı yalnız Ana Ajan'dadır (`ask_user_question` canlı kök ajanda çalışır); alt ajanlar eksik bilgi/karar ihtiyacını rapor eder. `ralph` yalnızca kullanıcı açıkça Ralph/fresh-agent döngüsü isterse kullanılır.

---

## 5. Ajan-Yetenek Eşlemesi

| Ajan | Yetenek Dosyaları + DSH Araçları |
|------|----------------------------------|
| Ana Ajan | `PROJE_YOL_HARITASI.md`, `SİSTEM_YETENEKLERİ.md`, tüm `AJANLAR/` + `YETENEKLER/` (dağıtımda); subagent, workflow, goal, todo_write, ask_user_question, job_* |
| Kalite Kontrol | Bölüm 12 kalite kapıları; `09-degerlendirme-ajani.md` kanıtları; pwsh (test/lint komutları) |
| Stil | `YETENEKLER/07-stil-rehberi.md`; read/write/edit; ekran görüntüsü incelemesi |
| Ücretsizlik | `YETENEKLER/08-ucretsiz-arac-envanteri.md`; `PROJE_YOL_HARITASI.md` (Bölüm 2.1, 7, 15 düzenleme yetkisi); web_search |
| Indexer | `YETENEKLER/01-pdf-pptx-isleme.md`; pwsh (uv, python) |
| Not Üretici | `YETENEKLER/02-rag-not-uretimi.md`, `06-atif-sistemi.md` |
| Chapter Quiz | `YETENEKLER/03-chapter-quiz-uretimi.md`, `06-atif-sistemi.md` |
| Overall Quiz | `YETENEKLER/04-overall-quiz-uretimi.md`, `06-atif-sistemi.md` |
| Essay Grader | `YETENEKLER/05-acik-uclu-puanlama.md`, `14-essay-degerlendirme.md`, `06-atif-sistemi.md` |
| Flashcard | `YETENEKLER/09-flashcard-ve-uzamsal-tekrar.md`, `06-atif-sistemi.md` |
| Materyale Sor | `YETENEKLER/10-materyale-sor.md`, `06-atif-sistemi.md` |
| Medya Alım | `YETENEKLER/11-medya-alimi.md`, `01-pdf-pptx-isleme.md` |
| İhracat | `YETENEKLER/12-ihracat-formatlari.md` |
| Çalışma Rehberi | `YETENEKLER/13-calisma-rehberi.md`, `06-atif-sistemi.md` |
| Değerlendirme | Tüm üretim yetenekleri (01–15) + test altyapısı; eval kümesi oluşturma |
| Backend Geliştirici | `PROJE_YOL_HARITASI.md` Bölüm 3, 8, 11, 17; `YETENEKLER/01–15` (runtime sözleşmeler); pwsh (uv, pytest) |
| Frontend Geliştirici | `YETENEKLER/07-stil-rehberi.md`; `AJANLAR/02-stil-ajani.md` denetimi; pnpm/vitest/playwright |
| Test Mühendisi | pytest/vitest/Playwright; pwsh |
| DevOps | GitHub Actions; pwsh (build, audit); README + kullanıcı dokümantasyonu |
| Güvenlik Denetim | Bölüm 8; bandit/pip-audit/pnpm audit/gitleaks; pwsh |

> **Ortak referans:** Tüm ajanların DSH davranışına dair yetki dosyası `SİSTEM_YETENEKLERİ.md`'dir (araç kataloğu, sandbox/onay kuralları, orkestrasyon rehberi); tam kazı ve kaynak dokümantasyon `DSH_ARASTIRMA_RAPORU.md`'dedir. DSH'in somut davranışında şüphede canlı referans: yerel DSH checkout'unun `docs\` dizini.

---

## 6. Faz Planı (8 Hafta)

### Faz 0 — Temeller (Hafta 1)
- 0.0 **Ön Koşullar (Ana Ajan Faz 0 başında doğrular):** git; Python ≥ 3.11 + uv; Node ≥ 20 + pnpm; DeepSeek API anahtarı (kullanıcı sağlar, Ayarlar sayfasına girilir); isteğe bağlı LibreOffice (PPTX render; yoksa metin fallback); gitleaks. Proje-yerel araçlar `.tools/` altında toplanır (mevcut: uv-python 3.12, gitleaks — kickoff'ta sürümler doğrulanır)
- 0.1 Repo & Tooling (monorepo, CI, lint, type-check, gitleaks pre-commit)
- 0.2 SQLite Şema & Migration (Bölüm 3)
- 0.3 Backend İskeleti & Health Check
- 0.4 Frontend Scaffold (Vite dev server + proxy)

### Faz 1 — Dönem & Ders Yönetimi (Hafta 2)
- 1.1 Dönem CRUD API + UI
- 1.2 Ders CRUD + Metadata + PDF Yükleme
- 1.3 Ders Notebook Landing Page ("Chapter Ekle" butonu)
- 1.4 **Ayarlar sayfası: API anahtarı + model seçimi** (settings tablosu)

### Faz 2 — Chapter & Guide Slides (Hafta 3)
- 2.1 Chapter CRUD + Guide Slide Çıkarımı (PDF/PPTX; PPTX→PDF dönüşümü)
- 2.2 Vektör İndekleme Pipeline (chunk + embed + LanceDB; indexing_jobs)

### Faz 3 — Not Oluşturma (Hafta 4)
- 3.1 Not üretimi prompt & pipeline (map-reduce, hibrit retrieval, kapsama doğrulama)
- 3.2 SSE streaming + ilerleme göstergesi
- 3.3 Not Viewer + interaktif atıflar (CitationPopup)

### Faz 4 — Bölüm Quiz (Hafta 5)
- 4.1 Quiz üretimi pipeline (5 MCQ/konu, atıf zorunlu)
- 4.2 Quiz state & persistence + anında feedback

### Faz 5 — Genel Quiz (Hafta 6)
- 5.1 Batch quiz üretimi (50 soru, karışık tip + sıra)
- 5.2 FIB eşleştirme (normalizasyon + üretim anında genişletilmiş kabul listesi)
- 5.3 Açık uçlu otomatik puanlayıcı (rubrik + güven kontrolü)

### Faz 6 — Polish, Kalite & Teslim (Hafta 7-8)
- 6.1 Stil cilası (stil rehberi uyumu, tema, mikro-metinler)
- 6.2 Değerlendirme Ajanı ölçümleri + Kalite kapıları (Bölüm 12)
- 6.3 Kullanıcı kabul testleri (uçtan uca akış)
- 6.4 Kullanıcı dokümantasyonu (kurulum, kullanım kılavuzu) + README
- 6.5 Pre-release güvenlik denetimi

---

## 7. Ücretsizlik Sözleşmesi (Ücretsizlik Ajanı tarafından zorunlu)

**Kural: Tüm araçlar ücretsiz ve açık kaynak olmalıdır. Tek istisna ailesi: LLM çıkarımı — kullanıcı kararıyla yerel LLM çalıştırılmaz; LLM gerektiren görevlerde ücretli API kullanımına izin verilir (birincil sağlayıcı: kullanıcının DeepSeek API anahtarı). LLM dışındaki her araç ücretsiz/açık kaynak kalır.**

### Kayıtlı İstisna (LLM Çıkarımı)
| İstisna | Koşul | Yönetim |
|---------|-------|---------|
| DeepSeek chat API (birincil) | Kullanıcı kendi anahtarını sağlar; ürün çıkarımı (not/quiz/puanlama) + geliştirme sırasındaki LLM ihtiyaçları | `generation_logs` ile maliyet gözetimi; Ücretsizlik Ajanı prompt verimliliğini denetler |
| Alternatif OpenAI uyumlu LLM sağlayıcı | Yalnızca kullanıcı onayıyla; DeepSeek'in karşılamadığı somut bir ihtiyaçta | Aynı maliyet gözetimi; istisna kaydına onay işlenir |

> **Not:** Yerel embedding modeli (sentence-transformers + bge-m3) **LLM değildir**; hafif CPU yüküyle yerelde çalışır, ücretsizdir ve bu istisnanın dışındadır. Yerel LLM (Ollama/GGUF) kullanıcı kararıyla kapsam dışıdır.

### Yasak (Tespitte Bloklar)
- LLM dışı ücretli SaaS/API'ler: vektör DB bulutları (Pinecone, Weaviate Cloud, Qdrant Cloud), auth SaaS (Clerk, Auth0, Firebase Auth, Supabase Auth), hosting (Vercel Pro, Netlify Pro, Railway, Render), monitoring (Sentry paid, DataDog, New Relic)
- Onay kaydı olmayan ücretli LLM sağlayıcı kullanımı (yalnızca kayıtlı LLM çıkarımı istisnası geçerlidir)
- Kullanım-bazlı ücretlendirme (LLM çıkarımı hariç)

### Zorunlu Yerel/Ücretsiz Stack
| Katman | Araç | Lisans |
|--------|------|--------|
| LLM | DeepSeek API (onaylı istisna — yerel LLM yok) | — |
| Embedding | sentence-transformers + bge-m3 | MIT |
| Vektör DB | LanceDB (embedded) | Apache-2.0 |
| Veritabanı | SQLite | Public Domain |
| PDF | pymupdf (kişisel yerel kullanım; dağıtımda pdfplumber) | AGPL-3.0 (pdfplumber MIT) |
| PPTX→PDF | LibreOffice headless | MPL-2.0 |
| Hosting | Localhost (yerel) / GitHub Pages (statik, opsiyonel) | — |

### Denetim Prosedürü
1. Tüm config dosyalarını tara (`package.json`, `pyproject.toml`, `requirements.txt`, `uv.lock`)
2. Her servis için fiyatlandırma/lisans sayfasını kontrol et
3. Ücretsiz tier limiti production'ı blokluyorsa → alternatif bul
4. Yol haritasını (bu dosya, Bölüm 2.1/7) migration notlarıyla güncelle → Bölüm 15'e işle
5. Alternatifin spike task ile çalıştığını doğrula
6. **Maliyet gözetimi:** `generation_logs`'u periyodik denetle; token israfı tespit ederse prompt optimizasyonu başlat ve Ana Ajan'a raporla

---

## 8. Güvenlik & Gizlilik

- **Hesap yok, telemetri yok, analytics yok.**
- **Tüm veri yerel:** SQLite + file store + LanceDB (uygulama veri dizininde: `data/`).
- **API'ye giden veri:** Not/quiz üretimi ve puanlama sırasında ilgili materyal chunk metinleri DeepSeek API'ye gönderilir. Bu, kullanıcının "kendi API anahtarı" kararının doğal sonucudur; kullanıcı Ayarlar'da bilgilendirilir. Gönderilen veri yalnızca çıkarım için gerekli chunk'larla sınırlı tutulur (gereksiz içerik gönderilmez).
- **API anahtarı:** `settings` tablosunda (yerel) veya geliştirmede `.env`'de tutulur; **asla commit edilmez**, log'a yazılmaz, hata mesajlarında görünmez. Gitleaks pre-commit hook + Güvenlik Denetim Ajanı kontrolü.
- **Ağ:** Uygulama çalışırken yalnızca DeepSeek API'ye gider; embedding **kesinlikle yereldir** — uzak embedding API'sine (Hugging Face Inference dahil) düşülmez; model kurulamazsa iş başarısız işaretlenir ve kullanıcıya kurulum talimatı gösterilir.
- **Yedekleme:** `data/` dizini taşınabilir; tüm kullanıcı verisi bu dizindedir.

---

## 9. Riskler & Azaltımlar

| Risk | Olasılık | Etki | Azaltım |
|------|----------|------|---------|
| API kesintisi / 429 / kota aşımı | Orta | Yüksek | Backoff + circuit breaker; iş durumu kaydı; kullanıcıya net mesaj; tamamlanan kısımlar korunur |
| API'ye veri gönderimi (gizlilik) | Kesin | Orta | Bölüm 8 politikası; yalnızca gerekli chunk'lar; kullanıcı bilgilendirmesi; yerel LLM yolu kullanıcı kararıyla kapalı |
| Output token limiti (50 soru / uzun not) | Kesin (önlenmezse) | Yüksek | Batch üretim (5–10 soru) + konu bazlı map-reduce; batch başına JSON şema doğrulama |
| PDF çıkarımı taranmış kitaplarda başarısız | Orta | Orta | pymupdf `likely_scanned_pages` tespiti → marker-pdf OCR; kullanıcıya ilerleme |
| LibreOffice yok → PPTX render edilemez | Orta | Düşük | Pop-up metin alıntısı fallback; kurulum kılavuzunda isteğe bağlı adım olarak yazılır |
| Vektör arama ilgili chunk'ı kaçırır | Orta | Yüksek | Hibrit arama (vektör + konu terimi keyword boost); chunk boyutu/overlap tuning; Değerlendirme Ajanı precision/recall ölçümü |
| Atıf eşlemesi bozulur (chunk → page/slide) | Düşük | Yüksek | Chunk başına kesin metadata; her üretimde atıf doğrulama adımı; %80+ coverage kapısı |
| Quiz üretimi halüsinasyon | Orta | Yüksek | Sıkı prompt: "SADECE sağlanan context kullan"; atıfsız soru yasağı; doğrulama; sıcaklık 0.1 |
| Açık uçlu puanlama tutarsız | Orta | Orta | Rubrik-enforced JSON; few-shot örnekler; güven kontrolü + yeniden değerlendirme; Değerlendirme Ajanı tutarlılık ölçümü (hedef ±1 puan) |
| Maliyet kontrolsüz artar | Düşük | Orta | `generation_logs` + Ücretsizlik Ajanı maliyet bekçiliği; prompt verimliliği denetimi |

---

## 10. Açık Sorular

1. ~~Desktop vs Web-first?~~ **ÇÖZÜLDÜ:** Localhost web uygulaması (kullanıcı kararı, bu oturum).
2. ~~Türkçe dil desteği?~~ **ÇÖZÜLDÜ:** Tüm UI ve prompt'lar Türkçe.
3. ~~LLM çalışma zamanı?~~ **ÇÖZÜLDÜ:** Yerel LLM çalıştırılmayacak (kullanıcı kararı); LLM gerektiren görevlerde ücretli API kullanımına izin — birincil sağlayıcı: DeepSeek API. Alternatif OpenAI uyumlu sağlayıcılar yalnızca kullanıcı onayıyla (Ücretsizlik Ajanı kaydıyla).
4. **Kullanıcı auth / çoklu cihaz?** Local-only (tek kullanıcı, auth yok) korunur. **v2 kararı (Bölüm 17):** bulut sync hesap/telemetri yasağıyla çelişir — yerel karşılığı dönem arşivi export/import; gerçek bulut sync gelecekte kullanıcı kararıyla feature-flag arkasında.
5. **Anki/PDF/Markdown export formatı?** **v2 kararı:** V2.3'te uygulanır (MD + Anki `.apkg` stdlib ile + CSV; PDF not export'u zaten var — yol haritası 5.7/9).
6. **Mobil companion?** **v2 kararı:** native yerine PWA + aynı ağdan erişim (V2.8); veri yine bilgisayarda kalır.

---

## 11. Geliştirme Komutları

```bash
# Backend
cd apps/backend && uv run uvicorn src.main:app --reload --port 8000

# Frontend (geliştirme)
cd apps/frontend && pnpm run dev        # http://localhost:5173 → proxy:8000

# Testler
cd apps/backend && uv run pytest -v
cd apps/frontend && pnpm test

# Lint & Tip
cd apps/backend && uv run ruff check . && uv run pyright
cd apps/frontend && pnpm run lint && pnpm run typecheck

# Güvenlik
cd apps/backend && uv run bandit -r src && uv run pip-audit
cd apps/frontend && pnpm audit
gitleaks detect --source .             # her commit öncesi

# Embedding modeli (bir kez, ücretsiz)
# sentence-transformers ilk kullanımda modeli otomatik indirir (HF Hub)
```

**DSH pratiği (Windows):** Uzun süreçler (uvicorn, vite, test koşuları) `pwsh`/`bash` + `run_in_background` ile başlatılır; loglar `job_output` ile okunur, `job_kill` ile durdurulur (force-kill `exit code 1` olarak raporlanır — interruption sayılır). Alt süreç çıktısı named-pipe üzerinden yakalanamaz (EPERM) — `stdio: inherit/ignore` kullanılır. Sandbox reddi (`[sandbox: file access denied ...]`) politika reddidir: komut başka yoldan tekrarlanmaz; yalnızca gerçek reddin ardından aynı komut bir kez, en dar geniş modla (`sandbox_permissions`) + gerekçeyle talep edilebilir. Ayrıntı: `SİSTEM_YETENEKLERİ.md` Bölüm 3–4.

---

## 12. Kalite Kapıları (Kalite Kontrol Ajanı tarafından)

| Kontrol | Araç | Geçme Kriteri |
|---------|------|---------------|
| Unit testler | pytest / vitest | %100 geçiş, flaky yok |
| Lint temiz | ruff / eslint | 0 hata, 0 uyarı |
| Tipler temiz | pyright / tsc | 0 hata |
| Güvenlik tarama | bandit / pip-audit / pnpm audit | 0 high/critical |
| Sırlar tarama | gitleaks / trufflehog | 0 sızıntı (anahtar asla commit'te) |
| Atıflar geçerli | atıf doğrulama adımı (`06-atif-sistemi.md`) | 0 çözümsüz atıf, %80+ coverage |
| Quiz halüsinasyonu | atıf denetimi | Her soru geçerli chunk'a atıflı; atıfsız soru = fail |
| Şema geçerli | JSON Schema | Tüm AI çıktısı validate |
| Maliyet log'u | generation_logs | Her LLM çağrısı log'lu; anormal artış raporlanır |
| Regresyon | Diff vs baseline | Sadece beklenen değişiklikler |
| Coverage | pytest-cov / vitest coverage | Backend %90, Frontend %85 |
| RAG kalitesi | Değerlendirme Ajanı | Precision/recall hedefleri faz başında belirlenir ve raporlanır |
| Erişilebilirlik | axe-core | WCAG 2.1 AA |
| Tasarım token | stil denetimi | Hardcoded renk/spacing yok (`07-stil-rehberi.md`) |
| Chat atıf zorunluluğu | `chat_service` doğrulaması (testli) | Yanıttaki her `[n]` verilen kaynaklardan; ihlal = ret/tek üretim (Yetenek 10) |
| SM-2 determinizmi | `srs.py` saf fonksiyon testleri | Aynı girdi → aynı ease/interval/due; interval tavanı 365 (Yetenek 09) |
| Export geçerliliği | apkg açma doğrulaması + arşiv round-trip testi | `.apkg` Anki'de açılır; arşiv export→import veri kaybı 0 (Yetenek 12) |
| Medya boş çıktı | extractor testleri (mock'lu) | Boş transkript/OCR = iş failed + Türkçe hata; sessiz atlama yok (Yetenek 11) |
| Migration güvenliği | `test_migrations.py` | Eski kurulumdan yükseltmede veri birebir korunur; init_db idempotent |

> **Faz uygulanabilirliği:** Unit/lint/tip/güvenlik/sır/coverage kapıları her fazda geçerlidir. Atıf, quiz halüsinasyonu, şema ve RAG kalitesi kapıları Faz 3'ten itibaren (üretim hatları mevcutken) uygulanır; erken fazlarda ölçülecek çıktısı olmayan kapı "uygulanamaz" işaretlenir ve blokaj oluşturmaz.
>
> **Kapı sahipliği:** Güvenlik ve sır tarama kapılarını Güvenlik Denetim Ajanı yürütür; atıf/quiz/RAG kapılarının ölçümlerini Değerlendirme Ajanı üretir; Kalite Kontrol Ajanı tüm kapıların kanıt tüketicisidir ve GEÇTİ/KALDI kararını verir.

---

## 13. Genişletilebilirlik Noktaları

1. **Yeni Quiz Tipleri:** `04-overall-quiz-uretimi.md` prompt + şemaya ekle
2. **Yeni Export Formatları:** export_service.py (Anki, PDF, MD) — Faz 6 sonrası
3. **Arama & Komut Paleti (Cmd+K):** Faz 6 sonrası
4. **Yeni Diller:** Prompt dili ve embedding modeli değiştirilir (bge-m3 çok dilli)
5. **Yeni Dosya Tipleri:** Indexer'a extractor ekle (DOCX, EPUB)
6. **Alternatif LLM Sağlayıcı:** LLM sağlayıcı arayüzü arkasında DeepSeek ↔ OpenAI uyumlu başka bir sağlayıcıya geçiş (Ayarlar'dan; kullanıcı onayı + istisna kaydı şart). Yerel LLM (Ollama/GGUF) kullanıcı kararıyla kapsam dışıdır.
7. **Opsiyonel Bulut Sync:** Feature flag arkasında sync engine (çok cihaz)

---

## 14. Dosya Yapısı

```
StuHub DS/
├── PROJE_YOL_HARITASI.md     ← BU BELGE (belkemiği)
├── SİSTEM_YETENEKLERİ.md     ← DSH yetenek kataloğu + ajan kullanım rehberi (prompt)
├── DSH_ARASTIRMA_RAPORU.md   ← DSH checkout'unun tam kazı raporu (kaynak dokümantasyon)
├── NİŞ_ANALİZİ_RAPORU.md     ← v2 kaynağı (30 uygulama kataloğu + 16 öneri; Bölüm 17)
├── KULLANIM.md               ← kullanıcı kılavuzu
├── AJANLAR/                  ← Ajan prompt dosyaları (20 adet, Bölüm 4.1)
├── YETENEKLER/               ← Yetenek/capability dokümanları (15 adet, Bölüm 5)
├── apps/
│   ├── frontend/              # React + TS + Vite
│   │   ├── src/
│   │   │   ├── pages/         (TermsPage, TermDetailPage, CoursePage, NotebookPage, SettingsPage)
│   │   │   ├── components/    (NoteViewer, CitationPopup, QuizPlayer, OverallQuizPlayer, ...)
│   │   │   ├── api/           (client.ts, sse.ts, ...)
│   │   │   ├── stores/        (appStore, generationStore)
│   │   │   └── lib/           (utils.ts, useAnimatedProgress.ts)
│   │   └── package.json
│   └── backend/               # FastAPI + Python
│       ├── src/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── db.py          # init_db + v2 migration runner (schema_migrations)
│       │   ├── routers/       (terms, courses, chapters, slides, materials, indexing,
│       │   │                   notes, quizzes, overall, settings)
│       │   ├── services/      (pdf_service, slides_service, chunking, embed_service,
│       │   │                   vector_store, retrieval, indexer, llm_service,
│       │   │                   note_generator, quiz_generator, overall_generator,
│       │   │                   essay_grader, export_service, fib_utils)
│       │   ├── prompts/       (note_prompts, quiz_prompts, overall_prompts)
│       │   └── workers/       (indexer.py)
│       ├── sql/               (schema.sql, migrations/)
│       ├── tests/
│       └── pyproject.toml
├── data/                      # Uygulama verisi (SQLite, LanceDB, materials/) — git'e GİRMEZ
├── .tools/                    # Proje-yerel araçlar (uv-python, gitleaks) — git'e GİRMEZ
├── .github/workflows/         (ci.yml)
├── .gitignore                 # data/, .env dahil
└── README.md
```

---

## 15. Sürüm Geçmişi

| Tarih | Sürüm | Değişiklik |
|-------|-------|------------|
| 2026-08-12 | 1.0 | İlk resmi belkemiği belgesi (yerel `.hermes/plans` kaynağı): Tauri masaüstü, yerel llama.cpp, 12 ajan, 8 haftalık faz planı |
| (bu oturum) | 2.0 | StuHub DS workspace'ine taşındı. **Karar deltaları:** platform → localhost web (Tauri kaldırıldı); LLM → kullanıcının DeepSeek API anahtarı (llama.cpp kaldırıldı, Model Yönetimi → API Yapılandırması); embedding → sentence-transformers çok dilli; güvenlik bölümü revize edildi; Açık Sorular #1-#3 çözüldü |
| (bu oturum) | 3.0 | **Mimari denetim raporu (17 düzeltme) uygulandı:** PPTX→PDF render pipeline; çok dilli embedding; batch quiz üretimi; map-reduce not üretimi; `slides` tablosu; Ayarlar sayfası + `generation_logs` + maliyet bekçisi; Faz 6 kapsamı (fazlalıklar genişletilebilirliğe taşındı); puanlama güven kontrolü; FIB normalizasyonu; Değerlendirme Ajanı (13. ajan); hibrit retrieval somutlaştırıldı; SSE streaming; `models` tablosu kaldırıldı; atıf doğrulama somutlaştırıldı; Effort kuralı (Ana Ajan V4 Pro sabit, diğerleri V4 Flash + yükseltme); Başlatma Protokolü eklendi |
| (bu oturum) | 4.0 | **DeepSeek Harness (DSH) tam kazısı entegre edildi.** Yerel DSH checkout'u (developer preview, 0.1.0-rc.5) derinlemesine araştırıldı: Cordis mimarisi, profil/bundle katmanları, 44 araçlık katalog, config/persistence katalogları, 50+ alt sistem, 47 paket grubu, CLI/Web/Python SDK/native/örnekler. Çıktılar: (1) `DSH_ARASTIRMA_RAPORU.md` — tam kazı raporu; (2) `SİSTEM_YETENEKLERİ.md` — araştırmanın ajan promptuna dönüştürülmüş hali (araç kataloğu, sandbox/onay kuralları, orkestrasyon rehberi, StuHub DS eşlemesi). Session başlangıç akışına (Bölüm 4.5) ve Bölüm 5/14'e referanslar işlendi |
| (bu oturum) | 4.1 | **DSH kataloğuna göre ince ayar:** Bölüm 0'a geliştirme katmanı sınırı (ürün kodu DSH plugin'i değildir) + ikinci zorunlu okuma notu; Bölüm 2.1'e DSH satırı; 4.2'ye Settings→Models notu; 4.5'e delegasyonda dosya yolu + `read` stratejisi (context optimizasyonu) ve `job_output` toplama kuralı; Başlatma Protokolü'ne goal semantiği (create/resume/complete) + `ask_user_question` yalnız-kök-ajan kuralı + `ralph` sınırı; Bölüm 11'e Windows süreç/sandbox pratikleri |
| (bu oturum) | 4.2 | **Ücretsizlik istisnası genişletildi (kullanıcı kararı):** yerel LLM çalıştırılmayacak; LLM gerektiren tüm görevlerde ücretli API kullanımına izin verilir (birincil: DeepSeek API; alternatif OpenAI uyumlu sağlayıcı yalnızca kullanıcı onayıyla). Yerel embedding modeli LLM sayılmaz, yerelde kalır; Bölüm 13'teki yerel model uzantısı kaldırıldı, alternatif sağlayıcı geçişine çevrildi |
| (bu oturum) | 4.3 | **Başlangıç öncesi denetim düzeltmeleri:** uzak embedding fallback'i (HF Inference) kaldırıldı — embedding kesinlikle yerel (gizlilik sözleşmesi); FIB feedback şeması tamamlandı + LLM hakem yedeği kaldırıldı (üretim anında genişletilmiş kabul listesi, interaksiyonda LLM çağrısı yok); batch/üst zarf JSON şemaları tanımlandı (03/04); marker-pdf lisansı GPL-3.0 olarak düzeltildi; `quizzes.type` kaldırıldı; puanlama riskindeki tanımsız "flag/override" çıkarıldı; Faz 0–2 sahipliği için **Frontend Geliştirici + Backend Geliştirici ajanları eklendi (toplam 15 ajan)** |
| (bu oturum) | 5.0 | **Faz 0 tamamlandı (checkpoint commit).** Ön koşullar: uv 0.12.4 + Python 3.12.13 workspace-managed (`.tools/uv-python`, `.tools/uv-cache`), gitleaks 8.30.1 pre-commit hook (`.githooks/`, `core.hooksPath`), git + `.gitignore`. Monorepo: `apps/backend` (FastAPI 0.141 + SQLite/aiosqlite; `sql/schema.sql` v4.3'e uyumlu — `quizzes.type` yok; config/db/main; `GET /health`, `/api/settings` maskeli anahtar, `/api/terms` iskeleti; 5 pytest geçti) + `apps/frontend` (Vite 6 + React 18 + TS strict + Tailwind v4 token tabanlı tema + Zustand + react-router 7; proxy 5173→8000; sağlık banner'ı; eslint/tsc/vitest/build yeşil; `npm audit` 0 yüksek/kritik). CI: GitHub Actions (gitleaks + backend ruff/pyright/pytest + frontend lint/typecheck/test/build). Kök: `.env.example`, `README.md`. Kalite kapıları Bölüm 12 (bu fazda uygulanabilir olanlar): unit/lint/tip/sır/coverage — geçti; atıf/quiz/RAG kapıları uygulanamaz (Faz 3+) |
| (bu oturum) | 5.1 | **Faz 1 tamamlandı (checkpoint commit).** 1.1 Dönem CRUD (GET/POST/PUT/DELETE `/api/terms` + `GET /{id}`) + TermsPage (liste/oluştur/sil, TermCard/TermForm); 1.2 Ders CRUD (`/api/terms/{id}/courses`, `/api/courses/{id}`) + materyal yükleme (multipart, tür/uzantı doğrulama, `data/materials/{course_id}/` UUID önekli depolama, dosya ile birlikte silme); 1.3 Ders Notebook Landing (CoursePage: chapter listesi + "Yeni Chapter Ekle" [chapter minimal CRUD — guide slides Faz 2.1] + materyal bölümü); 1.4 Ayarlar sayfası (maskeli API anahtarı + model seçimi → `/api/settings`). Frontend rotalar: `/`, `/donemler/:termId`, `/dersler/:courseId`, `/dersler/:courseId/defter/:chapterId`, `/ayarlar`. Testler: backend 16 pytest; frontend 3 vitest; E2E (proxy üzerinden dönem→ders→chapter→materyal→cascade temizlik) doğrulandı; `npm audit` 0 |
| (bu oturum) | 5.2 | **Faz 2 tamamlandı (checkpoint commit).** 2.1 Guide slides: `POST/GET /api/chapters/{id}/slides` + `DELETE /api/slides/{id}` — PDF (pymupdf) / PPTX (python-pptx, başlık+gövde+tablo+grup+notlar) çıkarımı, `slides` tablosu dolgusu, LibreOffice render yoksa metin fallback'i; NotebookPage (chapter detay: slide yükleme/liste/metin önizleme). 2.2 Vektör indeksleme: `services/` (pdf_service, slides_service, chunking [~1200 token, ~100 token overlap], embed_service [sentence-transformers + bge-m3, yerel, uzak API YASAK], vector_store [LanceDB `course_{id}_chunks`, idempotent upsert], indexer) + `workers/indexer.py` (arka plan döngü, stale kurtarma, atomik claim) + `POST /api/materials/{id}/index` + `GET /api/courses/{id}/indexing-jobs`; CoursePage materyal satırında durum/ilerleme/İndeksle butonu; materyal silme vektör temizliği. Bağımlılıklar: pymupdf 1.28, python-pptx 1.0, lancedb 0.37, sentence-transformers 5.7 + torch CPU. Testler: backend 33 pytest (chunking/pdf/pptx/slides-router/indexing-mock'lu); E2E GERÇEK bge-m3 ile doğrulandı (3 sayfa → 3 chunk, 1024-boyut, sayfa metadata, iş `done`); bandit 0, pip-audit 0, gitleaks temiz, npm audit 0 |
| (bu oturum) | 5.3 | **Faz 3 tamamlandı (checkpoint commit).** 3.1 Not üretim hattı: `services/llm_service.py` (DeepSeek/openai SDK — stream, üstel backoff, circuit breaker, `generation_logs` maliyet kaydı, Türkçe hata mesajları), `services/retrieval.py` (hibrit: 0.7·vektör + 0.3·keyword, sayfa komşusu, `material_id` taşıma), `services/note_generator.py` (konu çıkarımı → konu başına map-reduce stream üretim → kapsama doğrulama [max 3 iterasyon, yeniden üretim] → atıf doğrulama [fuzzy + LLM onay, çözümsüz atıf = hata] → kayıt), `prompts/note_prompts.py`. 3.2 SSE: `POST /api/chapters/{id}/notes` (`text/event-stream`; status/delta/done/error olayları; canlı doğrulandı — anahtar yoksa "API anahtarı ayarlanmadı" error olayı). 3.3 Frontend: `api/notes.ts` (fetch+SSE okuyucu), NoteViewer (react-markdown, bölüm bazlı atıf haritası, tıklanabilir [n]), CitationPopup (modal, Esc/odak, alıntı + çözümlenmiş chunk metni), NotebookPage'de üretim ilerlemesi (durum metni + progress bar + canlı önizleme). Ek: `GET /api/chapters/{id}/notes`, `GET /api/citations/{chunk_id}`, `GET /api/materials/{id}/file` (Range destekli). Bağımlılık: openai 3.0, react-markdown, pdfjs-dist. Testler: backend 53 pytest (llm_service mock istemci: retry/breaker/json; retrieval; note_generator: tam akış/kapsama/atıf hatası/log); frontend 5 vitest (NoteViewer atıf+pop-up); bandit 0, pip-audit 0, npm audit 0. **Not:** canlı üretim için `DEEPSEEK_API_KEY` (`.env` ya da Ayarlar) gerekir — anahtarsız tüm akışlar Türkçe hata ile güvenli kapanır |
| (bu oturum) | 5.4 | **Faz 4 tamamlandı (checkpoint commit).** 4.1 Quiz üretimi: `services/quiz_generator.py` (not bölümleme [esnek başlık↔konu eşleşmesi], konu başına 5 MCQ zarf [JSON şema, çeldirici/atıf/denge denetimi], deterministik yeniden dengeleme, atıf zenginleştirme; izinli atıf yoksa atıfsız soru kabulü), `prompts/quiz_prompts.py`; `POST /api/chapters/{id}/quiz` (SSE). 4.2 Anında feedback: `POST /api/quizzes/{id}/attempts` (interaksiyonda LLM çağrısı YOK — feedback üretim anında gömülü; skor + doğru/yanlış + açıklama + atıf), `GET /api/chapters/{id}/quiz`; QuizPlayer (tek soru/ekran, tam genişlik seçenekler, yeşil/kırmızı feedback kartı, atıf butonları + CitationPopup, ilerleme çubuğu, özet + tekrar). Başlık uyumu düzeltmeleri: not prompt'una sabit "### {topic}" başlık kuralı + `topic_matches` esnek eşleşmesi (backend + NoteViewer). Testler: backend 62 pytest; frontend 7 vitest; **GERÇEK canlı E2E (DeepSeek + bge-m3): kitap indeksleme → guide slides → not (2 konu, atıflı) → quiz (10 soru) → deneme 10/10 + yanlış-feedback doğrulaması — 55 sn, ~31k token (`generation_logs` ile izlendi)**; bandit 0, pip-audit 0, npm audit 0 |
| (bu oturum) | 5.5 | **Faz 5 tamamlandı (checkpoint commit).** 5.1 Genel quiz üretimi: `services/overall_generator.py` (dersin tüm chapter notları → konu havuzu + stratifikasyon; 9 batch: MCQ 3×5 + TF 8+7 + FIB 3×5 + açık uçlu 5; zarf şeması doğrulama, atıf _gid havuzu eşleme, TF 7-8 doğru dengesi + yeniden üretim, 15/15/15/5 dağılım doğrulaması, seed'li karıştırma, `answer_key` ayrı saklama), `prompts/overall_prompts.py`; `POST /api/courses/{id}/overall-quiz` (SSE, batch başına ilerleme). 5.2 FIB: `services/fib_utils.py` (Türkçe normalizasyon — İ→i, I→ı, i/ı korunur; kabul listesi deterministik eşleşme, interaksiyonda LLM YOK). 5.3 Açık uçlu puanlama: `services/essay_grader.py` (rubrik 0-10, correct/missing/incorrect/unnecessary + gerekçe + atıflı ideal cevap, güven kontrolü + yeniden değerlendirme, boş cevap deterministik 0); `POST /api/overall-quizzes/{id}/attempts` (mcq/tf/fib anında + essay LLM; skor 50/50 kapalı+açık); `GET /api/courses/{id}/overall-quiz` **answer_key'siz**. Frontend: `api/overall.ts`, OverallQuizPlayer (50 soru, 4 tip, karışık, anında feedback, açık uçlu özet analizi + ideal cevap), CoursePage genel quiz bölümü. Testler: backend 75 pytest; frontend 8 vitest; **GERÇEK canlı E2E: 2 chapter notu → 50 soru (15/15/15/5 tam) → deneme 45/45 kapalı + açık uçlu puanlama + answer_key sızıntı kontrolü — 206 sn**; bandit 0, pip-audit 0, npm audit 0 |
| (bu oturum) | 5.6 | **Faz 6 tamamlandı — ÜRÜN TESLİM EDİLDİ (v1.0.0).** 6.1 Stil cilası: hardcoded renk denetimi temiz (yalnızca `theme.css` tokenları), Türkçe mikro-metinler. 6.2 Kalite kapıları tam geçiş: backend 75 pytest + ruff/pyright 0 + bandit 0 + pip-audit 0; frontend 8 vitest + eslint/tsc 0 + build ✓ + npm audit 0; gitleaks tam tarama 0 sızıntı. 6.3 Kabul akışı: not→bölüm quizi→genel quiz→deneme canlı doğrulandı (kullanıcı son kabul testini `KULLANIM.md` ile yapar). 6.4 Dokümantasyon: `KULLANIM.md` (kullanım kılavuzu) + README güncellendi. 6.5 Pre-release güvenlik denetimi: anahtar sızıntısı yok (grep + gitleaks), `.env` ignore'lu, quiz `answer_key` gizliliği testli, üretim modunda API anahtarı maskeli. **Üretim modu:** FastAPI inşa edilmiş SPA'yi tek adreste sunar (`GET /` + SPA fallback + `/assets`; doğrulandı — kök HTML, `/donemler/1` fallback, health 1.0.0). Başlangıç hedefi tamamlandı: yerel, atıflı, Türkçe, ücretsiz-arac sözleşmesine uygun StuHub 1.0 |
| (bu oturum) | 5.7 | **Kullanıcı geri bildirim turu (10 madde).** 1) PDF yükleme: kök neden demo kitabının 0 bayt olması; akışkan (chunk) yükleme + net Türkçe boş-dosya hatası (geçerli 5 MB PDF doğrulandı). 2) Slaytlar artık önizleyiciyle teker teker (SlidePreview: ok tuşları + sayfa atlamaları), tüm sayfa listesi değil. 3) Kitap/materyal önizleme: Önizle butonu → iframe PDF penceresi (Range destekli `/file`). 4) Quiz üretimi sağlamlaştırıldı: 3 deneme + ayrıntılı hata mesajı. 5) Not bitince bölüm quizi OTOMATİK üretilir, notun altında görünür. 6) Animasyonlu progress bar (`useAnimatedProgress`: %1 adımlarla) — not/quiz/genel quiz/indeksleme tümünde. 7) Genel quiz açık uçlu soru görünümü düzeltildi. 8) Quiz bitişi → açılır-kapanır "Sorular ve cevaplar" önizleme penceresi (her iki oynatıcı). 9) Not PDF export (`GET /api/notes/{id}/export`, markdown→pymupdf, Türkçe glifli) + "PDF İndir" butonu. 10) Notlar açılır-kapanır panelde. Testler: backend 77 pytest (boş dosya + export); frontend 8 vitest; ruff/pyright/eslint/tsc 0; canlı doğrulama (boş→422 net mesaj, geçerli PDF→201) |
| (bu oturum) | 5.8 | **Kullanıcı geri bildirim turu 2 (8 madde).** 1) Chapter slaytları: ders sayfası gibi şık önizleyici (kart görünümü, sayfa atlama) + "Sunumu aç" → PDF penceresi (`GET /api/materials/{id}`). 2) Üretimler sayfadan bağımsız KÜRESEL: `stores/generationStore` + App genelinde ilerleme paneli — sayfa değişse bile üretim sürer, her sayfada görünür. 3) Quizler DAİMA kaydedilir: geçmiş listesi (`GET /api/chapters/{id}/quizzes`, `GET /api/courses/{id}/overall-quizzes`) + silme uçları; "yenile" kaldırıldı, "Yeni Oluştur" her zaman ekler. 4) PDF export görsel hatası: kelime bazlı satır sarma (taşma yok, doğrulandı) + kalın başlık fontu. 5) Quiz üretimi ASLA BAŞARISIZ OLMAZ: yumuşak geçiş (şema-geçerli sorular kabul, atıf self-heal, denge), sorunlu konu/batch uyarıyla atlanır, içerik daima teslim edilir (`warnings` listesi). 6) Denemeler KALICI: oynatıcılar kayıtlı denemeyi geri yükler (bitmiş quiz yeniden başlamaz), "Yeniden çöz" + "Cevapları sil" + "Quiz'i sil" (`GET /api/quizzes/{id}/attempts`, DELETE uçları). 7) Önizlemede soru + TÜM seçenekler (seçilen/doğru işaretli); genel quiz sonuçlarına options/correct_index/statement/user_answer eklendi. 8) Dosya adları UUID öneksiz özgün adla gösterilir (`display_name`). Testler: backend 77 pytest + frontend 8 vitest; canlı doğrulama (display_name, geçmiş uçları, 404'ler) |
| (bu oturum) | 5.9 | **Kullanıcı geri bildirim turu 3 (3 madde).** 1) Genel quiz **55 soru: 20 çoktan seçmeli + 15 doğru-yanlış + 15 boşluk doldurma + 5 açık uçlu**; puanlama: kapalı 50×1 + açık 5×10 = **100 puan** (`overall_generator.BATCH_PLAN` 4×5 MCQ, `overall.py` skor = closed_correct + open_total; CoursePage/KULLANIM/README metinleri güncellendi). 2) Bölüm quizi JSON hatası KÖK NEDEN çözümü: `llm_service.chat_json` → `_extract_json` (``` fence'lerini sıyırır, ilk `{`…son `}` ayıklama) + JSON hatasında 3'e kadar yeniden deneme ("geçerli JSON döndür" notu ile); batch/topic düzeyinde `LLMError` yutulur, sorunlu batch uyarıyla atlanır, kullanıcıya hata YÜZEYE ÇIKMAZ — içerik daima teslim edilir. 3) Genel quiz sonuçları TAM GÖSTERİM: her soru satır içi açık (kapalı `<details>` kaldırıldı) — tam soru + tüm seçenekler (doğru ✓ / senin cevabın ← işaretli) + TF doğru/yanlış cevabın + FIB kabul edilen cevaplar + açık uçlu puan kırılımı (doğru/eksik/yanlış/gereksiz + ideal cevap) + **doğruysa "neden doğru", yanlışsa öğretici açıklama**; bölüm quizi önizlemesinde de doğru cevaplara açıklama eklendi. Testler: backend 79 pytest (20-MCQ sayıları, skor 100 modeli, `_extract_json` + garbage→valid kurtarma); frontend 8 vitest + build ✓; ruff/pyright/eslint/tsc 0 |
| (bu oturum) | 5.10 | **Faz V2.0 tamamlandı (checkpoint commit) — Niş Analizi Entegrasyonu başladı.** `NİŞ_ANALİZİ_RAPORU.md` (30 uygulama kataloğu + 16 öneri) repoya alındı; yol haritasına Bölüm 17 (v2 sözleşmesi) eklendi, Bölüm 3/4.1/4.3/4.4/5/10/14/16 güncellendi. Backend: migration runner (`schema_migrations`; `sql/migrations/0001_materials_tipleri.sql` + `0002_yeni_tablolar.sql` — veri koruyan, idempotent), 7 yeni tablo (`flashcard_sets`, `card_reviews`, `chat_messages`, `study_guides`, `essay_submissions`, `activity_log`, `schema_migrations`), `indexing_jobs.kind`, extractor registry refactor'u (v1 davranışı birebir korundu), config v2 alanları (whisper_model/ocr_enabled/not_dili/daily_goal) + `.env.example`. Ajan kataloğu 15→20 (`15-flashcard`, `16-materyal-sor`, `17-medya-alim`, `18-ihracat`, `19-calisma-rehberi` yeni; 00/04/05/08 güncellendi), yetenek kataloğu 8→15 (09–15 yeni; 05/06/08 güncellendi). Bağımlılıklar: yt-dlp (Unlicense), faster-whisper (MIT), rapidocr-onnxruntime (Apache-2.0), python-docx (MIT), vite-plugin-pwa (MIT). Kapılar: ruff/pyright 0, **pytest 82/82** (3 yeni migration testi), bandit 0, pip-audit 0, eslint/tsc 0, vitest 8/8, build ✓, npm audit 0, gitleaks temiz |
| (bu oturum) | 5.11 | **Faz V2.1 tamamlandı (checkpoint commit) — Materyale Sor.** Backend: `prompts/chat_prompts.py` (DIRECT/SOCRATIC/QUIZ), `services/chat_service.py` (hibrit retrieval → numaralı kaynaklar → SSE; `[n]` atıf doğrulaması + `retry` olayı + tek yeniden üretim; boş retrieval'da LLM'siz rehber mesaj; `chat_messages` kaydı + `activity_log` ON CONFLICT UPSERT; `generation_logs` kind=chat), `routers/chat.py` (POST SSE/GET/DELETE `/api/courses/{id}/chat`). Frontend: `api/chat.ts` (SSE okuyucu + retry olayı), `ChatPanel` (atıf çipli react-markdown, CitationPopup preloadedText, mod seçici, geçmiş/geçmiş temizleme), CoursePage "Materyale Sor" bölümü. **V2.3 backend önden teslim:** `anki_export.py` (stdlib apkg + açma doğrulaması + CSV BOM), `archive_service.py` (manifest v1 export/import — kimlik yeniden eşleme, çakışma eki, ekleme-only; B608'siz sabit SQL), `routers/exports.py` (apkg/csv/md + arşiv uçları), not export'u format param'lı (pdf/md), `srs.py` (SM-2 saf fonksiyon — V2.2 çekirdeği). Kapılar: ruff/pyright 0, **pytest 117/117** (12 chat + 5 anki + 5 arşiv + 13 srs), bandit 0, pip-audit 0, eslint/tsc 0, **vitest 11/11**, build ✓, npm audit 0, gitleaks temiz |
| (bu oturum) | 5.12 | **Faz V2.2 + V2.4 + V2.6 tamamlandı (checkpoint commit).** V2.2: `flashcard_generator` (konu başına map-reduce kart üretimi — not+quiz'den qa/term, atıf zorunlu, dedup, asla başarısız olma) + `routers/flashcards.py` (SSE üretim, due kuyruğu [vadesi geçen önce], SM-2 review UPSERT, activity_log) + FlashcardPlayer (flip + Again/Hard/Good/Easy + atıf çipleri) + generationStore 'flashcards'. V2.4: TabBar sekme hub'ları (NotebookPage: Notlar/Kartlar/Quiz; CoursePage: Genel Bakış/Genel Quiz/Materyale Sor/Bugünün Kartları), Sidebar ağacı (Dönem→Ders→Chapter, tembel yükleme), StreakRing + `GET /api/streaks` (daily_goal settings-tablo öncelikli), 3 adımlı OnboardingWizard, SettingsPage günlük hedef. V2.6: `media_extractors` paketi (youtube altyazı tr→en + faster-whisper fallback; audio STT; docx; epub stdlib; rapidocr; text; tembel import) + `chunk_segments` ([mm:ss] önekli) + `indexing_jobs.kind='transcribe'` zinciri (transkript JSON → otomatik index) + `routers/media.py` (YouTube URL + metin yapıştırma) + materials yeni tür/uzantılar + otomatik işe alma. Kapılar: ruff/pyright 0, **pytest 183/183** (10 flashcard + 21 extractor + 5 pipeline + 11 exports + 7 streak + 7 guide + 5 essay), bandit 0 (B310/B112 düzeltildi), **vitest 20/20**, lint/tsc/build ✓, npm audit 0 |

---

## 16. Faz Durumu (Checkpoint Takibi)

> Ana Ajan her faz geçişinde bu tabloyu günceller. "TAMAM" işareti, Bölüm 12 kalite kapılarının o faz kapsamında geçtiği anlamına gelir.

| Faz | Ad | Durum | Tarih | Not |
|-----|----|-------|-------|-----|
| 0 | Temeller | ✅ TAMAM | 2026-08-14 | uv+Python workspace-managed, gitleaks hook, monorepo, CI, SQLite şema (Bölüm 3), FastAPI iskeleti + /health, frontend scaffold (tema + sayfalar + sağlık banner'ı). Kapılar: ruff/pyright/pytest 5/5, eslint/tsc/vitest/build, npm audit 0 yüksek/kritik, gitleaks temiz |
| 1 | Dönem & Ders Yönetimi | ✅ TAMAM | 2026-08-14 | 1.1 Dönem CRUD + TermsPage; 1.2 Ders CRUD + PDF/PPTX yükleme (depolama); 1.3 Notebook landing (chapter minimal CRUD; guide slides Faz 2.1'de); 1.4 Ayarlar sayfası (maskeli anahtar + model). Kapılar: ruff/pyright/pytest 16/16, eslint/tsc/vitest 3/3, E2E proxy akışı, npm audit 0 |
| 2 | Chapter & Guide Slides | ✅ TAMAM | 2026-08-14 | 2.1 Guide slides yükleme/çıkarım (PDF/PPTX) + NotebookPage; 2.2 Vektör indeksleme (chunk+embed+LanceDB, indexing_jobs, arka plan worker) + CoursePage durum/ilerleme. Kapılar: ruff/pyright/pytest 33/33, bandit 0, E2E gerçek bge-m3 ile (3 chunk, 1024-dim), npm audit 0 |
| 3 | Not Oluşturma | ✅ TAMAM | 2026-08-14 | 3.1 map-reduce üretim + hibrit retrieval + kapsama/atıf doğrulama + generation_logs; 3.2 SSE streaming (canlı doğrulandı); 3.3 NoteViewer + CitationPopup. Kapılar: ruff/pyright/pytest 53/53, bandit 0, vitest 5/5, npm audit 0. Canlı üretim için API anahtarı gerekli |
| 4 | Bölüm Quiz | ✅ TAMAM | 2026-08-14 | 4.1 Konu başına 5 MCQ (atıf zorunlu, denge yeniden düzenleme ile); 4.2 Anında feedback (interaksiyonda LLM çağrısı yok) + QuizPlayer. Kapılar: pytest 62/62, vitest 7/7, bandit 0. **Canlı E2E (gerçek LLM): not→quiz→10/10 deneme** |
| 5 | Genel Quiz | ✅ TAMAM | 2026-08-14 | 5.1 50 soru (15/15/15/5, seed'li karışık, answer_key saklı); 5.2 FIB deterministik eşleşme; 5.3 açık uçlu otomatik puanlama (rubrik + güven kontrolü). Kapılar: pytest 75/75, vitest 8/8, bandit 0. **Canlı E2E: 2 not → 50 soru → deneme + essay puanlama** |
| 6 | Polish, Kalite & Teslim | ✅ TAMAM | 2026-08-14 | 6.1 Stil denetimi (bileşenlerde hardcoded renk yok, tokenlar); 6.2 Kalite kapıları tam geçiş (75 pytest + 8 vitest + tüm lint/type/audit 0); 6.3 Canlı uçtan uca kabul akışı doğrulandı (kullanıcı son testini yapar); 6.4 KULLANIM.md + README; 6.5 Güvenlik denetimi (gitleaks 0, anahtar sızıntısı yok, answer_key gizliliği testli). **Üretim modu: FastAPI inşa edilmiş SPA'yi tek adreste sunar (v1.0.0)** |
| V2.0 | v2 Mimari İskelet | ✅ TAMAM | (bu oturum) | Migration runner (schema_migrations) + 0001/0002 + yeni tablolar + extractor registry + config v2 + 5 yeni ajan (15–19) + 7 yeni yetenek (09–15) + bağımlılıklar (yt-dlp, faster-whisper, rapidocr, python-docx, vite-plugin-pwa). Kapılar: ruff/pyright 0, pytest 82/82, bandit 0, pip-audit 0, eslint/tsc 0, vitest 8/8, build ✓, npm audit 0, gitleaks temiz. v1 davranışı birebir korundu |
| V2.1 | Materyale Sor | ✅ TAMAM | (bu oturum) | `chat_service` (retrieval → numaralı kaynaklar → SSE; atıf doğrulama + retry olayı; direct/socratic/quiz; `chat_messages` + `activity_log` UPSERT) + `routers/chat.py` (POST SSE/GET/DELETE) + ChatPanel (atıf çipli, CitationPopup preloaded) + CoursePage bölümü. Kapılar: pytest 12 yeni test, vitest 3 yeni test |
| V2.2 | Flashcard + SM-2 | ✅ TAMAM (backend+frontend; commit sıradaki turda) | (bu oturum) | `flashcard_generator` (not+quiz'den konu başına map-reduce kart üretimi, atıf zorunlu + dedup + asla başarısız olma) + `routers/flashcards.py` (SSE üretim, set listesi, due kuyruğu [vadesi geçen önce], SM-2 review UPSERT + activity_log) + `srs.py` (deterministik çekirdek) + FlashcardPlayer (flip + Again/Hard/Good/Easy + atıf çipleri) + NotebookPage "Kartlar" + CoursePage "Bugünün Kartları". Kapılar: pytest 157, vitest 15 |
| V2.3 | Export + Arşiv | 🚧 SÜRÜYOR (backend) | — | Not MD/PDF, Anki `.apkg` (stdlib), CSV, dönem arşivi export/import (manifest v1) — backend servisleri + router hazır; frontend butonları V2.4 paketiyle |
| V2.4 | UI Paketi | ✅ TAMAM | (bu oturum) | NotebookPage (Notlar/Kartlar/Quiz) + CoursePage (Genel Bakış/Genel Quiz/Materyale Sor/Bugünün Kartları) sekme hub'ları (TabBar), Dönem→Ders→Chapter Sidebar ağacı (tembel yükleme), StreakRing (SVG halka + GET /api/streaks), 3 adımlı OnboardingWizard (onboarding_done bayrağı), SettingsPage günlük hedef girdisi. Kapılar: vitest 20, lint/tsc/build ✓ |
| V2.5 | Essay Değerlendirici | 🚧 SÜRÜYOR (backend hazır) | — | `essay_service` (0–100 rubrik, güven eşiği, boş metin deterministik) + `essays/grade` uçları commit'li; frontend ekranı kuyrukta |
| V2.6 | Medya Alımı | ✅ TAMAM (backend; frontend yükleme arayüzü V2.9 paketiyle) | (bu oturum) | `media_extractors` paketi (youtube [altyazı tr→en + whisper fallback], audio [faster-whisper], docx, epub [stdlib], ocr [rapidocr], text; tembel import) + `chunk_segments` ([mm:ss] önekli) + `kind='transcribe'` zinciri (transkript JSON → otomatik index) + `routers/media.py` (YouTube URL + metin yapıştırma) + materials yeni tür/uzantılar + otomatik işe alma. Kapılar: 21 extractor + 5 pipeline testi, bandit 0 |
| V2.7 | Rehber + Çok Dilli | 🚧 SÜRÜYOR (backend hazır) | — | `guide_service` (özet + DAG kavram haritası) + `/guide(s)` uçları commit'li; `not_dili` prompt entegrasyonu guide'da tamam; not/quiz promptlarına dil talimatı + frontend Rehber sekmesi kuyrukta |
| V2.8 | PWA + LAN | 🚧 SÜRÜYOR (backend hazır) | — | `/sw.js` + `/manifest.webmanifest` FastAPI rotaları hazır (SPA fallback'ten önce); vite-plugin-pwa yapılandırması + ikonlar + LAN dokümantasyonu kuyrukta |
| V2.9 | Teslim v2.0.0 | ⬜ PLANLI | — | Kalite kapıları tam turu, README/KULLANIM güncellemesi, canlı E2E, sürüm geçmişi |

---

## 17. v2 — Niş Analizi Entegrasyonu (StudyFetch/Mindgrasp + 30 Uygulama Kataloğu)

> **Kaynak:** [`NİŞ_ANALİZİ_RAPORU.md`](./NİŞ_ANALİZİ_RAPORU.md) (30 uygulama kataloğu, iki anchor derin incelemesi, 13 uygulamalık arayüz örneklemi, 16 geliştirme önerisi). Bu bölüm, raporun StuHub'a uygulanmasının sözleşmesidir; faz durumu Bölüm 16'dadır.

### 17.1 Strateji

StuHub rakiplerin zayıf olduğu yerlerde zaten güçlü: **yerel-öncelikli gizlilik (hesap/telemetri yok), üretim çıktısının kendisinde atıf derinliği, abonelik/kredi yok (BYO DeepSeek anahtarı), Türkçe**. v2, nişin standartlarına en ucuz yoldan yetişir (flashcard, chat, streak) ve raporun "bilinçli yapılmayacaklar" listesine dokunmaz.

### 17.2 Özellik → Faz Haritası

| # | Özellik | Faz | Durum | Ana bileşenler |
|---|---------|-----|-------|----------------|
| 1 | Flashcard + yerel spaced repetition (SM-2) | V2.2 | ✅ | `flashcard_sets`/`card_reviews`, `services/srs.py` + `flashcard_generator.py`, `FlashcardPlayer` |
| 2 | Materyale Sor (atıflı RAG chat) | V2.1 | ✅ | `chat_messages`, `services/chat_service.py`, `ChatPanel` (atıf çipli) |
| 3 | Çalışma modu sekmeleri (Notlar\|Kartlar\|Quiz\|Rehber) | V2.4 | ✅ | `NotebookPage`/`CoursePage` sekme hub'ları (TabBar) |
| 4 | Anki + Markdown export | V2.3 | 🟡 backend ✅ | `export_service.py` genişletme + `anki_export.py` (stdlib apkg) — frontend butonları sürüyor |
| 5 | Streak + günlük hedef halkası (yerel) | V2.4 | ✅ | `activity_log`, `services/streak_service.py`, `StreakRing` |
| 6 | 3 adımlı onboarding + klasör ağacı sidebar | V2.4 | ✅ | `OnboardingWizard`, `SidebarNav`→`Sidebar` (Dönem→Ders→Chapter) |
| 7 | Essay/ödev değerlendirici | V2.5 | 🟡 backend ✅ | `essay_submissions`, `essay_service.py`, `essays/grade` uçları — frontend ekranı sürüyor |
| 8 | YouTube → içerik | V2.6 | ✅ backend | `media_extractors/youtube.py` + `media.py` (URL alımı) — ön yüz formu sürüyor |
| 9 | Ses/ders kaydı → not | V2.6 | ✅ backend | `media_extractors/audio.py` + transkripsiyon zinciri — ön yüz yükleme sürüyor |
| 10 | Çalışma rehberi + kavram haritası | V2.7 | 🟡 backend ✅ | `study_guides`, `services/guide_service.py` — `GuideView` (SVG) sürüyor |
| 11 | Mobil erişim (PWA + LAN) | V2.8 | 🟡 backend ✅ | `/sw.js` + `/manifest.webmanifest` rotaları; vite-plugin-pwa yapılandırması sürüyor |
| 12 | Sokratik chat modu | V2.1 | ✅ | `chat_service.py` modları (`direct\|socratic\|quiz`) |
| 13 | Çok cihaz sync | — | 📄 KARAR | Bulut sync yok (Bölüm 10/4); yerel karşılığı: dönem arşivi export/import (#16). Gerçek bulut sync = gelecekte kullanıcı kararı + feature-flag |
| 14 | DOCX/EPUB/fotoğraf (OCR)/metin yapıştırma | V2.6 | ✅ backend | `media_extractors/{docx,epub,ocr,text}.py`; EPUB stdlib (AGPL'li ebooklib yasak) — ön yüz sürüyor |
| 15 | Çok dilli not (tr/en/auto) | V2.7 | ✅ | settings `not_dili` → tüm üretim promptlarına dil talimatı (not/quiz/flashcard/rehber/genel quiz) |
| 16 | Paylaşım/paket export (dönem arşivi) | V2.3 | 🟡 backend ✅ | `services/archive_service.py`, manifest v1 export/import — ön yüz butonları sürüyor |

### 17.3 Bilinçli Yapılmayacaklar (rapor 7.6 — bağlayıcı)

Paylaşımlı içerik kütüphanesi/sosyal katman, leaderboard/çok oyunculu oyunlaştırma, LMS entegrasyonları, kredi/kota ekonomisi, yerel LLM çalıştırma — hiçbiri v2'ye girmez.

### 17.4 Teknik Sözleşme

- **Şema:** Bölüm 3'ün v2 blokları; `init_db` → `schema.sql` → migration runner (`schema_migrations`). Yeni migration: `sql/migrations/NNN_aciklama.sql` (idempotent zorunlu).
- **Yeni LLM çağrıları:** `generation_logs` kind'ları: `flashcards`, `chat`, `guide`, `essay_grade` (mevcut: note/quiz/overall/essay_grade). Maliyet bekçiliği + Türkçe hatalar tümünde geçerli.
- **Yerel araçlar:** yt-dlp (Unlicense), faster-whisper (MIT), rapidocr-onnxruntime (Apache-2.0), python-docx (MIT), vite-plugin-pwa (MIT) — Ücretsizlik Ajanı kaydı `YETENEKLER/08`'dedir. Tüm çıkarım yerel; model indirmeleri (whisper/OCR) ilk kullanımda, ayarlarla kapatılabilir.
- **Gizlilik değişmez:** hesap/telemetri yok; yeni medya verileri de `data/` içinde; `answer_key` ön yüze asla çıkmaz.
- **Ajan/yetenek eşlemesi:** Bölüm 4.1 (20 ajan) + Bölüm 5. Yeni runtime sözleşmeleri: Yetenekler 09–15.

---

*Bu belge Ana Ajan ve tüm alt ajanlar tarafından referans alınır. Değişiklikler Ana Ajan koordinasyonunda yapılır ve Sürüm Geçmişi'ne işlenir.*
