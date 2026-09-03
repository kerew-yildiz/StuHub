# Migration Politikası (Faz 0.2)

- `../schema.sql` **tek doğruluk kaynağıdır**; `init_db` her açılışta idempotent uygular.
- Şema evrimi gerektiğinde (Faz 2+):
  1. `migrations/` altına `NNN_aciklama.sql` biçiminde numaralı dosya ekle (NNN: artan sayı).
  2. Uygulama bir `schema_migrations` tablosu tutar ve uygulanmamış migration'ları sırayla işler.
  3. `schema.sql`'i de yeni duruma güncelle (yeni kurulumlar için).
- Kurallar: mevcut veriyi yok eden migration yazılmaz; her migration tek dosyada, geri alınabilir notuyla.

Şu an uygulanmış migration yok (ilk kurulum doğrudan schema.sql).
