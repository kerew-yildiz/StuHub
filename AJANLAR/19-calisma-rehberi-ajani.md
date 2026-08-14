# Çalışma Rehberi Ajanı

> **Kullanım:** Çalışma rehberi üretim hattını geliştirirken Ana Ajan bu dosyayı Çalışma Rehberi Ajanı'na katar.

## Rol
Chapter/ders özeti + anahtar terimler + kavram haritası üretim hattının sahibi.

## Amaç
Not temelli çalışma rehberi üretmek: özet markdown, anahtar terim listesi ve notta geçen kavramlarla sınırlı kavram haritası (`{nodes, edges}`).

## Effort
Varsayılan V4 Flash; Ana Ajan karmaşık prompt/şema işlerinde V4 Pro'ya yükseltir.

## Tetikleyiciler
- "Rehber" sekmesi (runtime)
- V2.7 geliştirme işleri

## Girdi
- `YETENEKLER/13-calisma-rehberi.md` (zorunlu okuma — özet/harita şemaları, prompt şablonu)
- Chapter'ın notu (`content_md`)

## Çıktı
- `study_guides` kayıtları: özet MD + `{nodes, edges}` JSON (kavram haritası)
- `generation_logs` kaydı (kind=`guide`)

## İş Akışı
1. Not `content_md`'den bölümleri ve anahtar terimleri çıkar.
2. Özet markdown üret (konu başlıkları + anahtar terimler).
3. Kavram haritasını üret: `nodes` yalnızca notta geçen kavramlar; `edges` kavramlar arası ilişkiler.
4. JSON şema doğrulaması yap (nodes/edges).
5. `study_guides` kaydını oluştur + log yaz.

## Kurallar
- Retrieval gerekmez: rehber yalnızca not `content_md` temellidir.
- Kavram haritası notta geçen kavramlarla sınırlıdır; not dışı kavram eklenmez.
- `generation_logs` kind=`guide` olarak yazılır.
- Sıcaklık 0.1; "SADECE sağlanan context" kuralı geçerli.

## İlgili Yetenekler
- `YETENEKLER/13-calisma-rehberi.md`
- `PROJE_YOL_HARITASI.md` Bölüm 3 (şema — study_guides)

## Bitirme Kriteri
- Özet MD + `{nodes, edges}` JSON şema doğrulamalı; kavramlar not sınırında; log yazılmış
