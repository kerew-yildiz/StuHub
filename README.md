# StuHub

Üniversite öğrencileri için AI ders çalışma asistanı. Ders dönemlerini klasörler, her ders için notebook oluşturur; dersin PDF kitapları, hoca sunumları ve v2 ile **YouTube videoları, ses kayıtları, DOCX/EPUB belgeleri, görseller ve yapıştırılan metinler** üzerinden **atıflı AI notları**, **bölüm ve genel quizler**, **flashcard'lar (SM-2 uzamsal tekrar)**, **atıflı "Materyale Sor" sohbeti**, **çalışma rehberi + kavram haritası** ve **ödev değerlendirmesi** üretir.

> ✅ **1.0 sürümü teslim edildi** (Faz 0–6). **2.0 sürümü geliştirildi** (V2.0–V2.9 — Niş Analizi Entegrasyonu). Kullanım için: **[`KULLANIM.md`](./KULLANIM.md)**.
>
> 🎯 **Dağıtım hedefi: SaaS.** Bu repodaki sürüm **localhost'ta** çalışır (auth yok, veri `data/` altında, LLM için kendi DeepSeek anahtarınız) — bu bugünkü durumdur, nihai mimari değildir. Ürün SaaS olarak yayınlanacak; açık kararlar vault'taki `KARAR-SAAS-GECISI.md`'de. Aşağıdaki "tüm veri cihazınızda / hesap yok" ifadeleri yerel sürümü tarif eder.
>
> 📓 **Geliştirme belgeleri bu repoda değil.** Yol haritası, sistem yetenekleri, araştırma raporları, `AJANLAR/` ve `YETENEKLER/` sözleşmeleri KerewOS vault'unda tutulur: `KerewOS/🏰 300-Projects/StuHub/`. Belgelerin birbirine verdiği göreli yollar (`PROJE_YOL_HARITASI.md`, `AJANLAR/…`, `YETENEKLER/…`) o klasörde aynen geçerlidir. Tek kaynak doğrusu hâlâ `PROJE_YOL_HARITASI.md`; bu repo yalnızca çalışan uygulamayı barındırır.

## Özellikler

- **Dönem/Ders/Chapter yönetimi** — dönem klasörleri, ders notebook'ları, chapter'lar; 3 adımlı Türkçe onboarding
- **Materyal yükleme** — kitap PDF'leri + sunumlar (PDF/PPTX) + **v2: YouTube, ses kaydı, DOCX, EPUB, görsel (OCR), metin yapıştırma**; yerel vektör indeksleme (LanceDB + bge-m3); ses/youtube için yerel transkripsiyon (faster-whisper)
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
| Backend | FastAPI + SQLite (aiosqlite) (`apps/backend`) |
| Vektör DB | LanceDB (embedded) |
| Embedding | sentence-transformers + bge-m3 (yerel, ücretsiz) |
| LLM | DeepSeek API (kullanıcının kendi anahtarı — onaylı istisna) |
| Medya (v2) | yt-dlp (altyazı/indirme) · faster-whisper (yerel STT) · rapidocr-onnxruntime (yerel OCR) · python-docx (tümü ücretsiz lisanslı; EPUB stdlib) |

## Hızlı Başlangıç

```bash
# Backend (veri dizini: data/)
cd apps/backend && uv sync
uv run uvicorn src.main:app --port 8000

# Frontend (ayrı terminal)
cd apps/frontend && npm install
npm run dev          # http://localhost:5173

# Üretim (tek komut): npm run build → yalnızca backend → http://127.0.0.1:8000
# Aynı ağdan erişim (PWA/telefon): uvicorn src.main:app --host 0.0.0.0 --port 8000
```

`.env` dosyasına `DEEPSEEK_API_KEY` ekleyin (bkz. `.env.example`) — ayrıntılı rehber: `KULLANIM.md`.

## Test / Lint / Güvenlik

```bash
cd apps/backend && uv run ruff check . && uv run pyright && uv run pytest -v
cd apps/backend && uv run bandit -r src && uv run pip-audit
cd apps/frontend && npm run lint && npm run typecheck && npm test && npm run build
cd apps/frontend && npm audit
gitleaks detect --source .   # commit öncesi (pre-commit hook da çalışır)
```

Mevcut kapılar: backend **183 pytest** · frontend **20 vitest** · bandit/pip-audit/npm audit **0 bulgu** · gitleaks temiz.

## Güvenlik & Gizlilik

- Hesap yok, telemetri yok, analytics yok. Tüm veri yerel (`data/`).
- API anahtarı `settings` tablosunda ya da `.env`'de; asla loglanmaz/yanıtlanmaz (maskeli).
- Uygulama çalışırken yalnızca DeepSeek API'ye (üretim için gerekli parçalar) ve YouTube altyazı indirmesine ağ çağrısı yapar; embedding, STT ve OCR tamamen yereldir.
- Quiz `answer_key`'leri frontend'e hiçbir rotada gitmez.
- Şema evrimi güvenli: `init_db` idempotent + `schema_migrations` migration runner'ı (eski kurulum verisi korunarak yükselir).
