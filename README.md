# StuHub

Üniversite öğrencileri için AI ders çalışma asistanı. Ders dönemlerini klasörler, her ders için notebook oluşturur; dersin PDF kitapları, hoca sunumları ve v2 ile **YouTube videoları, ses kayıtları, DOCX/EPUB belgeleri, görseller ve yapıştırılan metinler** üzerinden **atıflı AI notları**, **bölüm ve genel quizler**, **flashcard'lar (SM-2 uzamsal tekrar)**, **atıflı "Materyale Sor" sohbeti**, **çalışma rehberi + kavram haritası** ve **ödev değerlendirmesi** üretir.

## İki çalışma modu

StuHub **tek kod tabanı, iki mod** olarak çalışır. Modu `.env`'deki `DATABASE_URL` belirler
(`src/config.py` → `Settings.saas_mode`); dallanan bir kod yolu yoktur.

| | **Yerel mod** (`DATABASE_URL` boş) | **SaaS mod** (`DATABASE_URL` dolu) |
|---|---|---|
| Veritabanı | SQLite (aiosqlite), `data/stuhub.db` | Postgres / Supabase (asyncpg) |
| Kimlik doğrulama | Yok — sabit `tenant_id = "local"` | Supabase JWT zorunlu, kiracı başına izolasyon |
| Kota / abonelik | Yok, sınırsız | Plan bazlı aylık kota + Lemon Squeezy |
| Veri | Tamamen cihazda (`data/`) | Supabase'de; materyal dosyaları sunucu diskinde |

> 🎯 **Mevcut durum: SaaS dağıtımına hazırlanılıyor.** Supabase ve Lemon Squeezy
> yapılandırıldı, deploy hedefi **Railway** olarak seçildi ve konteyner dosyaları yazıldı
> (`Dockerfile`, `railway.json`). **Henüz canlıya alınmadı.**
>
> Bu repoda "tüm veri cihazınızda / hesap yok" diyen her ifade **yalnızca yerel mod için**
> geçerlidir.

### Belge haritası — hangi dosya neyi anlatır

| Dosya | İçerik |
|---|---|
| **[`DEVIR.md`](./DEVIR.md)** | **Projenin güncel durumu**: ne yapıldı, ne kaldı, bilinen tuzaklar. Devralan kişi/ajan önce bunu okumalı. |
| [`DEPLOY.md`](./DEPLOY.md) | Railway deploy adımları + deploy sonrası doğrulama listesi |
| [`KULLANIM.md`](./KULLANIM.md) | Yerel modda kurulum ve günlük kullanım |
| [`KULLANIM-SAAS.md`](./KULLANIM-SAAS.md) | SaaS modu: Supabase, auth, Lemon Squeezy kurulumu |
| `~/.claude/plans/stuhub-scalable-yapmak-sorted-valiant.md` | Ölçeklenebilirlik yol haritası (100 → 100k kullanıcı). **Aşama 0 bölümü eskimiştir** — `DEVIR.md` §3'teki düzeltmelerle okunmalı. |

> 📓 **Geliştirme belgeleri bu repoda değil.** Yol haritası, sistem yetenekleri, araştırma raporları, `AJANLAR/` ve `YETENEKLER/` sözleşmeleri KerewOS vault'unda tutulur: `KerewOS/🏰 300-Projects/StuHub/`. Belgelerin birbirine verdiği göreli yollar (`PROJE_YOL_HARITASI.md`, `AJANLAR/…`, `YETENEKLER/…`) o klasörde aynen geçerlidir.
>
> ✅ **1.0 sürümü teslim edildi** (Faz 0–6). **2.0 sürümü geliştirildi** (V2.0–V2.9 — Niş Analizi Entegrasyonu).

## Özellikler

