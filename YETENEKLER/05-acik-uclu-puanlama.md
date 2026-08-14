# Yetenek 05 — Açık Uçlu Puanlama (Essay Grading)

> **Sahibi:** Essay Grader Ajanı (`AJANLAR/08-essay-grader-ajani.md`). Bu dosya, genel quiz'deki açık uçlu cevapların objektif puanlama sözleşmesidir.

## Amaç
Kullanıcının açık uçlu cevabını saklı cevap anahtarına göre **10 üzerinden objektif** puanlamak; doğru, eksik, yanlış ve gereksiz kısımları bildirip açıklamak; ardından **ideal örnek cevap** hazırlamak.

## Girdiler
- Soru gövdesi + `answer_key` (üretim anında saklanmış: anahtar noktalar + atıflar)
- İlgili kaynak chunk'lar
- Kullanıcı cevabı

## Adım Adım İş Akışı

### 1. Bağlam toplama
- Soru + cevap anahtarı + kaynak chunk'lar + kullanıcı cevabı tek prompt'a hazırlanır.

### 2. Rubrik ile puanlama
- 10 puanlık rubrik; puan, anahtar noktaların karşılanma oranına dayanır:
  - Anahtar noktaların tamamı + doğru bağlantılar → 9-10
  - Çoğu nokta, küçük eksik → 7-8
  - Kısmi kapsama → 5-6
  - Ciddi eksik/yanlış karışımı → 3-4
  - Konuya temas var ama çoğunlukla yanlış → 1-2
  - Alakasız/boş → 0
- Few-shot örnekler prompt'a gömülüdür (tutarlılık için).

### 3. Dört kategorili analiz
- **correct[]:** anahtarla eşleşen doğru ifadeler
- **missing[]:** anahtarda olup cevapta olmayan noktalar
- **incorrect[]:** cevapta olup kaynaklarla çelişen ifadeler
- **unnecessary[]:** materyal/anahtar dışı veya soruyla ilgisiz içerik
- Her kategori ya dolu liste ya da açık "yok" işareti taşır; `explanation` puanı gerekçelendirir.

### 4. Güven kontrolü (objektiflik garantisi)
- Puanlama çıktısı ile cevap anahtarı çapraz doğrulanır (anahtarda olmayan bir noktanın `correct`'e yazılıp yazılmadığı denetlenir).
- `confidence` düşükse veya tutarsızlık varsa **yeniden değerlendirme** (tek ek çağrı); ikinci sonuç kesindir.

### 5. İdeal cevap üretimi
- Anahtar noktalardan + kaynak chunk'lardan, inline atıflı örnek ideal cevap yazılır; kullanıcıya analizden sonra gösterilir.

### 6. Kayıt
- `overall_attempts.score_json` güncellenir; `generation_logs` yazılır.

## Çıktı JSON Şeması

```json
{
  "score": 7,
  "correct": ["..."],
  "missing": ["..."],
  "incorrect": ["..."],
  "unnecessary": ["..."],
  "explanation": "Puanın gerekçesi...",
  "ideal_answer": "İdeal cevap [1] atıflı metin...",
  "confidence": 0.9
}
```

## Prompt Şablonu (taslak)

```
Sen bir sınav değerlendiricisisin. Aşağıda bir soru, cevap anahtarı, kaynak parçaları ve öğrencinin cevabı var.

KURALLAR:
1. Puanı SADECE cevap anahtarına göre ver (0-10); anahtarda olmayan bilgi doğru sayılmaz, "gereksiz" kategorisine girer.
2. correct/missing/incorrect/unnecessary listelerini doldur; boş kalan kategoriye "yok" yaz.
3. explanation alanında puanı gerekçelendir.
4. ideal_answer: anahtardan ve kaynaklardan tam bir örnek cevap yaz, atıfları [n] ile işaretle.
5. JSON şemasına birebir uy.

SORU: {question}
CEVAP ANAHTARI: {answer_key}
KAYNAKLAR: [1] ... [2] ...
ÖĞRENCİ CEVABI: {user_answer}
```

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Şema ihlali | Yeniden değerlendirme (1 kez) |
| Düşük güven | Yeniden değerlendirme; ikinci sonuç kesin |
| Boş cevap | score=0; missing=anahtarın tamamı; açıklama rehberlik eder |
| Anahtar eksik (eski quiz kaydı) | Anahtar üretilir (kaynaklardan), sonra puanlanır |

## Kabul Kriterleri
- Puan anahtara dayalı ve gerekçeli; dört kategori eksiksiz
- İdeal cevap atıflı
- `generation_logs` kaydı mevcut
- Aynı cevabın iki puanlaması arasında tutarlılık hedefi: ±1 puan (Değerlendirme Ajanı ölçer)
