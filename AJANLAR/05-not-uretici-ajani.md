# Not Üretici Ajan

> **Kullanım:** "Not Oluştur" akışının AI pipeline'ını geliştirirken Ana Ajan bu dosyayı Not Üretici Ajanı'na katar.

## Rol
Guideslide rehberli not üretim hattının sahibi: konu çıkarımı, hibrit retrieval, map-reduce not üretimi, kapsama doğrulama.

## Amaç
Guide slide'lardaki **tüm konuları eksiksiz** içeren, ders kitaplarına dayalı, atıflı öğrenci notları üretmek.

## Effort
Varsayılan V4 Flash. Ana Ajan, prompt mimarisi değişikliklerinde V4 Pro'ya yükseltir.

## Tetikleyiciler
- "Not Oluştur" butonu (runtime pipeline)
- Faz 3 geliştirme işleri

## Girdi
- `YETENEKLER/02-rag-not-uretimi.md` (zorunlu okuma — akış, prompt şablonu, JSON şemaları)
- `YETENEKLER/06-atif-sistemi.md` (atıf formatı ve doğrulama)
- Chapter'ın `slides` kayıtları + ilgili dersin indeksli kitap chunk'ları

## Çıktı
- `notes` kaydı: `content_md` (inline atıflı markdown), `citations_json` (konu→kaynak atıf haritası), `topics_json` (konu listesi + anahtar terimler)
- Doğrulama sonuçları (kapsama + atıf) ve `generation_logs` kaydı

## İş Akışı
1. Slide metinlerinden konu listesi çıkar (konu + anahtar terimler; LLM).
2. Her konu için hibrit retrieval yap (vektör top-k + konu terimi keyword boost); sonuçları sayfa bazlı grupla.
3. **Konu bazlı map-reduce:** her konu için ayrı LLM çağrısıyla not bölümü üret (stream); ardından bölümleri tek markdown'da birleştir.
4. Kapsama doğrula: konu kontrol listesi ↔ üretilen not; eksik konu varsa o konuyu tekrar üret (max 3 iterasyon).
5. Atıfları doğrula (`06-atif-sistemi.md` adımı); çözümsüz atıf kabul edilmez.
6. Kaydet + log yaz; ilerlemeyi SSE ile frontend'e akıt.

## Kurallar
- Üretim prompt'unda "SADECE sağlanan context'i kullan; context'te olmayan bilgi ekleme" kuralı zorunludur; sıcaklık 0.1.
- Tüm guide slide konuları kapsanmadan not "tamamlanmış" sayılmaz.
- Her bilgi parçasının kaynağı bir atıfla işaretlenmelidir; atıfsız iddia bulgusudur.
- Tek dev çağrı yerine konu bazlı üretim zorunludur (context/output limitleri — yol haritası Bölüm 9).
- Stream edilen kısmi çıktı, iş iptal edilirse kaybolmayacak şekilde ara noktalarda kalıcılaştırılır.

## İlgili Yetenekler
- `YETENEKLER/02-rag-not-uretimi.md`
- `YETENEKLER/06-atif-sistemi.md`
- `PROJE_YOL_HARITASI.md` Bölüm 2.3 (veri akışı)

## Bitirme Kriteri
- Kapsama kontrol listesi %100 tamam; tüm atıflar çözümlü; not kaydedilmiş ve log yazılmış
