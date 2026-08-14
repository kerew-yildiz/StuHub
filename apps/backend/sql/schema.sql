-- StuHub DS — SQLite şeması (Faz 0.2)
-- Kaynak: PROJE_YOL_HARITASI.md Bölüm 3 (tek doğruluk kaynağı).
-- Idempotent: CREATE TABLE IF NOT EXISTS — init_db her açılışta güvenle uygular.
-- Migration politikası: sql/migrations/README.md

PRAGMA foreign_keys = ON;

-- Dönem klasörleri (ör. "2026 Bahar")
CREATE TABLE IF NOT EXISTS terms (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    start_date TEXT,
    end_date   TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Dersler (bir dönem altında)
CREATE TABLE IF NOT EXISTS courses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id       INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    instructor    TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Materyaller: ders kitabı PDF'i, hoca sunumu ya da v2 medya türleri
-- (youtube, audio, docx, epub, image, text — YETENEKLER/11-medya-alimi.md)
CREATE TABLE IF NOT EXISTS materials (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id      INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    type           TEXT NOT NULL CHECK (type IN ('textbook', 'slides', 'youtube', 'audio', 'docx', 'epub', 'image', 'text')),
    filepath       TEXT NOT NULL,
    extracted_text TEXT,
    page_count     INTEGER,
    vector_ns      TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Chapter'lar (ders içi bölümler)
CREATE TABLE IF NOT EXISTS chapters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id  INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Slide bazlı atıf granülaritesi (Faz 2)
CREATE TABLE IF NOT EXISTS slides (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id   INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    material_id  INTEGER REFERENCES materials(id) ON DELETE SET NULL,
    slide_no     INTEGER NOT NULL,
    content_text TEXT
);

-- Üretilen notlar (markdown + atıf/topic JSON'ları)
CREATE TABLE IF NOT EXISTS notes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id     INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    content_md     TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    topics_json    TEXT NOT NULL DEFAULT '[]',
    generated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_used     TEXT
);

-- Quiz'ler (sorular denormalize JSON; v4.3: type kaldırıldı)
CREATE TABLE IF NOT EXISTS quizzes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id     INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    questions_json TEXT NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id           INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    user_answers_json TEXT NOT NULL,
    score             REAL,
    feedback_json     TEXT,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS overall_quizzes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id      INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    questions_json TEXT NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS overall_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    overall_quiz_id INTEGER NOT NULL REFERENCES overall_quizzes(id) ON DELETE CASCADE,
    answers_json    TEXT NOT NULL,
    score_json      TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Vektör indeksleme işleri (arka plan, Faz 2.2)
-- kind: 'index' (çıkarım+embed) | 'transcribe' (v2: ses/youtube → transkript, ardından index zincirlenir)
CREATE TABLE IF NOT EXISTS indexing_jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    progress    REAL NOT NULL DEFAULT 0,
    error       TEXT,
    kind        TEXT NOT NULL DEFAULT 'index',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Atıf defteri (chunk → kaynak eşlemesi; doğrulama Faz 3+)
CREATE TABLE IF NOT EXISTS citations_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id    TEXT,
    text        TEXT,
    source_type TEXT,
    source_id   INTEGER,
    page        INTEGER,
    slide       INTEGER
);

-- LLM çağrı günlüğü (maliyet gözetimi — Ücretsizlik Ajanı denetimi)
CREATE TABLE IF NOT EXISTS generation_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    kind              TEXT NOT NULL,
    course_id         INTEGER,
    chapter_id        INTEGER,
    model             TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Anahtar/değer ayarları (API anahtarı, model adı vb. — yerel, commit dışı)
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ── v2 tabloları (Niş Analizi Entegrasyonu — migration 0002 ile de kurulur) ──

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

-- Uygulanan şema migration'larının kaydı (db.py migration runner'ı)
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Sık sorgu indeksleri
CREATE INDEX IF NOT EXISTS idx_courses_term        ON courses(term_id);
CREATE INDEX IF NOT EXISTS idx_materials_course    ON materials(course_id);
CREATE INDEX IF NOT EXISTS idx_chapters_course     ON chapters(course_id);
CREATE INDEX IF NOT EXISTS idx_slides_chapter      ON slides(chapter_id);
CREATE INDEX IF NOT EXISTS idx_notes_chapter       ON notes(chapter_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_chapter     ON quizzes(chapter_id);
CREATE INDEX IF NOT EXISTS idx_overall_quizzes_course ON overall_quizzes(course_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_course     ON flashcard_sets(course_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_chapter    ON flashcard_sets(chapter_id);
CREATE INDEX IF NOT EXISTS idx_card_reviews_due          ON card_reviews(due_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_course      ON chat_messages(course_id);
CREATE INDEX IF NOT EXISTS idx_study_guides_course       ON study_guides(course_id);
CREATE INDEX IF NOT EXISTS idx_essay_submissions_course  ON essay_submissions(course_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_date         ON activity_log(date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_activity_day_kind_course
    ON activity_log(date, kind, COALESCE(course_id, 0));
