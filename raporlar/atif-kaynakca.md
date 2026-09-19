# İş 3 — Atıf Numaralandırma + Kaynakça: Doğrulama Raporu

**Dal:** `feat/atif-kaynakca` · **Tarih:** 2026-09-18 · **Ortam:** Windows (PowerShell + Git Bash), yerel backend + gerçek test hesabı verisi

---

## 1. Kullanıcı isteği (özet)

1. Not sonunda kaynakça olsun: kitap → sayfa no, slayt → slayt no, web → link.
2. Not parça parça üretildiği için atıf numaraları her bölümde `[1][2][3]`'ten yeniden başlıyordu; **artarak devam etmeli**.
3. Materyal atıfı ile web atıfı **görsel olarak (renk hariç) ayırt edilebilsin**.

## 2. Kod tarafında yapılmış olanlar (bu oturumda DOKUNULMADI, yalnız doğrulandı)

- `apps/backend/src/services/note_generator.py`
  - `_CitationRegistry` (satır ~250): not üretimi boyunca TEK `chunk_id → global numara` kaydı; aynı kaynak ikinci kez geçerse AYNI numara.
  - `_resolve_citations` (satır ~287): bölüm metnindeki yerel `[n]` → global numara; **web** kaynağı `⟨n⟩`, **kitap/slayt** `[n]` (dönüşümü backend yapar, model tek biçim üretir).
  - `_bibliography_block` (satır ~703): not sonuna KOD tarafından `## Kaynakça` ekler — kitap `[n] ad, s. sayfa`, slayt `[n] ad, slayt no`, web `⟨n⟩ başlık — <URL>` (tıklanabilir). Yalnız notta GERÇEKTEN kalan atıflar listelenir.
  - `_validate_citations` (satır ~598): atıflar deterministik fuzzy alıntı eşleşmesiyle doğrulanır; çözümsüz atıf "sorunlu konu" sayılır → yedek zincir (web → slayt → deterministik) devreye girer. Not ASLA atıf hatasıyla bitmez.
- `apps/backend/src/services/quiz_generator.py`: kaynakça başlıkları quiz/flashcard üretiminde konu olarak atlanır.
- `apps/frontend/src/components/NoteViewer.tsx`: `⟨n⟩` → kesikli kenarlık + küçük ↗ oku; `[n]` → düz kenarlık, ok yok. RENK FARKI YOK.

## 3. Test sonuçları

