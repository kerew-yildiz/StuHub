-- 0009: essay_submissions.kind kolonu — ödev taslak koçu (Plan #41).
-- Idempotent: "duplicate column name" hoş görülür (bkz. migrations/README.md).
--
-- 'grade' = son teslim değerlendirmesi (mevcut davranış, varsayılan — eski satırlar
-- da bu değeri alır), 'draft' = puansız yapısal geri bildirim (tez/kanıt/zayıf bölüm).
-- SQLite'ta yalnızca yeni kolonu referans alan CHECK, ALTER TABLE ADD COLUMN ile
-- eklenebilir (3.25+) — tablo yeniden yaratmaya gerek yok.
--
-- Postgres (Supabase) karşılığı sql/schema_postgres.sql'de tutulur; mevcut canlı
-- veritabanı için elle uygulanacak eşdeğer:
--   ALTER TABLE essay_submissions ADD COLUMN kind TEXT NOT NULL DEFAULT 'grade';
--   ALTER TABLE essay_submissions ADD CONSTRAINT essay_submissions_kind_check
--       CHECK (kind IN ('grade', 'draft'));

ALTER TABLE essay_submissions
    ADD COLUMN kind TEXT NOT NULL DEFAULT 'grade' CHECK (kind IN ('grade', 'draft'));

CREATE INDEX IF NOT EXISTS idx_essay_submissions_kind ON essay_submissions(tenant_id, course_id, kind);
