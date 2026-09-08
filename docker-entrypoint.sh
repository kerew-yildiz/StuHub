#!/bin/sh
# StuHub konteyner giriş noktası — rolü STUHUB_ROLE belirler.
#
#   api    (varsayılan) : uvicorn + istek-içi arka plan işçileri (bugünkü davranış)
#   worker               : yalnızca indeksleme/feed işçileri, HTTP sunucusu yok
#
# `worker` rolü şimdilik API ile AYNI imajı kullanır; imaj ayrımı üretimin kuyruğa
# taşınmasına bağlıdır (bkz. Dockerfile başlığı, yol haritası Aşama 2).
set -eu

: "${STUHUB_ROLE:=api}"
: "${PORT:=8000}"

case "$STUHUB_ROLE" in
  api)
    # Tek worker: embedding modeli process-global olduğu için her uvicorn worker'ı
    # modelin ayrı bir kopyasını belleğe alır. Yatay ölçekleme, process çoğaltmakla
    # değil, Railway replikasıyla yapılmalı (durum paylaşımı için yol haritası Aşama 2:
    # object storage + pgvector + Redis).
    exec uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --workers 1
    ;;
  worker)
    exec python -m src.worker_main
    ;;
  *)
    echo "Bilinmeyen STUHUB_ROLE: $STUHUB_ROLE (api|worker)" >&2
    exit 1
    ;;
esac
