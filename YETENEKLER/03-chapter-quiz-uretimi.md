# Yetenek 03 — Chapter Quiz Üretimi

> **Sahibi:** Chapter Quiz Ajanı (`AJANLAR/06-chapter-quiz-ajani.md`). Bu dosya, bölüm quizi üretim hattının sözleşmesidir.

## Amaç
Üretilen notları tarayıp konuları saptamak; her konu için **5 çoktan seçmeli soru** üretmek; her soruyu gerçek bir kaynağa atıflandırmak; anlık geribildirim metinlerini üretim anında hazırlamak.

## Girdiler
- Chapter notu: `content_md`, `topics_json`, `citations_json`
- Kaynak chunk'lar (`citations_ledger` üzerinden)

## Adım Adım İş Akışı

### 1. Konu segmentasyonu
- `topics_json` + markdown başlık yapısı; çelişirse başlık yapısı esas.
- Her konu için not bölümü + o bölümün atıf listesi ayrılır.

### 2. Soru üretimi (konu başına)
- Konu başına tek LLM çağrısı ile tam 5 MCQ üretilir (JSON şeması zorunlu).
- Her soru: `topic, question, options[4], correct_index, explanation, citations[]`.
- `citations[]` yalnızca o konunun atıf listesindeki gerçek kaynaklardan seçilir.

### 3. Çeldirici denetimi
- 4 seçenek: biri doğru, üçü aynı kaynaklardan türetilmiş makul çeldirici; komik/bariz yanlış yasak.
- Doğru cevap index dağılımı dengeli (aynı şık en fazla 2 kez doğru olabilir).

### 4. Geribildirim şablonları (üretim anında hazırlanır)
- **Doğru:** kısa onay + konunun pekiştirme cümlesi ("Doğru! ...").
- **Yanlış:** "Doğru cevap: <X>. Açıklama: ... [kaynak: [1] sayfa 41 / [2] slide 3]" — açıklama materyale atıfla bağlanır.
- Feedback metinleri soru JSON'una gömülür; kullanıcı cevap verdiğinde **ek LLM çağrısı yapılmaz**.

### 5. Atıf doğrulama
- `YETENEKLER/06-atif-sistemi.md` adımı; atıfsız soru = geçersiz üretim.

### 6. Kayıt
- `quizzes` kaydı (konu bazlı gruplu `questions_json` — üst zarf şeması aşağıda); `generation_logs` yazılır.

## Soru JSON Şeması (tek soru)

```json
{
  "topic": "Hücre zarı yapısı",
  "question": "Fosfolipid çift katmanın temel özelliği nedir?",
  "options": ["...", "...", "...", "..."],
  "correct_index": 1,
  "explanation": "Doğru cevap: ... Açıklama: ...",
  "feedback_correct": "Doğru! ...",
  "feedback_wrong": "Doğru cevap: ... Açıklama: ...",
  "citations": [
    { "id": 1, "source_type": "textbook", "source_id": 12, "page": 41 }
  ]
}
```

## Üst Zarf (Envelope) Şeması — konu batch'i

```json
{ "topic": "Hücre zarı yapısı", "questions": [ <5 mcq objesi> ] }
```

- Her LLM çağrısı TAM 5 soruluk bu zarfı döner; `json_schema enforced` bu zarfa uygulanır.
- `quizzes.questions_json` bu zarfların konu sıralı birleşimidir: `{ "topics": [ { "topic": "...", "questions": [...] }, ... ] }`.

## Prompt Şablonu (taslak)

```
Aşağıdaki ders notu bölümünden [KONU] hakkında TAM 5 çoktan seçmeli soru üret.

KURALLAR:
1. Sorular SADECE sağlanan not bölümü ve atıf listesindeki kaynaklardan üretilecek.
2. Her sorunun 4 seçeneği olacak; çeldiriciler makul ve aynı kaynaklardan türetilmiş olacak.
3. Her soru en az bir atıf taşıyacak (citations alanı).
4. Doğru/yanlış geribildirim metinlerini yaz; yanlış geribildirimi atıflı açıklama içerecek.
5. JSON şemasına birebir uy.

NOT BÖLÜMÜ: {note_section}
ATIF LİSTESİ: {citations_json}
```

## Hata Modları
| Durum | Davranış |
|-------|----------|
| 5'ten az/çok soru üretildi | Batch yeniden üretilir (max 2 deneme), sonra kullanıcıya hata |
| Şema ihlali | Batch reddedilir, yeniden üretilir |
| Atıfsız soru | Soru atılır; konu için yeniden üretim |
| Notta konu bulunamadı | "Önce not oluştur" rehber mesajı |

## Kabul Kriterleri
- Her konu için tam 5 şema-geçerli MCQ; tümü atıflı
- Feedback metinleri soruyla birlikte kayıtlı (interaksiyonda LLM çağrısı yok)
- Doğru cevap dağılımı dengeli
