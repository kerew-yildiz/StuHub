-- 0006: study_guides.kind CHECK kısıtına 'comparison' eklenir (Plan #24 —
-- karşılaştırma tablosu üretici).
--
-- SQLite'ta CHECK kısıtı ALTER edilemez; tablo yeniden yaratılır (veri kopyalanır,
-- hiçbir satır kaybolmaz). Migration runner sürüm takibi yaptığı için bu betik bir
-- kez çalışır; yine de yarı kalmış bir denemeye karşı DROP TABLE IF EXISTS ile
-- tekrar çalıştırılabilir haldedir.
--
-- Geri alma: aynı adımlar 'comparison' içermeyen CHECK ile tekrarlanır — geri
-- almadan önce kind = 'comparison' satırları silinmelidir.
--
-- Postgres (Supabase) karşılığı sql/schema_postgres.sql'de tutulur; mevcut canlı
-- veritabanı için elle uygulanacak eşdeğer:
--   ALTER TABLE study_guides DROP CONSTRAINT IF EXISTS study_guides_kind_check;
--   ALTER TABLE study_guides ADD  CONSTRAINT study_guides_kind_check
--     CHECK (kind IN ('summary', 'concept_map', 'comparison'));

DROP TABLE IF EXISTS study_guides_pre_0006;

ALTER TABLE study_guides RENAME TO study_guides_pre_0006;

CREATE TABLE study_guides (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id    TEXT NOT NULL DEFAULT 'local',
    course_id    INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    chapter_id   INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('summary', 'concept_map', 'comparison')),
    content_json TEXT NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_used   TEXT
);

INSERT INTO study_guides (id, tenant_id, course_id, chapter_id, kind, content_json, created_at, model_used)
SELECT id, tenant_id, course_id, chapter_id, kind, content_json, created_at, model_used
FROM study_guides_pre_0006;

DROP TABLE study_guides_pre_0006;

CREATE INDEX IF NOT EXISTS idx_study_guides_course ON study_guides(course_id);
CREATE INDEX IF NOT EXISTS idx_study_guides_tenant ON study_guides(tenant_id, course_id);
