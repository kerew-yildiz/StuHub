# Yetenek 14 — Genel Ödev (Essay) Değerlendirme

> **Sahibi:** Essay Grader Ajanı (`AJANLAR/08-essay-grader-ajani.md` — v2'de genişletilmiş kapsam: açık uçlu quiz puanlaması + genel ödev değerlendirme). Bu dosya, serbest metin ödev değerlendirme sözleşmesidir; **`YETENEKLER/05-acik-uclu-puanlama.md`'yi temel alır** (aynı makine: rubrik + güven kontrolü + yeniden değerlendirme).

## Amaç
Kullanıcının yazdığı serbest metin ödevi (essay/kompozisyon/rapor) 0–100 aralığında, ölçüt bazlı ve gerekçeli olarak değerlendirmek; güçlü/zayıf yönleri ve satır içi alıntı yorumlarını bildirmek.

## Girdiler
- `{ "prompt": "...", "rubric": null, "user_text": "..." }` (rubrik opsiyonel)
- Model: DeepSeek chat API (JSON modu)

## Adım Adım İş Akışı

### 1. Rubrik çözümü
- `rubric` verilmemişse **varsayılan ölçütler** kullanılır:
  1. İçerik doğruluğu
  2. Argüman yapısı
  3. Kapsam (prompt'a uygunluk)
  4. Dil/anlatım
  5. Kaynak kullanımı
- Ölçütlerin `max` puanları toplamı 100 olacak şekilde ağırlıklandırılır.

### 2. Puanlama (0–100)
- Çıktı şeması:
  ```json
  {
    "score": 72,
    "criteria": [
      { "name": "İçerik doğruluğu", "score": 18, "max": 20, "comment": "..." }
    ],
    "strengths": ["..."],
    "weaknesses": ["..."],
    "quotes": [ { "text": "metinden alıntı", "comment": "..." } ],
    "confidence": 0.85
  }
  ```
- `criteria[].score` toplamı `score`'a eşit olmalıdır (tutarlılık denetimi).

### 3. Boş metin (deterministik)
- `user_text` boş/yalnız boşluk ise LLM çağrısı yapılmaz; `score=0`, her ölçüt 0, `weaknesses` rehberlik eder, `confidence=1.0`.

### 4. Güven kontrolü
- `confidence` eşiğin altındaysa veya şema/toplam tutarsızlığı varsa **tek yeniden değerlendirme**; ikinci sonuç kesindir.

### 5. Kayıt
- `essay_submissions` kaydı (prompt + metin + sonuç JSON).
- `generation_logs` kind=`essay_grade`.

## 05 ile İlişki (çapraz referans)

| Yetenek | Kapsam | Ölçek | Kaynak |
|---------|--------|-------|--------|
| `05-acik-uclu-puanlama.md` | Quiz açık uçlu cevaplar | 0–10; cevap anahtarına göre | Soru `answer_key` + kaynak chunk'lar |
| `14-essay-degerlendirme.md` | Genel ödev/essay | 0–100; rubrik/ölçütlere göre | `prompt` + (opsiyonel) rubrik |

- Aynı makine paylaşılır: ölçüt bazlı puan + güven kontrolü + tek yeniden değerlendirme.
- Quiz açık uçlu puanlaması `05`'te kalır; genel ödev akışı `14`'tedir.

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Boş metin | Deterministik 0 (LLM yok) |
| `criteria` toplamı ≠ `score` | Yeniden değerlendirme (1 kez) |
| Düşük güven | Yeniden değerlendirme; ikinci sonuç kesin |
| Şema ihlali | `_extract_json` onarımı; başarısızsa yeniden üretim |
| Rubrik bozuk/geçersiz | Varsayılan ölçütlere düşülür |

## Kabul Kriterleri
- 0–100 puan; ölçüt bazlı ve gerekçeli; `criteria` toplamı `score`'a eşit
- Boş metin deterministik; güven eşiği altında tek yeniden değerlendirme
- `essay_submissions` kaydı + `generation_logs` kind=`essay_grade`
