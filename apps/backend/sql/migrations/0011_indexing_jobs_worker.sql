-- 0011: indexing_jobs'a worker kimliği + heartbeat — çok-instance kurtarma (yol haritası Aşama 0-11).
-- Idempotent: ALTER TABLE ADD COLUMN "duplicate column name" hatası db.py'de hoş görülür.
--
-- Sorun: `recover_stale_jobs()` açılışta status='processing' olan TÜM işleri, hangi
-- process'e ait olduğuna bakmadan 'pending'e çeviriyordu. Tek instance'ta bu doğru bir
-- çökme kurtarmasıydı; ama Railway rolling deploy'unda (eski ve yeni instance kısa süre
-- birlikte çalışır) ya da ikinci bir replika açıldığında, YENİ process, ESKİ process'in
-- o an aktif işlediği işleri kuyruğa geri koyuyordu → aynı materyal iki kez indekslenir,
-- embedding/LLM maliyeti iki katına çıkar.
--
-- Çözüm: her iş, onu claim eden process'in kimliğini (`worker_id`) ve son yaşam
-- işaretini (`heartbeat_at`) taşır. Kurtarma yalnızca heartbeat'i bayatlamış işleri
-- geri alır; canlı bir worker'ın işlediği iş dokunulmadan bırakılır.
--
-- Geri alma: kolonlar bırakılabilir (veri kaybı olmaz, kurtarma eski davranışa döner):
--   ALTER TABLE indexing_jobs DROP COLUMN worker_id;
--   ALTER TABLE indexing_jobs DROP COLUMN heartbeat_at;
--
-- Postgres (Supabase) karşılığı sql/schema_postgres.sql'de tutulur; mevcut canlı
-- veritabanı için elle uygulanacak eşdeğer:
--   ALTER TABLE indexing_jobs ADD COLUMN IF NOT EXISTS worker_id    TEXT;
--   ALTER TABLE indexing_jobs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;
--   CREATE INDEX IF NOT EXISTS idx_indexing_jobs_recovery
--       ON indexing_jobs(status, heartbeat_at);

ALTER TABLE indexing_jobs ADD COLUMN worker_id TEXT;
ALTER TABLE indexing_jobs ADD COLUMN heartbeat_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_indexing_jobs_recovery
    ON indexing_jobs(status, heartbeat_at);