- **Dönem/Ders/Chapter yönetimi** — dönem klasörleri, ders notebook'ları, chapter'lar; 3 adımlı Türkçe onboarding
- **Materyal yükleme** — kitap PDF'leri + sunumlar (PDF/PPTX/PPT) + **v2: YouTube, ses kaydı, DOCX, EPUB, görsel (OCR), metin yapıştırma**; yerel vektör indeksleme (LanceDB + sentence-transformers); ses/youtube için yerel transkripsiyon (faster-whisper)
- **Atıflı not üretimi** — guide slides rehberli, kitap taramalı, konu başına map-reduce üretim; tıklanabilir atıflar; çok dilli üretim (tr/en/auto)
- **Bölüm quizi** — her konu için 5 çoktan seçmeli soru; anında açıklamalı geri bildirim
- **Genel quiz** — 55 soru (20 MCQ + 15 D/Y + 15 boşluk + 5 açık uçlu); açık uçlular otomatik puanlanır
- **Flashcard + uzamsal tekrar** — not ve quizden atıflı kart üretimi; yerel SM-2 (Again/Hard/Good/Easy); kurs bazlı günlük tekrar kuyruğu
- **Materyale Sor** — atıflı RAG sohbet (Doğrudan / Sokratik / Sınav Modu); yanıtlar kaynak çipli
- **Çalışma rehberi + kavram haritası** — chapter/ders özeti, anahtar terimler, sınav odakları, DAG kavram haritası
- **Ödev değerlendirici** — 0–100 rubrikli puanlama; ölçüt kırılımı, güçlü/zayıf yönler, alıntılı yorumlar
- **Export & arşiv** — not PDF/MD, Anki `.apkg`, CSV; dönem arşivi (zip) dışa/içe aktarma (çok cihaz için yerel taşıma)
- **Streak + günlük hedef** — yerel öğrenme alışkanlığı halkası (hesap/leaderboard yok)
- **PWA + LAN erişimi** — üretim modunda kurulabilir uygulama; aynı ağdan erişim
- **Maliyet gözetimi** — her LLM çağrısı `generation_logs`'ta; Türkçe hata mesajları, üstel bekleme + devre kesici

## Mimari

| Katman | Teknoloji |
|--------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind + Zustand + vite-plugin-pwa (`apps/frontend`) |
| Backend | FastAPI (`apps/backend`) — yerel modda SQLite (aiosqlite), SaaS modunda Postgres/Supabase (asyncpg). Ortak arayüz `src/pg_compat.py` sarmalayıcısıyla sağlanır. |
| Vektör DB | LanceDB (embedded, yerel diskte). **Tek instance kısıtı** — yatay ölçekleme için pgvector'e taşınması planlı (`DEVIR.md` §6). |
| Embedding | sentence-transformers, yerel ve ücretsiz. **Kullanılan model: `paraphrase-multilingual-MiniLM-L12-v2`** (384 boyut, ~458 MB), `STUHUB_EMBED_MODEL` ile ayarlanır. Kodun varsayılanı `BAAI/bge-m3`'tür (1024 boyut, ~4.3 GB) — ikisi uyumsuzdur, bkz. `DEVIR.md` §5.1. |
| LLM | Ücretsiz sağlayıcı zinciri (yetenek sırasına göre, biri kota sınırına ulaşınca otomatik sıradakine geçilir): Gemini 3.1 Flash Lite → OpenRouter (Nemotron 3 Ultra 550B free) → Groq (Llama 3.3 70B) → Cerebras (Llama 3.3 70B, geçici) → GitHub Models (GPT-4.1 mini). Geçici çözüm; ücretli birincil sağlayıcıya geçiş planlı. Tek kaynak: `src/services/llm_providers.py` |
| Medya (v2) | yt-dlp (altyazı/indirme) · faster-whisper (yerel STT) · rapidocr-onnxruntime (yerel OCR) · python-docx (tümü ücretsiz lisanslı; EPUB stdlib) |
| Dağıtım | Railway, GHCR imajından (repo build'inden değil — CI'da derlenip yayınlanır). Tek imaj, iki rol: `STUHUB_ROLE=api\|worker` — bkz. `DEPLOY.md` |

## Hızlı Başlangıç (Windows native)

StuHub **yalnızca native Windows** üzerinde çalışır — WSL/Linux bağımlılığı yok
(eski WSL ortamı kalıcı olarak kaldırıldı, bkz. proje kararları). Repo zaten
Windows diskinde (`C:\Users\...\StuHub`); backend için Windows Python venv
(`.venv-win`), frontend için native `npm install` ile kurulan `node_modules`
kullanılır.

```powershell
# Backend (ilk kurulum, tek seferlik) — Windows Python 3.12 + uv
cd apps\backend
$env:UV_PROJECT_ENVIRONMENT = ".venv-win"
uv sync --python 3.12

# Frontend (ilk kurulum, tek seferlik)
cd apps\frontend
npm install
```

