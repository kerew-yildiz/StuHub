# Yetenek 01 — PDF/PPTX İşleme ve İndeksleme

> **Sahibi:** Indexer Ajanı (`AJANLAR/04-indexer-ajani.md`). Bu dosya, RAG altyapısının çıkarım + chunking + embedding + indeksleme sözleşmesidir.

## Amaç
Kitap PDF'lerini ve sunumları (PDF/PPTX) doğru sayfa/slide metadata'sıyla metne çevirmek, chunk'lamak, embed etmek ve LanceDB'ye yazmak; taranmış belgelerde OCR yedeğini işletmek.

## Girdiler
- Materyal dosyası (`materials.filepath`; tip: `textbook` | `slides`)
- Materyal kaydı (`materials` tablosu satırı)
- Opsiyonel: chapter kaydı (slides materyalinde)

## Adım Adım İş Akışı

### 1. Dosya tipi tespiti
- Uzantı + içerik imzası ile PDF/PPTX ayrımı yap; bilinmeyen tip → `indexing_jobs.error` = "Desteklenmeyen dosya türü: <uzantı>".

### 2. PDF metin çıkarımı (kitaplar ve PDF sunumlar)
- pymupdf ile sayfa sayfa metin çıkar; `page_count`'u `materials`'a yaz.
- `likely_scanned_pages` denetimi: metin oranı eşiğin altındaki sayfalar → **marker-pdf OCR** yedeği (yalnızca bu sayfalar için).
- Şifreli PDF → hata: "PDF şifreli; şifreyi kaldırıp tekrar yükleyin." Bozuk dosya → hata: "PDF okunamadı, dosya bozuk olabilir."

### 3. PPTX işleme (sunumlar)
- python-pptx ile slide başına metin çıkar (başlık + gövde + notlar); `slides` tablosuna `(chapter_id, material_id, slide_no, content_text)` yaz.
- **Render:** LibreOffice headless ile `soffice --headless --convert-to pdf` komutuyla PDF kopyası üret; `materials` ile ilişkilendir (pop-up render kaynağı). LibreOffice yoksa: "render yok" bayrağı; pop-up metin alıntısı fallback'i kullanır.

### 4. Chunking
- PDF: sayfa bazlı böl; ~1200 token hedefiyle sayfa içinde büyük parçaları böl; chunk'lar arası ~100 token overlap.
- PPTX: slide bazlı (bir slide = en az bir chunk; uzun slide bölünebilir).
- Her chunk metadata taşır: `chunk_id, course_id, material_id, page, slide, text`. `page/slide` offset'leri atıf pop-up'ının doğru bölümü açması için **kaybedilemez**.

### 5. Embedding
- Model: sentence-transformers + **bge-m3** (öncelik) veya **multilingual-e5-small**; CPU ile çalışır.
- Embedding **kesinlikle yereldir**: model indirilemez/çalıştırılamazsa iş `failed` olur ve kullanıcıya kurulum talimatı gösterilir. **Uzak embedding API'sine (Hugging Face Inference dahil) düşülmez** (gizlilik sözleşmesi, yol haritası Bölüm 8).
- Vektörler chunk metniyle birlikte LanceDB namespace `course_{id}_chunks`'a upsert edilir.

### 6. Durum makinesi
- `indexing_jobs`: `pending → processing (progress 0-100) → done | failed(error)`.
- İş iptal edilirse kaldığı sayfadan devam edilebilir (idempotent upsert).

## Veri Formatları

LanceDB chunk satırı:
```json
{
  "chunk_id": "chk_<material_id>_<page_or_slide>_<seq>",
  "course_id": 1,
  "material_id": 2,
  "page": 41,
  "slide": null,
  "text": "...",
  "vector": [0.01, ...]
}
```

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Şifreli PDF | failed + Türkçe hata mesajı |
| Bozuk/boş dosya | failed + Türkçe hata mesajı |
| Taranmış sayfalar | OCR yedeği; OCR de başarısızsa sayfa "boş" işaretlenir, iş devam eder |
| LibreOffice yok | render bayrağı yok; indexing başarılı sayılır |
| Embedding modeli indirilemedi | failed + kurulum talimatı (uzak fallback YASAK — yol haritası Bölüm 8) |
| Dev dosyalar (>1000 sayfa) | İş parçalanır; ilerleme raporlanır |

## Kabul Kriterleri
- Her sayfa/slide en az bir chunk'ta temsil edilir; page/slide metadata'sı doğru
- `indexing_jobs` her zaman terminal durumda biter (done/failed + mesaj)
- OCR yalnızca taranmış sayfalarda çalışır (kanıt: iş günlüğü)
- Aynı materyal yeniden indekslendiğinde eski chunk'lar silinir, yenisi yazılır (dup yok)

## Notlar
- pymupdf AGPL-3.0'dır: kişisel yerel kullanımda kabul (yol haritası Bölüm 7). Dağıtım hedeflenirse pdfplumber (MIT) ile değiştir — Ücretsizlik Ajanı denetiminde.
