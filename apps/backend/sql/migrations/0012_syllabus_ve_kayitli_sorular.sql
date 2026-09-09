-- 0012: materials.type'a 'syllabus' eklenir + saved_questions tablosu (Plan: kazanımlar).
-- Idempotent: materials rebuild'i 0001 desenini izler (SQLite CHECK değiştirilemez);
-- saved_questions tüm DDL'i CREATE ... IF NOT EXISTS.
--
-- syllabus: ders izlencesi/müfredat belgesi (PDF/DOCX) — not/quiz üretimi bu materyalin
-- extracted_text'ini {kazanimlar} olarak prompt'a ekler (bkz. services/note_generator.py
-- load_kazanimlar, services/quiz_generator.py). saved_questions: kullanıcının feed'den
-- kaydettiği sorular — aynı soru bir kiracı için yalnızca bir kez kaydedilebilir.
--
-- Postgres (Supabase) karşılığı sql/schema_postgres.sql'de tutulur; mevcut canlı
-- veritabanı için elle uygulanacak eşdeğer:
--   ALTER TABLE materials DROP CONSTRAINT IF EXISTS materials_type_check;
--   ALTER TABLE materials ADD CONSTRAINT materials_type_check
--       CHECK (type IN ('textbook', 'slides', 'youtube', 'audio', 'docx', 'epub', 'image', 'text', 'syllabus'));
--   CREATE TABLE IF NOT EXISTS saved_questions (
--       id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
--       tenant_id          UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
--       feed_question_id   BIGINT NOT NULL REFERENCES feed_questions(id) ON DELETE CASCADE,
--       created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
--       UNIQUE(tenant_id, feed_question_id)
--   );
--   CREATE INDEX IF NOT EXISTS idx_saved_questions_tenant_created
--       ON saved_questions(tenant_id, created_at DESC);
--   ALTER TABLE saved_questions ENABLE ROW LEVEL SECURITY;
--   DROP POLICY IF EXISTS tenant_isolation ON saved_questions;
--   CREATE POLICY tenant_isolation ON saved_questions
--       USING (tenant_id = auth.uid()) WITH CHECK (tenant_id = auth.uid());

PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS materials_new (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id      TEXT NOT NULL DEFAULT 'local',
    course_id      INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    type           TEXT NOT NULL CHECK (type IN ('textbook', 'slides', 'youtube', 'audio', 'docx', 'epub', 'image', 'text', 'syllabus')),
    filepath       TEXT NOT NULL,
    extracted_text TEXT,
    page_count     INTEGER,
    vector_ns      TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO materials_new (id, tenant_id, course_id, type, filepath, extracted_text, page_count, vector_ns, created_at)
    SELECT id, tenant_id, course_id, type, filepath, extracted_text, page_count, vector_ns, created_at FROM materials;
DROP TABLE materials;
ALTER TABLE materials_new RENAME TO materials;
COMMIT;
PRAGMA foreign_keys = ON;

CREATE INDEX IF NOT EXISTS idx_materials_tenant_course ON materials(tenant_id, course_id);

CREATE TABLE IF NOT EXISTS saved_questions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id          TEXT NOT NULL DEFAULT 'local',
    feed_question_id   INTEGER NOT NULL REFERENCES feed_questions(id) ON DELETE CASCADE,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, feed_question_id)
);
CREATE INDEX IF NOT EXISTS idx_saved_questions_tenant_created
    ON saved_questions(tenant_id, created_at DESC);
