# ruff: noqa: E501 — prompt şablonları doğal dil metnidir
"""Genel quiz üretim + açık uçlu puanlama prompt'ları (Yetenek 04/05)."""

OVERALL_BATCH_PROMPT = """Aşağıdaki ders notu parçalarından "{category}" türünde TAM {count} soru üret.

KURALLAR:
1. Sorular SADECE sağlanan not parçaları ve ATIF LİSTESİ'ndeki kaynaklardan üretilecek; atıfsız soru üretme.
2. Konular verilen DAĞILIM PLANI'na göre dengeli dağılacak.
3. Her soru kendi tip şemasına birebir uyacak.
4. MCQ/TF/FIB için doğru/yanlış geribildirim metinleri üretimde hazırlanacak; yanlış geribildirimi atıflı açıklama içerecek.
5. FIB sorularına kabul edilen cevap listesi (accepted_answers) eklenecek — eş anlamlılar ve yaygın yazım varyantları dahil (interaksiyonda LLM çağrısı yapılmaz).
6. Açık uçlu sorulara saklı cevap anahtarı (answer_key: points listesi + citations) yazılacak.
7. Yalnızca JSON döndür: {{"category": "{category}", "questions": [ ... ]}}
8. {dil_talimati}

TIP ŞEMALARI:
- mcq: {{"type": "mcq", "topic": "...", "question": "...", "options": ["","","",""], "correct_index": 0, "explanation": "...", "feedback_correct": "Doğru! ...", "feedback_wrong": "Doğru cevap: X. Açıklama: ...", "citations": [{{"id": 1}}]}}
- tf: {{"type": "tf", "topic": "...", "statement": "...", "answer": true, "explanation": "Açıklama (yanlışsa düzeltme dahil)", "feedback_correct": "...", "feedback_wrong": "...", "citations": [{{"id": 1}}]}}
- fib: {{"type": "fib", "topic": "...", "text": "... ____ ...", "accepted_answers": ["cevap", "eş anlamlı"], "explanation": "...", "feedback_correct": "Doğru! ...", "feedback_wrong": "Doğru cevap: ... Açıklama: ...", "citations": [{{"id": 1}}]}}
- open: {{"type": "open", "topic": "...", "question": "...", "answer_key": {{"points": ["anahtar nokta 1", "anahtar nokta 2"], "citations": [{{"id": 1}}]}}}}

DAĞILIM PLANI:
{distribution_plan}

NOT PARÇALARI:
{note_sections}

ATIF LİSTESİ:
{citations_json}
"""

ESSAY_GRADE_PROMPT = """Sen bir sınav değerlendiricisisin. Aşağıda bir soru, cevap anahtarı, kaynak parçaları ve öğrencinin cevabı var.

KURALLAR:
1. Puanı SADECE cevap anahtarına göre ver (0-10); anahtarda olmayan bilgi doğru sayılmaz, "unnecessary" kategorisine girer.
2. correct/missing/incorrect/unnecessary listelerini doldur; boş kategoriye "yok" yaz.
3. explanation alanında puanı gerekçelendir.
4. ideal_answer: anahtardan ve kaynaklardan tam bir örnek cevap yaz, atıfları [n] ile işaretle.
5. confidence: 0-1 arası puanlamaya güvenin.
6. Yalnızca JSON döndür: {{"score": 7, "correct": ["..."], "missing": ["..."], "incorrect": ["..."], "unnecessary": ["..."], "explanation": "...", "ideal_answer": "...", "confidence": 0.9}}

SORU: {question}
CEVAP ANAHTARI: {answer_key}
KAYNAKLAR:
{numbered_sources}
ÖĞRENCİ CEVABI: {user_answer}
"""
