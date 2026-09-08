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
: "${STUHUB_DATA_DIR:=/data}"

# Railway kalıcı volume'u ROOT olarak mount ediyor (docs.railway.com/volumes →
# "Permissions"). İmaj non-root bir kullanıcıyla BAŞLARSA veri dizinine hiç
# yazamaz: materyal yükleme, SQLite ve LanceDB ilk yazmada "permission denied"
# ile düşer. Railway'in kendi önerdiği çözüm RAILWAY_RUN_UID=0, yani uygulamayı
# tümüyle root çalıştırmak; onun yerine konteyner root başlar, YALNIZCA veri
# dizinini uygulama kullanıcısına devreder ve ayrıcalığı hemen bırakır.
# (2026-09-08: bu ortamda Docker olmadığı için ilk Railway build'inde doğrulanacak.)
APP_UID=10001

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$STUHUB_DATA_DIR"
  chown -R "$APP_UID:$APP_UID" "$STUHUB_DATA_DIR"
  if command -v setpriv >/dev/null 2>&1; then
    # Aynı script'i ayrıcalıksız kullanıcıyla yeniden çalıştırır; ikinci turda
    # id -u artık 0 olmadığı için doğrudan role geçilir.
    exec setpriv --reuid="$APP_UID" --regid="$APP_UID" --clear-groups "$0" "$@"
  fi
  # setpriv beklenmedik biçimde yoksa boot'u kırmaktansa root devam edilir.
  echo "UYARI: setpriv bulunamadı — uygulama root olarak çalışıyor" >&2
fi

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