Sonraki her çalıştırmada kök dizindeki kısayollar yeterli (PowerShell veya
Windows Terminal'den):

```powershell
.\dev-backend.cmd     # http://127.0.0.1:8000
.\dev-frontend.cmd    # http://localhost:5173 (ayrı pencere/terminal)

# Üretim (tek komut): apps\frontend içinde npm run build → yalnızca backend → http://127.0.0.1:8000
```

`.env` dosyasına en az bir sağlayıcı anahtarı ekleyin (`GOOGLE_API_KEY` önerilir; bkz. `.env.example`) — ayrıntılı rehber: `KULLANIM.md`.

## Test / Lint / Güvenlik

`uv run` proje kökü venv'ini (`.venv`) değil `UV_PROJECT_ENVIRONMENT` ile seçilen
`.venv-win`'i kullanmalı — kabuk başına bir kere ayarlayın (`$env:UV_PROJECT_ENVIRONMENT = ".venv-win"`,
`apps\backend` içinden) ya da doğrudan `apps\backend\.venv-win\Scripts\python.exe -m pytest` gibi çağırın.

```bash
cd apps/backend && uv run ruff check . && uv run pyright && uv run pytest -v
cd apps/backend && uv run bandit -r src && uv run pip-audit
cd apps/frontend && npm run lint && npm run typecheck && npm test && npm run build
cd apps/frontend && npm audit
gitleaks detect --source .   # commit öncesi (pre-commit hook da çalışır)
```

Mevcut kapılar: backend **334 pytest (0 başarısız)** · frontend **64 vitest (0 başarısız)** ·
ruff/pyright **0 hata** · bandit/pip-audit/npm audit **0 bulgu** · gitleaks temiz.

> ⚠️ **CI `ruff check .`** (kök dizin dahil) çalıştırır; yerelde sık kullanılan
> `ruff check src/ tests/` ile aynı değildir. Depoda commit edilmemiş scratch
> dosyaları varsa CI lint adımı düşebilir — bkz. `DEVIR.md` §5.4.
>
> ⚠️ **Frontend testleri zamanlamaya duyarlı.** `GuideView.test.tsx` Mermaid'i gerçekten
> çiziyor (mock yok) ve jsdom'da ~12 sn sürüyor; yüklü makinede başka testler de vitest'in
> 5 sn'lik varsayılanına takılabiliyor. Tek seferlik bir başarısızlık gördüğünüzde önce
> tekrar çalıştırın — flake olma ihtimali yüksek.

## Güvenlik & Gizlilik

**Her iki modda da geçerli:**

- API anahtarı `settings` tablosunda ya da `.env`'de; asla loglanmaz/yanıtlanmaz (maskeli).
- Embedding, STT ve OCR tamamen yereldir — materyal içeriği bu adımlarda cihazdan/sunucudan çıkmaz. Dışarıya yalnızca yapılandırılmış LLM sağlayıcılarına üretim için gerekli parçalar ve YouTube altyazı indirmesi gider.
- Quiz `answer_key`'leri frontend'e hiçbir rotada gitmez.
- Şema evrimi: `init_db` idempotent + `schema_migrations` migration runner'ı. **Yalnızca SQLite yolunda otomatiktir**; Postgres şeması hâlâ elle uygulanır (`sql/schema_postgres.sql`) — otomatik runner'a taşınması planlı, bkz. `DEVIR.md` §6.

**Yalnızca yerel modda (`DATABASE_URL` boş):**

- Hesap yok, telemetri yok, analytics yok. Tüm veri cihazda (`data/`).

**Yalnızca SaaS modunda (`DATABASE_URL` dolu):**

- Kiracı izolasyonu **uygulama katmanında** `tenant_id` filtreleriyle sağlanır; uygulama RLS'i bypass eden service-role anahtarıyla bağlandığı için RLS ikincil savunmadır. Kimlik parametresi alan her uç sahiplik doğrulamalıdır (`KULLANIM-SAAS.md` §6).
- Materyal dosyaları sunucu diskinde tutulur (object storage'a taşınması planlı).
- KVKK/GDPR gizlilik metni **henüz yazılmadı** — canlıya almadan önce gerekli.
