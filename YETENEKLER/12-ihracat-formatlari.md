# Yetenek 12 — İhracat Formatları

> **Sahibi:** İhracat Ajanı (`AJANLAR/18-ihracat-ajani.md`). Bu dosya, not/kart/quiz çıktılarının Markdown, Anki (.apkg), CSV ve dönem arşivi olarak dışa/içe aktarım sözleşmesidir.

## Amaç
Üretilen çıktıları taşınabilir formatlarda dışa aktarmak ve dönem arşivini güvenle içe aktarmak; kullanıcının verisine kilitlenmesini önlemek.

## Format 1 — Markdown (MD)
- Notun `content_md` alanı **birebir** kopyalanır; dosya başına `# {topic/başlık}` eklenir.
- Quiz/flashcard için basit MD listeleme (soru/cevap satırları) üretilir.

## Format 2 — Anki (.apkg)
- **stdlib `zipfile`** ile paket; içinde:
  - `collection.anki2` — SQLite; `col`, `notes`, `cards`, `revlog` tabloları (Anki şeması).
  - `media` — JSON (medya eşlemesi).
- Deck adı: **`StuHub::{Ders}`**; kart tipi **Basic** (`front`/`back`).
- Paket sonrası **açma doğrulaması**: üretilen `.apkg` yeniden açılır ve şema/entegrasyon doğrulanır; geçersiz paket üretilmez (yeniden üretilir).

## Format 3 — CSV
- Sütunlar: `front;back;topic;citation` (noktalı virgül ayraç).
- Dosya **UTF-8 BOM** ile yazılır (Excel uyumluluğu).

## Format 4 — Dönem Arşivi (zip)
```
archive.zip
├── manifest.json
└── courses/
    └── {id}/
        ├── notes/          (MD)
        ├── quizzes/        (JSON)
        ├── flashcards/     (JSON)
        ├── chats/          (JSON)
        ├── guides/         (JSON)
        └── materials/      (opsiyonel, archive_include_files)
```
- `manifest.json`:
  ```json
  {
    "app": "stuhub",
    "version": 1,
    "generated_at": "2026-08-15T09:00:00Z",
    "term": "2025 Güz",
    "courses": [1, 2],
    "materials_included": true
  }
  ```
- Materyal dosyaları yalnızca `archive_include_files=true` ise pakete girer.

## İçe Aktarma (Import)
1. **Manifest sürüm doğrulaması:** `version` desteklenmiyorsa import reddedilir (Türkçe hata).
2. **Kimlik yeniden eşleme:** eski id'ler yeni yerel id'lere eşlenir (not↔quiz↔flashcard bağları korunur).
3. **Çakışan isim:** aynı adlı ders/chapter varsa "-içe aktarıldı" eki eklenir.
4. **Mevcut veri asla silinmez:** import yalnızca ekleme yapar; üzerine yazma/silme yok.

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Geçersiz `.apkg` | Açma doğrulaması başarısız → paket yeniden üretilir |
| Manifest sürüm uyumsuz | Import reddedilir + Türkçe hata |
| Çakışan ders/chapter adı | "-içe aktarıldı" eki |
| Boş deck (0 kart) | apkg üretilmez; kullanıcıya bilgi |
| Arşiv bozuk/eksik | Import atomik: hiçbir şey yazılmadan durur |

## Kabul Kriterleri
- MD `content_md` birebir; CSV UTF-8 BOM'lu
- `.apkg` Anki'de açılır (açma doğrulaması testli)
- Arşiv `manifest.json` sürüm 1; import mevcut veriyi silmez, kimlikleri yeniden eşler
