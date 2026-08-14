-- 0001: materials.type CHECK genişletme (v2 medya türleri)
-- SQLite CHECK değiştirilemediği için tablo yeniden kurulur; mevcut veri birebir korunur.
-- Idempotent: taze kurulumda (schema.sql zaten yeni CHECK'li) çalıştırılsa bile
-- INSERT OR IGNORE + tam kopya sayesinde veri kaybı olmaz.
-- Not: PRAGMA foreign_keys bir transaction içinde değiştirilemez; bu yüzden
-- kopyalama tek açık transaction'da (BEGIN IMMEDIATE ... COMMIT) yapılır.

PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS materials_new (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id      INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    type           TEXT NOT NULL CHECK (type IN ('textbook', 'slides', 'youtube', 'audio', 'docx', 'epub', 'image', 'text')),
    filepath       TEXT NOT NULL,
    extracted_text TEXT,
    page_count     INTEGER,
    vector_ns      TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO materials_new (id, course_id, type, filepath, extracted_text, page_count, vector_ns, created_at)
    SELECT id, course_id, type, filepath, extracted_text, page_count, vector_ns, created_at FROM materials;
DROP TABLE materials;
ALTER TABLE materials_new RENAME TO materials;
COMMIT;
PRAGMA foreign_keys = ON;
