# Yetenek 02 — RAG Not Üretimi

> **Sahibi:** Not Üretici Ajanı (`AJANLAR/05-not-uretici-ajani.md`). Bu dosya, guideslide rehberli kitap tarama + not üretim hattının sözleşmesidir.

## Amaç
Guide slide'lardaki konuları rehber alarak ders kitaplarından, **tüm konuları eksiksiz kapsayan**, inline atıflı öğrenci notları üretmek.

## Girdiler
- Chapter'ın `slides` kayıtları (slide_no + içerik)
- Dersin indeksli kitap chunk'ları (LanceDB `course_{id}_chunks` + `citations_ledger` adayları)
- Model: DeepSeek chat API (stream)

## Adım Adım İş Akışı

### 1. Konu çıkarımı
- Slide metinlerini LLM'e ver; çıktı: konu listesi `[{topic, keywords[], slide_refs[]}]` (JSON şeması zorunlu).
- Konu çıkarılamazsa (boş slayt seti vb.): kullanıcıya bilgi ver, manuel düzeltme yolu sun, işi başarısız işaretleme.

### 2. Hibrit retrieval (konu başına)
- **Vektör skoru:** konu sorusunun embedding'i ile chunk vektörleri arasında cosine benzerliği (top-k, k=10 varsayılan).
- **Keyword skoru:** konu `keywords` terimlerinin chunk metninde geçme sıklığı (BM25-vari basit skor).
- Birleşik skor: `0.7 * vektör + 0.3 * keyword`; sayfa bazlı grupla ve komşu sayfa ekleme yap (bağlam bütünlüğü).
- Sonuç kümesi context limitini aşarsa skora göre kırp; her chunk `[n]` atıf kimliği alır.

### 3. Konu bazlı map-reduce üretim
- **Her konu ayrı LLM çağrısıdır** (tek dev çağrı yasak — context/output limitleri).
- Prompt: konu + slide rehberi + retrieved chunk'lar + atıf formatı talimatı.
- Üretim stream edilir; SSE ile frontend'e ilerleme akar.

### 4. Kapsama doğrulama
- Konu kontrol listesi (adım 1 çıktısı) ile üretilen not bölümleri eşleştirilir (LLM doğrulama çağrısı).
- Eksik konu varsa o konu için yeni retrieval + üretim (max 3 iterasyon). 3 iterasyonda kapanmayan konu: not "eksik konu" uyarısıyla kaydedilir ve kullanıcıya bildirilir (asla sessizce atlanmaz).

### 5. Atıf doğrulama
- `YETENEKLER/06-atif-sistemi.md` adımı çalıştırılır; çözümsüz atıf kabul edilmez.

### 6. Kayıt
- `notes`: `content_md`, `citations_json`, `topics_json`, `generated_at`, `model_used`.
- `generation_logs`'a token sayıları yazılır.

## Veri Formatları

Konu listesi (adım 1 çıktısı):
```json
{
  "topics": [
    { "topic": "Hücre zarı yapısı", "keywords": ["fosfolipid", "çift katman", "protein"], "slide_refs": [1, 2] }
  ]
}
```

Konu→kaynak atıf haritası (`citations_json`):
```json
{
  "topics": [
    {
      "topic": "Hücre zarı yapısı",
      "citations": [
        { "id": 1, "source_type": "textbook", "source_id": 12, "page": 41, "chunk_id": "chk_12_41_1", "quote": "..." }
      ]
    }
  ]
}
```

## Prompt Şablonu (üretim çağrısı — taslak)

```
Sen bir üniversite ders notu yazarısın. Aşağıda bir ders sunumunun [KONU] konusundaki rehber içeriği ve ders kitabından alınan kaynak parçaları var.

KURALLAR:
1. SADECE sağlanan kaynak parçalarını kullan; kaynaklarda olmayan bilgi EKLEME.
2. [KONU]'yu eksiksiz ve anlaşılır biçimde açıkla; öğrenci seviyesine uygun Türkçe yaz.
3. Her bilgi parçasının sonuna kaynak atıf numarasını [n] biçiminde koy.
4. Madde işaretleri ve kısa paragraflar kullan; gereksiz tekrar yapma.

REHBER (sunum): {slide_content}
KAYNAKLAR:
[1] (sayfa 41) {chunk_text}
[2] (sayfa 42) {chunk_text}

ÇIKTI: Markdown not bölümü (inline atıflı).
```

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Konu çıkarılamadı | Kullanıcı bilgilendirilir; manuel düzeltme yolu |
| Retrieval boş döndü | Konu "kaynak bulunamadı" işaretlenir; notta bu konu uyarılı yazılır |
| LLM kesintisi | Kısmi çıktı kalıcılaştırılır; iş kaldığı yerden sürdürülür |
| Kapsama 3 iterasyonda kapanmadı | Not uyarıyla kaydedilir; kullanıcıya bildirilir |
| Output token aşımı | Konu parçalanır (alt konulara bölünür) |

## Kabul Kriterleri
- Kapsama kontrol listesi %100 (uyarılı konu yoksa)
- Tüm atıflar çözümlü (`06-atif-sistemi.md` doğrulamasından geçmiş)
- Üretim map-reduce yapılmış (tek çağrı kanıtı yok)
- `generation_logs` kaydı mevcut
