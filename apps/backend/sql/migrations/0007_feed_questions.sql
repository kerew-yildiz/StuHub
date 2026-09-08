-- 0007: feed_questions tablosu — sonsuz kaydırma quiz feed'inin sunucu havuzu (Plan #feed).
-- Idempotent: tüm DDL CREATE ... IF NOT EXISTS.
--
-- Amaç: feed isteği anında LLM ÇAĞRILMAZ. Sorular önceden üretilip bu havuza yazılır,
-- istek tek SQL ile havuzdan servis edilir. Havuz hedefin (feed_service.TARGET_POOL)
-- altına inince arka planda doldurulur.
--
-- Yaşam döngüsü: satır `served_at IS NULL` doğar (havuzda bekler) → servis edilince
-- `served_at` damgalanır (bir daha servis edilmez) → cevaplanınca/atlanınca
-- `consumed_at` damgalanır. İki kolon ayrı tutulur: servis edilip cevaplanmayan soru
-- (kullanıcı sekmeyi kapattı) `served_at` dolu / `consumed_at` boş kalır, böylece
-- "kaç soru gerçekten tüketildi" ölçülebilir.
--
-- `origin_question_id` TEXT: kaynak quiz sorusunun kararlı kimliği
-- '<quizzes.id>:<topic_idx>-<q_idx>' — qid biçimi routers/quizzes.py `_flatten` ile
-- birebir aynıdır. Aynı quiz sorusunun havuza iki kez kopyalanması UNIQUE indeksle
-- engellenir (NULL değerler hem SQLite hem Postgres'te tekrarlanabilir).
-- Cevap kaydı bu kimlik üzerinden `quiz_attempts`'a yazılır (hata günlüğü + ısı
-- haritası mevcut sorgularıyla feed cevaplarını da görür).
--
-- `source`: 'generated' = feed için LLM ile üretilmiş parti, 'existing' = kullanıcının
-- daha önce ürettiği bölüm quizinden kopyalanmış soru.

CREATE TABLE IF NOT EXISTS feed_questions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id          TEXT NOT NULL DEFAULT 'local',
    course_id          INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    chapter_id         INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    topic              TEXT,
    question           TEXT NOT NULL,
    options_json       TEXT NOT NULL,
    correct_index      INTEGER NOT NULL,
    explanation        TEXT NOT NULL DEFAULT '',
    citations_json     TEXT,
    difficulty         TEXT,
    source             TEXT NOT NULL DEFAULT 'generated'
                       CHECK (source IN ('generated', 'existing')),
    origin_question_id TEXT,
    served_at          TIMESTAMP,
    consumed_at        TIMESTAMP,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feed_questions_serve
    ON feed_questions(tenant_id, course_id, served_at);
CREATE INDEX IF NOT EXISTS idx_feed_questions_consume
    ON feed_questions(tenant_id, course_id, consumed_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_feed_questions_origin
    ON feed_questions(tenant_id, course_id, origin_question_id);
