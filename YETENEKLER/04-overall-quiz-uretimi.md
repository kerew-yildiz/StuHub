# Yetenek 04 — Overall Quiz Üretimi

> **Sahibi:** Overall Quiz Ajanı (`AJANLAR/07-overall-quiz-ajani.md`). Bu dosya, ders seviyesindeki 50 soruluk genel quiz üretim hattının sözleşmesidir.

## Amaç
Dersin tüm chapter notlarından **15 çoktan seçmeli + 15 doğru-yanlış + 15 boşluk doldurma + 5 açık uçlu = 50 soru** üretmek; konuları chapter'lar boyunca dengeli dağıtmak; soruları **karışık sırayla** sunmak; açık uçlu sorular için saklı cevap anahtarı tutmak.

## Girdiler
- Dersin tüm chapter notları + atıfları
- Seed (karıştırma determinizmi için)

## Adım Adım İş Akışı

### 1. Konu havuzu ve stratifikasyon
- Tüm notlardan konu listesi çıkar; chapter'lar arası dengeli temsil planı yap (her chapter'ın soru payı, konu sayısıyla orantılı).
- Açık uçlu 5 soru: en kapsamlı/önemli konulardan seçilir.

### 2. Batch üretim (tek çağrıda 50 soru YASAK — output limiti)
- Kategori bazlı batch'ler: MCQ (3 batch × 5), TF (2 batch: 8+7), FIB (3 batch × 5), açık uçlu (1 batch × 5).
- Her batch, üst zarf şemasına (`category` + `questions`) göre doğrulanır; başarısız batch yeniden üretilir (max 2 deneme).

### 3. Kategori kuralları
- **MCQ:** `03-chapter-quiz-uretimi.md` şeması + aynı feedback kuralları; konular chapter'lar arası karışık.
- **Doğru-Yanlış:** her soru açık atıflı; yanlış ifadenin düzeltmesi `explanation` içinde; dağılım dengeli (7-8 doğru / 8-7 yanlış).
- **Boşluk doldurma:** boşluk `____` ile gösterilir; `accepted_answers[]` listesi + normalizasyon kuralı; cevap tek kelime/kısa ifade olmalı.
- **Açık uçlu:** soru + saklı `answer_key` (anahtar noktalar listesi + atıflar) + rubrik; puanlama Essay Grader Ajanı'nda (`05-acik-uclu-puanlama.md`).

### 4. FIB eşleştirme (runtime, kullanıcı cevabında)
- Normalizasyon: Türkçe küçük harf, noktalama temizliği, fazla boşluk silme, `i/ı` hassas korunur.
- `accepted_answers` ile eşleşme → doğru; listede olmayan cevap yanlış sayılır (eşleşme tamamen **deterministiktir**).
- Kabul listesi **üretim anında** genişletilir: LLM, her FIB için eş anlamlıları ve yaygın yazım varyantlarını üretim sırasında `accepted_answers`'a ekler — **interaksiyon anında LLM çağrısı YAPILMAZ** ("anında geribildirim" sözleşmesi).
- Feedback: doğru/yanlış her durumda atıflı açıklama (ilk üç kategoride aynı interaktif sistem); feedback metinleri üretim anında hazırlanır.

### 5. Birleştirme ve karıştırma
- 50 soru tek dizide toplanır; **seed'li karıştırma** (aynı quiz tekrarında aynı sıra; yeni denemede yeni seed).
- Soru tipleri karışık sunulur; kategori blokları korunmaz.

### 6. Doğrulama ve kayıt
- Dağılım 15/15/15/5 birebir doğrulanır; sapma = üretim geçersiz.
- Tüm atıflar `06-atif-sistemi.md` doğrulamasından geçer.
- `overall_quizzes` kaydı; açık uçlu `answer_key` yalnızca backend'de saklanır, frontend'e gitmez.

## Soru Tipleri JSON Şemaları

```json
// MCQ (chapter şemasıyla aynı) — tip: "mcq"
// Doğru-Yanlış — tip: "tf"
{ "topic": "...", "statement": "...", "answer": true,
  "explanation": "Açıklama (yanlışsa düzeltme dahil)",
  "feedback_correct": "...", "feedback_wrong": "...",
  "citations": [{ "id": 1, "source_type": "textbook", "source_id": 12, "page": 41 }] }

// Boşluk doldurma — tip: "fib"
{ "topic": "...", "text": "... ____ ...", "accepted_answers": ["hücre zarı", "plazma zarı"],
  "explanation": "...", "feedback_correct": "Doğru! ...", "feedback_wrong": "Doğru cevap: ... Açıklama: ...",
  "citations": [...] }

// Açık uçlu — tip: "open"
{ "topic": "...", "question": "...", "answer_key": { "points": ["...", "..."], "citations": [...] } }
```

## Üst Zarf (Envelope) Şemaları

Batch üretim zarfı (her LLM çağrısı bu zarfı döner; `json_schema enforced`):
```json
{ "category": "mcq|tf|fib|open", "questions": [ ... ] }
```

Nihai quiz kaydı (`overall_quizzes.questions_json`):
```json
{
  "seed": 1234,
  "questions": [
    { "type": "mcq", ... },
    { "type": "tf", ... },
    { "type": "fib", ... },
    { "type": "open", "question": "...", "answer_key_ref": "oq_7" }
  ]
}
```
- Her soru `type` alanı taşır; karıştırma sonrası sıra bu dizidedir.
- Açık uçlu `answer_key` ayrı tabloda/alandadır ve **frontend'e hiçbir rotada gitmez** (`answer_key_ref` yalnızca backend içindir).

## Prompt Şablonu (batch çağrısı — taslak)

```
Aşağıdaki ders notu parçalarından [KATEGORİ] türünde TAM N soru üret (MCQ/TF: 5, FIB: 5, açık uçlu: 5).

KURALLAR:
1. Sorular SADECE sağlanan not parçaları ve atıf listesinden üretilecek; atıfsız soru üretme.
2. Konular chapter'lar arası dengeli dağılacak; verilen dağılım planına uyulacak.
3. Her soru kendi tip şemasına birebir uyacak (mcq/tf/fib/open).
4. MCQ/TF/FIB için doğru/yanlış geribildirim metinleri üretimde hazırlanacak; yanlış geribildirimi atıflı açıklama içerecek.
5. FIB sorularına kabul edilen cevap listesi (accepted_answers) eklenecek — eş anlamlılar ve yaygın yazım varyantları dahil (interaksiyonda LLM çağrısı yapılmaz).
6. Açık uçlu sorulara saklı cevap anahtarı (answer_key) yazılacak.

DAĞILIM PLANI: {distribution_plan}
NOT PARÇALARI: {note_sections_with_citations}
```

**Not:** Batch başına 5–10 soru; çıktı JSON olarak validate edilir, başarısız batch max 2 kez yeniden üretilir.

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Batch şema ihlali | Yeniden üretim (max 2), sonra kullanıcıya hata |
| Dağılım sapması | Eksik kategori için ek batch; fazlalık atılır |
| FIB kabul listesi boş | Soru geçersiz sayılır, yeniden üretilir |
| Output token aşımı | Batch boyutu 5'e düşürülür |
| LLM kesintisi | Tamamlanan batch'ler korunur; kaldığı kategoriden devam |

## Kabul Kriterleri
- 50 soru; dağılım 15/15/15/5 birebir
- Seed'li karışık sıra; kategori blokları yok
- Tüm MCQ/TF/FIB soruları atıflı; feedback üretim anında hazır
- Açık uçlu `answer_key`'ler frontend'e sızmaz (API şeması ile kanıtlanır)
