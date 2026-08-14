# StuHub DS

Üniversite öğrencileri için **yerel** (localhost) çalışan ders notu ve quiz uygulaması. Ders dönemlerini klasörler, her ders için notebook oluşturur, dersin PDF kitapları ve hoca sunumları (guide slides) üzerinden **atıflı AI notları**, **bölüm quizleri** ve **genel quiz** üretir.

> ⚠️ **Geliştirme aşamasındadır.** Tek kaynak doğrusu: [`PROJE_YOL_HARITASI.md`](./PROJE_YOL_HARITASI.md) (belkemiği belgesi). Mevcut durum ve faz planı için o belgeye bakın.

## Mimari (özet)

| Katman | Teknoloji |
|--------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind + Zustand (`apps/frontend`) |
| Backend | FastAPI + SQLite (aiosqlite) (`apps/backend`) |
| Vektör DB | LanceDB (embedded, sonraki fazlarda) |
| Embedding | sentence-transformers (yerel, ücretsiz) |
| LLM | DeepSeek API (kullanıcının kendi anahtarı) |

## Geliştirme

Ön koşullar: Node ≥ 20 + npm, [uv](https://docs.astral.sh/uv/) (Python 3.12 yönetimi), git.

```bash
# Backend (veri dizini: data/)
cd apps/backend
uv sync
uv run uvicorn src.main:app --reload --port 8000

# Frontend (ayrı terminal; /api → 127.0.0.1:8000 proxy'li)
cd apps/frontend
npm install
npm run dev        # http://localhost:5173
```

Sağlık kontrolü: `GET http://127.0.0.1:8000/health`

Test / lint / tip:

```bash
cd apps/backend && uv run ruff check . && uv run pyright && uv run pytest -v
cd apps/frontend && npm run lint && npm run typecheck && npm test
```

## Güvenlik & Gizlilik

- Hesap yok, telemetri yok, analytics yok. Tüm veri yerel (`data/`).
- API anahtarı `settings` tablosunda ya da geliştirmede `.env`'de tutulur; **asla commit edilmez** (gitleaks pre-commit hook ile korunur).
- Uygulama çalışırken yalnızca DeepSeek API'ye ağ çağrısı yapar.
