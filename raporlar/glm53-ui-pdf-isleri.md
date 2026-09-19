# StuHub — UI/PDF İş Paketi Raporu (13 Kalem)

**Branch:** `feat/glm-13-item-batch` · 6 commit · push yapılmadı
**Sonuç:** 13 kalemin tamamı uygulandı. Kalite kapıları: backend **410 test geçti**, frontend **177 test geçti**, `tsc --noEmit` ve lint **temiz**.

## 1) Cursor'a duyarlı ağır efektler kaldırıldı, global glow geldi
- Panel bazlı yansıma/parlama sistemi (`data-reflect` + `--reflect-*` + kare başına `--edge-*`/`--smear*` değişken yazımı, her karede panel rect okuması) tamamen söküldü. Bu sistem her fare karesinde layout okuma + CSS değişkeni yazımı yaptığı için güç tüketiminin ana kaynağıydı.
- Yerine **tek ambient glow katmanı** eklendi: 600px, %8 alfa, bulanık radyal gradyan. Kök katman `translate3d` ile taşınır; kare başına CSS değişkeni **yazılmaz** — sadece GPU dostu transform.
- `CursorRing` bileşeni, tema token'ları ve testleri yeni davranışa göre güncellendi; `theme.css` ~124 satır sadeleşti.

## 2) Not görüntüleyici görsel düzeni
- `NoteViewer` render katmanı yeniden düzenlendi: başlık hiyerarşisi, bölüm boşlukları ve görsel ayrım iyileştirildi; içerik **tek bayt bile değişmedi** (saf CSS + sarım katmanı değişikliği).
- Daralt butonu artık **salt ikon** (chevron/kalem ikonu, metin kaldırıldı) — aria-label erişilebilirliği korundu.

## 3) PDF adlandırma
- PDF indirme adı artık chapter başlığından üretiliyor: **"1. Perspectives Research - Digital Copy"** biçiminde (`{chapter} - Digital Copy` / `{chapter} - Physical Copy`). Frontend `notes.ts` + `NotebookPage.tsx` güncellendi; dosya adı platform geçersiz karakterlerinden temizleniyor.

## 4) PDF kart yerleşimi yeniden tasarlandı
- Alt konu başlıkları artık **kartın DIŞINDA**, yatay ortalı yazılıyor; hemen altında kart açılıp o alt başlığın içeriğini sarmalıyor.
- Kart **sayfa sonunda her zaman kapatılır**; kalan içerik yeni sayfada **yeni bir kartta** kaldığı yerden devam eder. Eski "kart konu bitmeden kapanmaz, düz çizgiyle taşar" davranışı tamamen kaldırıldı.
- Ana başlık: alt başlıktan büyük punto, yatay ortalı ve hemen altında **başlığın en alt satır uzunluğuna göre** ölçülen separator çizgisi.
- Footer artık **kart alanının içinde**, sayfa sonundaki rezerve bantta; içerik akışı footer'ın üstünde biter — çakışma imkânsız.
- Kart kenar boşlukları **%35 artırıldı** (16pt → 21.6pt) ve dikey metin taşması için kart/metin padding-harf aralığı optimize edildi.

## 5) [n] atıf sistemi tamamen kaldırıldı
- Not üretimi **kaynaklardan beslenmeye devam eder** (promptlarda kaynak temelli üretim kuralları korundu); sadece gösterim katmanı söküldü.
- Kaldırılanlar: `[n]` işaretleme + çözümleme zinciri (`_CitationRegistry`, `_validate_citations`, atıf doğrulama geçidi, `CITATION_CONFIRM_PROMPT`), notun sonundaki `## Kaynakça` bloğu ve üretici kodu, frontend'de atıf çipleri/kaynakça render'ı.
- "Bu konu kaynaklarda bulunamadı" tarzı uyarılar son kullanıcıya bir daha gösterilmez.

## 6) Çalışma süresi takibi (chapter + ders)
- Chapter süresi = chapter layer'a bağlı **tüm sekmelerde** (Genel, Notlar, Quiz, Flashcard Practice, Materyale Sor) geçirilen gerçek süre; heartbeat ile canlı artar ve arayüzde güncel gösterilir.
- Ders süresi = ders sekme süresi (Genel, Notlar, Kaydedilenler, Flashcard Practice, Kaydırarak Quiz, Materyale Sor, Ödev Değerlendir, Ödev Taslak Koçu) **+ içindeki chapterların sürelerinin toplamı**.
- `study_time` heartbeat zinciri, `card_summary` ve ders/chapter kartlarındaki süre gösterimleri bu tanıma göre bağlandı.

## 7) Chapter'lar başlığı ortalı ve 1 punto büyük
- Chapter kartı başlığı **16px** (bir punto büyütüldü) ve **yatay ortalı**; düzenle/sil aksiyonları varken sola hizalamayı korur (butonlarla çakışmasın diye).

## 8) Isı haritasından chat çıkarıldı
- Chat kolonu, chat sinyali, `chat` ağırlığı ve `chat_messages` sorguları backend'den tamamen kaldırıldı; zayıflık skoru **quiz 0.625 / kart 0.375** olarak yeniden normalize edildi (eski oran korundu).
- Frontend ızgarasından Chat kolonu ve chat ağırlık metni çıkarıldı; `heatmap.ts` tipleri backend ile birebir eşlendi. Sohbet özelliğinin kendisi etkilenmedi — yalnızca ısı haritası ölçümünden çıkarıldı.

## 9) Flashcard swipe animasyonu yenilendi
- "Tüm kartın hızlı fade olması" yerine **dış kartta maskeleme**: kart, kapalı bir alana kayarak giriyor gibi, fade olmadan kayıyor. Kart kenardan dış karta girerken maskeleniyor.
- **%25 eşiği:** kullanıcı kartın %25'inden azını kaydırdıysa bıraktığında kart olduğu yere **geri döner**; %25'i geçerse kaydırma tamamlanır. Klavye/flick hız eşiği de aynı eşikle uyumlu hale getirildi.

## Notlar
- Rapor dışındaki tüm çalışma (kod, yorum, commit) İngilizce yürütüldü; UI metinleri Türkçe korundu.
- Birlefirme sırasında geçici yama betikleri (`_patch_heatmap*.py`) silindi; çalışma dizini temiz.
- İşlem sırasında 3 lint hatası bulundu ve giderildi: `export_service.py`'de eksik `_TAG_RE` tanımı, uzun docstring satırı ve `notes.ts`'te kontrol karakterli regex.
