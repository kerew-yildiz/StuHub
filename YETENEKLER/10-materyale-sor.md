# Yetenek 10 — Materyale Sor (RAG Chat)

> **Sahibi:** Materyale Sor Ajanı (`AJANLAR/16-materyale-sor-ajani.md`). Bu dosya, kurs materyaline karşı atıflı sohbet (RAG chat) sözleşmesidir.

## Amaç
Kullanıcı sorusunu dersin indeksli materyaline karşı **numaralı, tıklanabilir atıflarla** yanıtlamak; yanıtın yalnızca sağlanan kaynak parçalarına dayanmasını garanti etmek.

## Girdiler
- Kullanıcı sorusu + `course_id` + `mode` (direct|socratic|quiz)
- `retrieval.hybrid_search(course_id, query)` çıktısı (chunk kümesi)
- Geçmiş `chat_messages` (mode dahil)
- Model: DeepSeek chat API (SSE stream)

## Adım Adım İş Akışı

### 1. Retrieval
- `retrieval.hybrid_search(course_id, query)`: **0.7 vektör + 0.3 keyword** (mevcut hibrit skor).
- Kaynaklar sıralı numaralanır `[1]..[n]`; etiket kaynak tipine göre: `sayfa <p>` / `slide <s>` / `dakika <start>`.
- Context token bütçesi aşılırsa skora göre kırpılır (bütçe sözleşmesi aşağıda).

### 2. Mod seçimi
- `direct`: doğrudan atıflı cevap.
- `socratic`: **cevap YOK**; ipucu + yönlendirici soru (doğrudan cevap vermez).
- `quiz`: model materyalden soru sorar; kullanıcı cevap verince **atıflı** değerlendirir (doğru/yanlış + açıklama + kaynak).

### 3. Yanıt üretimi (SSE stream)
- Prompt'a kaynak listesi + "SADECE sağlanan kaynak parçalarını kullan" kuralı gömülür.
- Retrieval boş dönerse LLM çağrısı **yapılmaz**; kullanıcıya "kaynak bulunamadı" mesajı döner.

### 4. Atıf kimliği doğrulama (deterministik)
- Yanıttaki her `[n]` işareti, verilen kimlik kümesinden (1..n) olmalıdır.
- **Tanımsız n → yanıt reddi + tek üretim** (yeniden deneme); ikinci ihlalde "kaynak bulunamadı/kısıtlı yanıt" fallback.

### 5. Kayıt
- `chat_messages` (soru + yanıt + `mode` + kullanılan kaynak kimlikleri).
- `generation_logs` kind=`chat`.

## Veri Formatları

Kaynak listesi (prompt'a giren):
```json
{
  "sources": [
    { "n": 1, "source_type": "textbook", "source_id": 12, "page": 41, "text": "..." },
    { "n": 2, "source_type": "slides", "source_id": 3, "slide": 7, "text": "..." },
    { "n": 3, "source_type": "audio", "source_id": 8, "segment": 5, "start": "00:12:30", "text": "..." }
  ]
}
```

`chat_messages` satırı:
```json
{
  "course_id": 1,
  "role": "assistant",
  "mode": "direct",
  "content": "Fosfolipid çift katman ... [1]",
  "sources": [1]
}
```

## Mod Davranış Tablosu

| Mod | Yanıt beklenir mi | Kaynak atıfı | Not |
|-----|------------------|--------------|-----|
| direct | Evet (cevap) | Zorunlu | Her bilgi `[n]` ile |
| socratic | Hayır (ipucu + soru) | İpucu atıflı olabilir | Doğrudan cevap YASAK |
| quiz | Model soru sorar | Değerlendirme atıflı | Kullanıcı cevabı atıflı değerlendirilir |

## Prompt Şablonu (taslak)

```
Sen bir ders materyali asistanısın. Aşağıda kullanıcı sorusu ve ders materyalinden alınan kaynak parçaları var.

KURALLAR:
1. SADECE sağlanan kaynak parçalarını kullan; kaynaklarda olmayan bilgi EKLEME.
2. Her bilgi parçasının sonuna kaynak atıf numarasını [n] biçiminde koy.
3. [n] numaraları yalnızca aşağıda verilen kaynak listesinden olacak; listede olmayan numara KULLANMA.
4. Mod: {mode} — mod kurallarına uy (socratic ise cevap verme, ipucu ver; quiz ise soru sor).
5. Türkçe, öğrenci seviyesinde, kısa paragraflar.

KAYNAKLAR:
[1] (sayfa 41) {text}
[2] (slide 7) {text}
...
SORU: {question}
```

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Retrieval boş | LLM çağrısı yapılmaz; "kaynak bulunamadı" mesajı |
| Tanımsız atıf kimliği (n ∉ 1..n) | Yanıt reddi + tek üretim; ikinci ihlalde fallback mesaj |
| Context token bütçesi aşımı | Skora göre kırpma (en düşük skorlu kaynak atılır) |
| Stream kesintisi | Kısmi yanıt kalıcılaştırılır; tamamlanmamışsa yeniden üretim |
| `mode` tanımsız/geçersiz | `direct` kabul edilir; geçmişe gerçek mode yazılır |

## Kabul Kriterleri
- Yanıttaki her `[n]` verilen kimliklerden (deterministik doğrulama; tanımsız n kabul edilmez)
- Kaynak yoksa açık "kaynak bulunamadı" mesajı (LLM yok)
- Üç mod da çalışır; `mode` geçmişte saklı
- SSE stream; `generation_logs` kind=`chat` kaydı mevcut
