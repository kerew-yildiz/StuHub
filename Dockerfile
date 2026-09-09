# StuHub — üretim imajı (Railway).
#
# Tek imaj, iki rol: aynı imaj hem API hem (ileride) ayrı worker servisi olarak
# çalıştırılabilir; rol `STUHUB_ROLE` ile seçilir (bkz. docker-entrypoint.sh).
#
# NEDEN TEK İMAJ (şimdilik): API'nin ML bağımlılıklarından kurtulabilmesi için not/quiz
# üretiminin istek-içi olmaktan çıkıp kuyruğa taşınması gerekiyor — bugün üretim ve
# sohbet API process'inde çalışıyor ve `retrieval.hybrid_search` → `embed_service`
# zinciriyle embedding modeline ihtiyaç duyuyor. İmaj ayrımı, yol haritasının Aşama 2
# adımına (Arq kuyruğu) bağlıdır; o iş bitmeden ayırmak API'yi çalışmaz hale getirir.
#
# Embedding modeli imaja GÖMÜLÜR: ephemeral konteynerde çalışma anında indirilirse her
# deploy/restart/scale-out'ta yeniden inilir ve ilk indeksleme isteği dakikalarca asılı
# kalır.

# ── Aşama 1: frontend derlemesi ────────────────────────────────────────────
FROM node:22-slim AS frontend

WORKDIR /build
COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN npm ci

COPY apps/frontend/ ./
# Vite `envDir: '../../'` ile kök .env'i okur; üretimde bu değerler build argümanı
# olarak gelir (VITE_* değişkenleri tarayıcıya gömülür, gizli DEĞİLdir).
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build


# ── Aşama 2: python bağımlılıkları ─────────────────────────────────────────
FROM python:3.12-slim AS deps

# uv: lock dosyasıyla birebir kurulum (CI ile aynı sürümler).
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app/apps/backend
ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY apps/backend/pyproject.toml apps/backend/uv.lock ./
# --no-dev: pytest/pyright/ruff üretim imajına girmez.
RUN uv sync --frozen --no-dev --no-install-project


# ── Aşama 3: embedding modelini imaja göm ──────────────────────────────────
FROM deps AS model

# Kodun varsayılanı (BAAI/bge-m3, 4.3 GB) değil, üretimde kullanılan model gömülür.
# Bu değer, çalışma zamanındaki STUHUB_EMBED_MODEL ile AYNI olmalı — farklıysa indeks
# boyutu uyuşmaz ve uygulama `VectorDimMismatch` ile durur (services/vector_store.py).
ARG EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV HF_HOME=/opt/hf
RUN /app/.venv/bin/python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('${EMBED_MODEL}')" \
    && find /opt/hf -name '*.onnx' -delete \
    && find /opt/hf -name '*.msgpack' -delete \
    && find /opt/hf -name '*.h5' -delete


# ── Aşama 4: çalışma imajı ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# ffmpeg: faster-whisper ses/YouTube transkripsiyonu için gerekli (yt-dlp çıktısını çözer).
# libgl1/libglib2.0-0: rapidocr-onnxruntime (OpenCV) çalışma zamanı bağımlılıkları.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Uygulamanın çalıştığı ayrıcalıksız kullanıcı. `USER` ile SABİTLENMEZ: Railway
# kalıcı volume'u root olarak mount ettiği için konteynerin root başlaması,
# /data'yı bu kullanıcıya devretmesi ve ayrıcalığı sonra bırakması gerekiyor
# (bkz. docker-entrypoint.sh). Aksi halde uygulama volume'a hiç yazamaz.
RUN useradd --create-home --uid 10001 stuhub

WORKDIR /app
# Sahiplik KOPYALAMA SIRASINDA verilir. Ayrı bir `RUN chown -R` adımı, dokunduğu her
# dosyayı yeni bir katmana yeniden yazar: 2026-09-09'da ölçüldü — içerik toplam 2.6 GB
# (venv 2.1 GB + model 458 MB) iken imaj 8.39 GB'a çıkıyordu (aynı veri 2-3 kez) ve
# chown adımı tek başına 175 saniye sürüyordu. `--chown`/`--chmod` bunu sıfıra indirir.
COPY --from=deps --chown=stuhub:stuhub /app/.venv /app/.venv
COPY --from=model --chown=stuhub:stuhub /opt/hf /opt/hf
COPY --chown=stuhub:stuhub apps/backend /app/apps/backend
COPY --from=frontend --chown=stuhub:stuhub /build/dist /app/apps/frontend/dist
COPY --chown=stuhub:stuhub --chmod=0755 docker-entrypoint.sh /app/docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/hf \
    # Konteyner root başlayıp entrypoint'te uid 10001'e düştüğü için HOME aksi halde
    # `/root` kalıyor: asyncpg açılışta varsayılan SSL anahtarını ($HOME/.postgresql/
    # postgresql.key) stat'lıyor ve `PermissionError` ile uygulamayı düşürüyor.
    # (2026-09-09, ilk canlı Railway deploy'unda yakalandı.)
    HOME=/home/stuhub \
    # Materyal dosyaları ve LanceDB için yol. Railway'de kalıcı bir volume buraya
    # bağlanmalı — aksi halde her deploy'da yüklenen materyaller ve indeks kaybolur.
    # (Object storage'a taşıma yol haritasının "ölçekten bağımsız" maddesi.)
    STUHUB_DATA_DIR=/data \
    # Kod varsayılanı 4.3 GB'lık bge-m3; imaja gömülen modelle aynı olmalı.
    STUHUB_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# USER yok — ayrıcalık bırakma entrypoint'te (yukarıdaki gerekçe).
WORKDIR /app/apps/backend
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
