# StuHub DS

Üniversite öğrencileri için **yerel** (localhost) çalışan ders notu ve quiz uygulaması. Ders dönemlerini klasörler, her ders için notebook oluşturur, dersin PDF kitapları ve hoca sunumları (guide slides) üzerinden **atıflı AI notları**, **bölüm quizleri** ve **ders geneli 55 soruluk quiz** üretir. Tüm veri cihazınızda kalır.

> ✅ **1.0 sürümü teslim edildi** (Faz 0–6 tamamlandı). Tek kaynak doğrusu: [`PROJE_YOL_HARITASI.md`](./PROJE_YOL_HARITASI.md). Kullanım için: **[`KULLANIM.md`](./KULLANIM.md)**.

## Özellikler

- **Dönem/Ders/Chapter yönetimi** — dönem klasörleri, ders notebook'ları, chapter'lar
- **Materyal yükleme** — kitap PDF'leri + sunumlar (PDF/PPTX); yerel vektör indeksleme (LanceDB + bge-m3)
- **Atıflı not üretimi** — guide slides rehberli, kitap taramalı, konu başına map-reduce üretim; tıklanabilir atıflar
- **Bölüm quizi** — her konu için 5 çoktan seçmeli soru; anında açıklamalı geri bildirim
- **Genel quiz** — 55 soru (20 MCQ + 15 D/Y + 15 boşluk + 5 açık uçlu); açık uçlular otomatik puanlanır (rubrik + ideal cevap)
- **Maliyet gözetimi** — her LLM çağrısı `generation_logs`'ta; Türkçe hata mesajları, üstel bekleme + devre kesici

## Mimari

| Katman | Teknoloji |
|--------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind + Zustand (`apps/frontend`) |
| Backend | FastAPI + SQLite (aiosqlite) (`apps/backend`) |
| Vektör DB | LanceDB (embedded) |
| Embedding | sentence-transformers + bge-m3 (yerel, ücretsiz) |
| LLM | DeepSeek API (kullanıcının kendi anahtarı — onaylı istisna) |

## Hızlı Başlangıç

```bash
# Backend (veri dizini: data/)
cd apps/backend && uv sync
uv run uvicorn src.main:app --port 8000

# Frontend (ayrı terminal)
cd apps/frontend && npm install
npm run dev          # http://localhost:5173

# Üretim (tek komut): npm run build → yalnızca backend → http://127.0.0.1:8000
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

Mevcut kapılar: backend **75 pytest** · frontend **8 vitest** · bandit/pip-audit/npm audit **0 bulgu** · gitleaks temiz.

## Güvenlik & Gizlilik

- Hesap yok, telemetri yok, analytics yok. Tüm veri yerel (`data/`).
- API anahtarı `settings` tablosunda ya da `.env`'de; asla loglanmaz/yanıtlanmaz (maskeli).
- Uygulama çalışırken yalnızca DeepSeek API'ye ağ çağrısı yapar; embedding yereldir.
- Quiz `answer_key`'leri frontend'e hiçbir rotada gitmez.