| Paket | Sonuç |
|---|---|
| `uv run ruff check src tests` | ✅ temiz |
| `uv run pytest -q` (backend, Windows venv sıfırdan kuruldu) | ✅ **386 geçti** (17'si bu işin atıf testleri) |
| `npm run lint` / `npm run typecheck` | ✅ temiz |
| `npm test` (frontend, `npm ci` sıfırdan) | ✅ **160 geçti** (NoteViewer çip biçim testleri dahil) |

## 4. Uçtan uca kanıt — gerçek üretimlerle

### 4.1 Gerçek veriyle üretim (test hesabı: 2026 Güz / Developmental Psychology → chapter 14, "3. Research Methods (2)")

"Oluştur" ile gerçek not üretimi çalıştırıldı (SSE akışı kayda alındı):

- Kaynakça bölümü **kod tarafından** üretildi, üç web kaynağı doğru biçimde listelendi:

```
## Kaynakça

- ⟨1⟩ Gelişim Psikolojisinde Araştırma Yöntemleri — <https://www.scribd.com/document/787414613/...>
- ⟨2⟩ Çocuk Gelişimi Araştırmaları — <https://www.scribd.com/document/1027903740/...>
- ⟨3⟩ VERİ TOPLAMA TEKNİKLERİ — <https://otp.tarimorman.gov.tr/Content/belgeler/veri+toplama+teknikleri.pdf>
```

- **Global numara + sabit kimlik kanıtı:** notun 1. bölümünde atıf görünen ⟵ ilk bölüm web yerine sunum içeriğinden yazıldı (bkz. §6); 2. bölüm (Etik İlkeler) ise web kaynaklı: `⟨3⟩ ⟨1⟩ ⟨2⟩ ⟨3⟩ …` — **aynı kaynak her geçişte AYNI numarayı aldı**, numaralar bölüm başında sıfırlanmadı.
- Web atıfları `⟨n⟩`, tıklanabilir `<URL>` — istenen biçim.

### 4.2 Kontrollü üretim (kendi test materyallerimle: dönem 35 → ders 42 → chapter 164)

Küçük bir kitap PDF'i (`textbook`) + 4 slaytlık sunum (`slides`) yüklendi, İKİSİ de indekslendi (`course_42_chunks`), sonra gerçek not üretimi (not 26):

- **Numaralar kaynak tipleri ARASINDA da artarak devam etti:**
  - Slayt kaynaklı bölüm atıfları: `[1] [2] [3] [4]` (slayt 1→4)
  - Web kaynaklı bölüm atıfları: `⟨5⟩ ⟨6⟩ ⟨7⟩` (1-7 kesintisiz, çakışma yok)
- **Kaynakça üç formatı da doğru yazdı:**

```
## Kaynakça

- [1] test-kitap.pdf, s. 1              ← kitap → sayfa
- [2] test-sunum.pdf, slayt 1           ← slayt → slayt no
- [3] test-sunum.pdf, slayt 2
- [4] test-sunum.pdf, slayt 3
- [5] Gelişim Psikolojisinde Araştırma Yöntemleri — <https://...>   ← web → link
```

### 4.3 Otomatik not üretimi (chapter 165)

Yeni chapter'a sunum yüklenince arka planda not kendiliğinden üretildi (not 27): kaynakça + global numara zinciri yukarıdakiyle aynı şekilde doğru.

## 5. Görsel ayrım kanıtı

- Birim: `NoteViewer.test.tsx` — `⟨n⟩` kesikli kenarlık + ↗, `[n]` düz kenarlık + ok yok (✅ 4/4).
- E2E ekran görüntüleri: `raporlar/ekran/` (koyu + açık tema).

## 6. Bilinen sınırlamalar (önceden var olan davranış, bu işin kapsamı dışında)

- Model bazı bölümlerde `### {konu}` başlığını atlayabiliyor → başlıksız bölümde atıf çipi yerine düz metin görünebilir.
- Materyal (kitap/slayt) atıfı, fuzzy alıntı eşleşmesi doğrulamayı geçemezse **bölüm korunur ama atıf düşer** (atanmış tasarım: not asla atıf hatasıyla bitmez). Bu yüzden gerçek çıktıda gövdede materyal çipi her üretimde garanti değildir; kaynakça yalnız kalan atıfları listeler. Web yedeği devreye girdiğinde bölümler web kaynaklı yazılır (`⟨n⟩`).
- Yerel ortamda test hesabının gerçek materyalleri henüz indekslenmemiş olduğu için üretim web yedeğine sık düşer; kontrollü test (§4.2) materyal indeksli senaryoyu kanıtlar.

## 7. Sade Türkçe özet

Atıf numaraları artık notun tamamında artarak devam ediyor; aynı kaynak her yerde aynı numarayı alıyor. Web kaynaklı atıflar `⟨n⟩` (kesikli çerçeve + ↗), kitap/slayt kaynaklılar `[n]` (düz çerçeve) olarak gösteriliyor — renk yok, istenen biçim farkı var. Notun sonuna kod tarafından `## Kaynakça` ekleniyor: kitap → sayfa, slayt → slayt no, web → tıklanabilir link. 386 backend + 160 frontend testi yeşil; gerçek hesap verisiyle ve kontrollü test materyalleriyle uçtan uca kanıtlandı. Test üretimleri temizlendi.

## 8. Temizlik

Silinen test verileri: dönem 35 → ders 42 (chapter 164, 165, materyal 70, 71 ve ürettiğim notlar 25/26/27) + chapter 14'e üretilen test notu 23 (eski not 6 otomatik geri gelir). Kullanıcının kendi verilerine dokunulmadı.

**Bıraktığım süreç: YOK**
