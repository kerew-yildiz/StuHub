-- 0002: v2 (Niş Analizi Entegrasyonu) yeni tabloları + indexing_jobs.kind
-- Idempotent: tüm DDL IF NOT EXISTS / hoş görülen "duplicate column name" ile güvenli.

-- Flashcard desteleri (chapter veya ders seviyesi; kartlar denormalize JSON)
CREATE TABLE IF NOT EXISTS flashcard_sets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    chapter_id  INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    cards_json  TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_used  TEXT
);

-- SM-2 uzamsal tekrar durumu (Yetenek 09; kart = cards_json[indeks])
CREATE TABLE IF NOT EXISTS card_reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id        INTEGER NOT NULL REFERENCES flashcard_sets(id) ON DELETE CASCADE,
    card_index    INTEGER NOT NULL,
    ease_factor   REAL NOT NULL DEFAULT 2.5,
    interval_days REAL NOT NULL DEFAULT 0,
    repetitions   INTEGER NOT NULL DEFAULT 0,
    due_at        TIMESTAMP,
    last_rating   TEXT,
    reviewed_at   TIMESTAMP,
    UNIQUE(set_id, card_index)
);

-- "Materyale Sor" sohbet geçmişi (yerel; atıflar JSON)
CREATE TABLE IF NOT EXISTS chat_messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id      INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    role           TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content        TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    mode           TEXT NOT NULL DEFAULT 'direct' CHECK (mode IN ('direct', 'socratic', 'quiz')),
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Çalışma rehberi çıktıları (özet / kavram haritası)
CREATE TABLE IF NOT EXISTS study_guides (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id    INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    chapter_id   INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('summary', 'concept_map')),
    content_json TEXT NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_used   TEXT
);

-- Genel ödev değerlendirme gönderimleri (Yetenek 14)
CREATE TABLE IF NOT EXISTS essay_submissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    chapter_id  INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    prompt      TEXT NOT NULL,
    user_text   TEXT NOT NULL,
    grade_json  TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Öğrenme alışkanlıkları — streak/günlük hedef için etkinlik sayacı (Yetenek 15)
CREATE TABLE IF NOT EXISTS activity_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date      TEXT NOT NULL,
    kind      TEXT NOT NULL CHECK (kind IN ('note', 'quiz', 'flashcard', 'chat')),
    count     INTEGER NOT NULL DEFAULT 1,
    course_id INTEGER
);

-- İndeksleme işi türü: 'index' (mevcut) | 'transcribe' (ses/youtube → sonra index zincirlenir)
ALTER TABLE indexing_jobs ADD COLUMN kind TEXT NOT NULL DEFAULT 'index';

CREATE INDEX IF NOT EXISTS idx_flashcard_sets_course     ON flashcard_sets(course_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_chapter    ON flashcard_sets(chapter_id);
CREATE INDEX IF NOT EXISTS idx_card_reviews_due          ON card_reviews(due_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_course      ON chat_messages(course_id);
CREATE INDEX IF NOT EXISTS idx_study_guides_course       ON study_guides(course_id);
CREATE INDEX IF NOT EXISTS idx_essay_submissions_course  ON essay_submissions(course_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_date         ON activity_log(date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_activity_day_kind_course
    ON activity_log(date, kind, COALESCE(course_id, 0));
