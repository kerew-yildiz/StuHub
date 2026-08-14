# Yetenek 09 — Flashcard Üretimi ve Uzamsal Tekrar (SM-2)

> **Sahibi:** Flashcard Ajanı (`AJANLAR/15-flashcard-ajani.md`). Bu dosya, flashcard üretim hattı ile yerel SM-2 tekrar zamanlamasının sözleşmesidir.

## Amaç
Chapter notlarından ve quiz verilerinden **atıflı** flashcard'lar üretmek; kart tekrarını yerel, deterministik bir SM-2 varyantıyla zamanlamak (Again/Hard/Good/Easy dörtlüsü).

## Girdiler
- Chapter notu: `content_md`, `topics_json`, `citations_json`
- Quiz verileri: chapter/genel `questions_json` (soru-cevap kartı türetimi için)
- Kaynak chunk'lar (`citations_ledger` üzerinden)
- Model: DeepSeek chat API (JSON modu — `chat_json`)

## Adım Adım İş Akışı

### 1. Kart kaynağı toplama
- Not `content_md` + `topics_json` (anahtar terim kaynağı) + quiz `questions_json` (soru-cevap kaynağı).
- İki kart tipi üretilir:
  - `type: "qa"` — soru-cevap kartı (quiz sorularından ve nottan türetilen "soru → cevap" çiftleri).
  - `type: "term"` — anahtar terim kartı (`topics_json.keywords` + nottaki tanımlardan "terim → tanım").

### 2. Konu başına map-reduce üretim
- **Her konu ayrı `chat_json` çağrısıdır** (tek dev çağrı yasak; `json_schema enforced`).
- Çağrı başına `cards[]` zarfı döner; konu başına 5–15 kart hedefi.
- Boş üretim (0 kart) yeniden denenir (max 2).

### 3. Atıf doğrulama
- Her kartın `citations[]` listesi **yalnızca o konunun `citations_json` kaynaklarından** seçilir.
- `YETENEKLER/06-atif-sistemi.md` doğrulaması çalıştırılır; **atıfsız kart reddedilir**.

### 4. Kayıt
- `flashcards` kaydı: `course_id`, `chapter_id`, `topic`, `front`, `back`, `type`, `citations_json`.
- `generation_logs` kind=`flashcard`.

### 5. SM-2 tekrar (runtime, yerel)
- Kullanıcı kartı çevirip **Again / Hard / Good / Easy** seçer; kart durumu deterministik güncellenir (Bölüm "SM-2 Kuralları").
- `due_at = now + interval_days`; due kuyruğu **kurs bazlıdır** ve **vadesi geçen kart önce** sunulur.

## Veri Formatları

Kart şeması:
```json
{
  "topic": "Hücre zarı yapısı",
  "front": "Fosfolipid çift katmanın temel işlevi nedir?",
  "back": "Hücreyi dış ortamdan ayırır; seçici geçirgen bariyer oluşturur.",
  "type": "qa",
  "citations": [
    { "id": 1, "source_type": "textbook", "source_id": 12, "page": 41, "chunk_id": "chk_12_41_1", "quote": "..." }
  ]
}
```

SM-2 kart durumu:
```json
{
  "card_id": 1,
  "ease_factor": 2.5,
  "interval_days": 1,
  "repetitions": 0,
  "due_at": "2026-08-15T09:00:00Z"
}
```

## SM-2 Kuralları (deterministik saf fonksiyon)

| Buton | Kalite | ease_factor delta | interval_days (sonraki) | repetitions |
|-------|--------|-------------------|--------------------------|-------------|
| Again | 1 | **-0.2** | 1 (sıfırlanır) | 0 |
| Hard  | 3 | **-0.15** | 0→1, 1→6, değilse `×1.2` | +1 |
| Good  | 4 | **+0.1** | 0→1, 1→6, değilse `×ease_factor` | +1 |
| Easy  | 5 | **+0.1** | 0→4, değilse `×ease_factor×1.3` | +1 |

- `ease_factor` aralığı **[1.3, 2.5]** (alt/üst sınırda kırpılır).
- `interval_days` tavanı **365**; başarısız (Again) her zaman 1'e döner.
- `due_at = now + interval_days` (gün bazlı, UTC).
- SM-2 **saf fonksiyondur**: aynı `(durum, buton)` girdisi her zaman aynı çıktıyı verir (saat/zaman bağımlılığı `due_at` dışında yoktur); birim testlidir.

## Prompt Şablonu (üretim — taslak)

```
Aşağıda bir ders notunun [KONU] bölümü, anahtar terimleri ve quiz soruları var.

KURALLAR:
1. SADECE sağlanan not bölümü ve kaynaklardan kart üret; kaynaklarda olmayan bilgi EKLEME.
2. İki tip kart üret: "qa" (soru→cevap) ve "term" (terim→tanım).
3. Her kart en az bir atıf taşıyacak (citations alanı); atıf yalnızca verilen atıf listesinden seçilecek.
4. Kart cümleleri kısa, net, öğrenci seviyesinde Türkçe olacak.
5. JSON şemasına birebir uy.

NOT BÖLÜMÜ: {note_section}
ANAHTAR TERİMLER: {keywords}
QUIZ SORULARI: {questions}
ATIF LİSTESİ: {citations_json}
```

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Atıfsız kart | Kart reddedilir; konu yeniden üretilir (max 2) |
| Boş üretim (0 kart) | Yeniden deneme (max 2); sonra konu "kart üretilemedi" işaretlenir |
| JSON şema ihlali | `_extract_json` onarımı (fence sıyırma/ayıklama); başarısızsa yeniden üretim |
| Yinelenen kart çifti | `front` normalize edilip çiftler ayıklanır (dedup) |
| Quiz yok + notta yeterli soru/terim yok | Sadece mevcut kaynaktan üretilir; boşsa kullanıcıya "önce not/quiz oluştur" mesajı |

## Kabul Kriterleri
- Tüm kartlar atıflı; kart şeması (`type: qa|term` + `citations[]`) geçerli
- Üretim map-reduce yapılmış (tek çağrı kanıtı yok)
- SM-2 saf fonksiyon + deterministik (birim testli: aynı girdi → aynı çıktı)
- Due kuyruğu kurs bazlı; vadesi geçen önce
- `generation_logs` kind=`flashcard` kaydı mevcut
