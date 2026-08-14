# Yetenek 11 — Medya Alımı (Çıkarım + Transkripsiyon)

> **Sahibi:** Medya Alım Ajanı (`AJANLAR/17-medya-alim-ajani.md`). Bu dosya, medya/doküman tipi materyallerin metne çıkarım ve transkripsiyon sözleşmesidir.

## Amaç
YouTube/ses kaydı, DOCX, EPUB, görsel ve düz metin materyallerinden **tamamen yerel araçlarla** metin/transkript çıkarmak; çıktıyı otomatik olarak indeksleme hattına bağlamak.

## Girdiler
- `materials` kaydı (tip + `filepath` veya `url`)
- `indexing_jobs` kaydı (iş durumu makinesi)

## Extractor Arayüzü

```python
extract(material) -> list[{'segment': int, 'text': str}]
```

- **Zaman damgalı ortamlar** (youtube, audio): `segment` = dakika/saniye indeksi.
- **Dokümanlar** (docx, epub, image, text): `segment` = bölüm/sayfa indeksi.

## Tip Bazlı Çıkarıcılar

| Tip | Araç | Davranış |
|-----|------|----------|
| `youtube` | yt-dlp (altyazı) → faster-whisper (fallback) | Altyazı **tr→en kademeli** çekilir; altyazı yoksa ses indirilip yerel transkripsiyon |
| `audio` | faster-whisper | `whisper_model` ayarı (varsayılan `small`); yerel STT |
| `docx` | python-docx | Paragraf akışı (bölüm indeksli) |
| `epub` | **stdlib `zipfile`** + XHTML metin çıkarımı | `ebooklib` (AGPL-3.0) **KULLANILMAZ** |
| `image` | rapidocr-onnxruntime | Yerel OCR |
| `text` | Doğrudan okuma | Bölüm/paragraf indeksi |

## İş Hattı

1. `indexing_jobs.kind='transcribe'` → ilgili extractor çalışır.
2. Transkript `data/transcripts/{material_id}.json` yazılır:
   ```json
   { "segments": [ { "index": 0, "start": 0.0, "end": 12.5, "text": "..." } ] }
   ```
3. `materials.extracted_text` = segment metinlerinin düz birleşimi.
4. Otomatik **`kind='index'` zincirleme**: transkript bitince chunking + embedding başlar (Yetenek 01).
5. Boş çıktı → `failed` + Türkçe hata mesajı.

## OCR Fallback
- Metinsiz PDF sayfaları `ocr_enabled=true` iken OCR'lanır; OCR modeli **ilk kullanımda yerel indirilir** (uzak OCR API YASAK).

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Araç kurulumu başarısız (yt-dlp/whisper/ocr) | İlgili tip için hata; **diğer özellikleri bloklamaz** (tembel import) |
| Altyazı bulunamadı (youtube) | Ses indirilip faster-whisper transkripsiyonuna düşülür |
| Boş çıktı (0 segment / boş metin) | `failed` + Türkçe hata ("materyalden metin çıkarılamadı") |
| EPUB XHTML bozuk | Segment atlanır; tamamı boşsa `failed` |
| Transkript JSON yazılamadı | `failed`; `extracted_text` güncellenmez |

## Kabul Kriterleri
- Tüm çıkarım **yereldir** (uzak STT/OCR/metin API'si yok)
- Tembel import: başarısız araç kurulumu diğer özellikleri bloklamaz
- Transkript JSON şeması geçerli; `extracted_text` düz metin birleşimi
- `transcribe` → `index` zincirleme otomatik; iş her zaman terminal durumda biter
