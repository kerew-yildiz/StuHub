# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Çalışma rehberi prompt şablonları (v3 — düşük akıl yürütmeli model için direktif sertleştirme)."""

from __future__ import annotations

from .common import (  # noqa: F401
    CIKTI_SOZLESMESI_JSON,
    DIDAKTIK_USLUP,
    YASAK_IFADELER,
    dil_talimati,
)

SUMMARY_PROMPT = (
    """Görevin: bir ders notundan ÇALIŞMA REHBERİ üretmek.
Rehber, notun yerine geçmez. Notu okumaya HAZIRLAR ve okuduktan sonra HATIRLAMAYI sınar.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM:
1. Notu oku. Her bölümün taşıdığı çekirdek iddiayı tek cümleye indir.
2. Bu cümleleri madde madde diz: her madde TEK bilgi iddiası, en fazla 25 kelime.
3. Maddeleri notun sırasına göre yaz. Süsleme, giriş cümlesi, "bu bölümde" kalıbı YASAK.
4. Toplam 150-300 kelime yaz. Sonuna "### Kendini sına" bölümü ekle.
5. Kendini sına altında 3-5 soru yaz; her sorunun hemen altına "**Cevap:** ..." satırı koy.
   Sorular notu okumadan cevaplanmayı deneyecek düzeyde olsun; ezber tekrarı olmasın.
6. key_terms: 5-15 anahtar terim, her biri 1-4 kelime. Cümle yazma.
7. exam_focus: 3-8 madde, her biri tam cümle; sınavda çıkması muhtemel odak noktasını söyler.

KURAL: yalnız notta geçen bilgiyi kullan. Notta olmayan bilgi EKLEME.

"""
    + YASAK_IFADELER
    + """

{dil_talimati}

ŞEMA (birebir uy):
{{"summary_md": "...", "key_terms": ["..."], "exam_focus": ["..."]}}

ALTIN REFERANS 1 (biçim örneği — içeriği kopyalama):
{{"summary_md": "- Klasik koşullanmada tarafsız uyaran, tepki doğuran uyaranla eşleşerek tepki üretir hale gelir.\\n- Koşullu uyaran, koşulsuz uyarandan önce gelmelidir; sıra bozulursa öğrenme kurulmaz.\\n- Söndürmede koşullu uyaran tek başına tekrarlanır ve tepki zayıflar.\\n\\n### Kendini sına\\n- Zil yemekten sonra çalınsaydı koşullanma neden kurulmazdı?\\n  **Cevap:** İşaret olayı önceden haber vermez, ilişkilendirme kurulmaz.\\n- Söndürme tepkiyi siler mi?\\n  **Cevap:** Silmez, zamanla zayıflatır.\\n- Edimsel koşullanmadan farkı nedir?\\n  **Cevap:** Klasikte uyaran eşleşmesi, edimselde davranışın sonucu öğretir.", "key_terms": ["koşulsuz uyaran", "koşullu uyaran", "söndürme", "genelleme", "ayırt etme"], "exam_focus": ["Koşullu ve koşulsuz uyaranın zamanlama sırası sorulur.", "Söndürme ile unutma arasındaki fark istenir.", "Klasik ve edimsel koşullanmayı ayırt eden örnek verilir."]}}

ALTIN REFERANS 2 (biçim örneği — içeriği kopyalama):
{{"summary_md": "- Bağlı listede her düğüm veriyi ve bir sonraki düğümün adresini tutar.\\n- Başa ekleme sabit sürede biter; yalnız baş işaretçisi güncellenir.\\n- Sona ekleme listenin baştan taranmasını gerektirir.\\n\\n### Kendini sına\\n- Başa ekleme neden sona eklemeden hızlıdır?\\n  **Cevap:** Son düğüme ulaşmak tarama gerektirir, başa ekleme gerektirmez.\\n- Baş düğüm kaybolursa ne olur?\\n  **Cevap:** Listenin tamamına erişim kaybolur.\\n- Diziden farkı nedir?\\n  **Cevap:** Dizide bellek bitişiktir, listede düğümler işaretçiyle bağlanır.", "key_terms": ["düğüm", "işaretçi", "baş düğüm", "tarama", "bitişik bellek"], "exam_focus": ["Başa ve sona ekleme maliyetleri karşılaştırılır.", "Dizi ile bağlı liste farkı örnek üzerinden sorulur.", "İşaretçi kaybının sonucu sorulur."]}}

TESLİM ÖNCESİ KONTROL: summary_md 150-300 kelime mi, "### Kendini sına" bölümü ve cevaplar var mı,
key_terms 5-15 arasında mı, exam_focus cümle halinde mi, çıktı tek JSON nesnesi mi?

NOT METNİ:
{note_md}"""
)

CONCEPT_MAP_PROMPT = (
    """Görevin: notun KAVRAM HARİTASINI üretmek ve her ilişkiyi bir hatırlama sorusuna çevirmek.
Harita bir özet metni değildir; öğrencinin üzerinde çalışacağı iskelettir.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM:
1. Notta GEÇEN kavramları çıkar. Hayali kavram ekleme.
2. 5-20 düğüm seç. Her düğüme kısa etiket ver (1-4 kelime).
3. importance ver: 3 = konunun çekirdeği, 2 = destekleyici, 1 = ayrıntı.
4. Kenarları "A → B" yönünde kur: A, B'nin önkoşulu ya da üst kavramıdır.
5. ÇEVRİM OLUŞTURMA. Bir kavrama geri dönen yol kurma (yönlü, çevrimsiz olmalı).
6. Her kenara 2-4 kelimelik ilişki etiketi yaz ("neden olur", "önkoşuludur", "alt türüdür").
7. Her kenara TEK soru yaz: o ilişkiyi yoklar, cevabı kısadır, evet/hayırla geçiştirilemez.
8. from ve to değerleri nodes içindeki id'lerden olacak; olmayan id YASAK.

{dil_talimati}

ŞEMA (birebir uy):
{{"nodes": [{{"id": "k1", "label": "kavram adı", "importance": 1}}], "edges": [{{"from": "k1", "to": "k2", "label": "ilişki (2-4 kelime)", "question": "..."}}]}}

ALTIN REFERANS 1 (biçim örneği — içeriği kopyalama):
{{"nodes": [{{"id": "k1", "label": "Koşulsuz uyaran", "importance": 3}}, {{"id": "k2", "label": "Koşullu uyaran", "importance": 3}}, {{"id": "k3", "label": "Söndürme", "importance": 2}}], "edges": [{{"from": "k1", "to": "k2", "label": "eşleşmeyle oluşturur", "question": "Tarafsız uyaran hangi koşulda koşullu uyarana dönüşür?"}}, {{"from": "k2", "to": "k3", "label": "tek başına tekrarlanırsa", "question": "Koşullu uyaran yalnız başına tekrarlanırsa tepkiye ne olur?"}}]}}

ALTIN REFERANS 2 (biçim örneği — içeriği kopyalama):
{{"nodes": [{{"id": "k1", "label": "Düğüm", "importance": 3}}, {{"id": "k2", "label": "İşaretçi", "importance": 3}}, {{"id": "k3", "label": "Başa ekleme", "importance": 2}}], "edges": [{{"from": "k1", "to": "k2", "label": "içinde barındırır", "question": "Bir düğüm veriden başka neyi tutar?"}}, {{"from": "k2", "to": "k3", "label": "güncellenerek sağlar", "question": "Başa ekleme sırasında hangi alan değişir?"}}]}}

TESLİM ÖNCESİ KONTROL: düğüm sayısı 5-20 mi, her kenarın from/to değeri nodes'ta var mı,
her kenarda question dolu mu, çevrim oluştu mu, çıktı tek JSON nesnesi mi?

NOT METNİ:
{note_md}"""
)

COURSE_SUMMARY_PROMPT = (
    """Görevin: bir dersin TÜM chapter notlarından ders geneli ÇALIŞMA REHBERİ üretmek.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM:
1. Her chapter notunu oku ve o chapter'ın çekirdek iddiasını çıkar.
2. summary_md içinde her chapter için "### <chapter başlığı>" alt bölümü aç.
3. Her alt bölümde 2-4 madde yaz; her madde tek bilgi iddiası, en fazla 25 kelime.
4. Chapter'ları notların verildiği sırayla yaz. Sıra değiştirme.
5. Son alt bölüm olarak "### Bağlantılar" ekle: farklı chapter'ları birbirine bağlayan 2-4 madde yaz
   (hangi konu hangisinin önkoşulu, hangi ikili karıştırılır).
6. Toplam 300-600 kelime.
7. key_terms: 10-25 terim (1-4 kelime). exam_focus: 5-12 tam cümle.

KURAL: yalnız verilen notlardan yararlan; dış bilgi EKLEME.

"""
    + YASAK_IFADELER
    + """

{dil_talimati}

ŞEMA (birebir uy):
{{"summary_md": "...", "key_terms": ["..."], "exam_focus": ["..."]}}

ALTIN REFERANS 1 (biçim örneği — içeriği kopyalama):
{{"summary_md": "### Öğrenme Kuramları\\n- Klasik koşullanma uyaran eşleşmesiyle öğrenmeyi açıklar.\\n- Edimsel koşullanma davranışı sonucuyla biçimlendirir.\\n\\n### Bellek\\n- Bilgi duyusal, kısa ve uzun süreli bellekten geçer.\\n- Tekrar ve anlamlandırma kalıcılığı artırır.\\n\\n### Bağlantılar\\n- Koşullanma, belleğin tekrar ilkesiyle birlikte çalışır.\\n- Söndürme ile unutma sınavda karıştırılır.", "key_terms": ["klasik koşullanma", "edimsel koşullanma", "söndürme", "kısa süreli bellek", "anlamlandırma"], "exam_focus": ["İki koşullanma türünü ayırt eden örnek istenir.", "Söndürme ile unutmanın farkı sorulur.", "Bellek aşamalarının sırası sorulur."]}}

ALTIN REFERANS 2 (biçim örneği — içeriği kopyalama):
{{"summary_md": "### Doğrusal Veri Yapıları\\n- Dizide bellek bitişiktir, erişim sabit süredir.\\n- Bağlı listede düğümler işaretçiyle bağlanır.\\n\\n### Yığın ve Kuyruk\\n- Yığın son gireni ilk çıkarır.\\n- Kuyruk ilk gireni ilk çıkarır.\\n\\n### Bağlantılar\\n- Yığın ve kuyruk, bağlı liste üzerine kurulabilir.\\n- Dizi ile liste maliyetleri sınavda karşılaştırılır.", "key_terms": ["dizi", "bağlı liste", "işaretçi", "yığın", "kuyruk", "LIFO", "FIFO"], "exam_focus": ["Dizi ve bağlı liste maliyet karşılaştırması sorulur.", "LIFO ve FIFO örnek üzerinden ayırt ettirilir.", "Yığının hangi yapıyla gerçeklendiği sorulur."]}}

TESLİM ÖNCESİ KONTROL: her chapter için alt bölüm var mı, "### Bağlantılar" bölümü var mı,
key_terms 10-25 arasında mı, 300-600 kelime mi, çıktı tek JSON nesnesi mi?

CHAPTER NOTLARI:
{notes_md}"""
)

COMPARISON_PROMPT = (
    """Görevin: öğrencinin sınavda karıştırdığı kavramları İKİLİ olarak karşılaştıran tablo üretmek.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM:
1. ZORUNLU İKİLİLER listesindeki her ikili için TAM BİR kayıt üret. Fazladan ikili ekleme, eksik bırakma.
2. Her ikili için en az 1 benzerlik yaz (cümle halinde).
3. Her ikili için en az 2 ayırt edici fark yaz. Her farkta:
   - "aspect": TEK bir karşılaştırma ölçütü (1-4 kelime). "genel olarak", "yapısı" gibi belirsiz ölçüt YASAK.
   - "a": birinci kavramdaki durum. "b": ikinci kavramdaki durum. İkisi de aynı ölçüte cevap verir.
4. "confusion": karıştırmanın MEKANİZMASINI tek cümlede yaz — öğrenci hangi yüzey benzerliğe aldanıyor
   (aynı isim kökü, benzer süreç, benzer sonuç).
5. "discriminator": sınavda 5 saniyede uygulanacak TEK ayırt etme testi yaz.
   Kalıp: "Soruda <işaret> geçiyorsa <kavram>'dır."
6. concepts alanını girdideki sırayla doldur.

KURAL: yalnız DERS BAĞLAMI'ndaki bilgiyi kullan; dış bilgi EKLEME.

{dil_talimati}

ŞEMA (birebir uy):
{{"concepts": ["..."], "pairs": [{{"a": "...", "b": "...", "similarities": ["..."], "differences": [{{"aspect": "...", "a": "...", "b": "..."}}], "confusion": "...", "discriminator": "..."}}]}}

ALTIN REFERANS 1 (biçim örneği — içeriği kopyalama):
{{"concepts": ["Klasik koşullanma", "Edimsel koşullanma"], "pairs": [{{"a": "Klasik koşullanma", "b": "Edimsel koşullanma", "similarities": ["İkisi de deneyim yoluyla davranış değişikliği üretir."], "differences": [{{"aspect": "öğrenme kaynağı", "a": "uyaranların eşleşmesi", "b": "davranışın sonucu"}}, {{"aspect": "öğrencinin rolü", "a": "edilgen tepki verir", "b": "etkin davranış üretir"}}], "confusion": "İkisinde de tekrar ve pekiştirme sözcükleri geçtiği için öğrenci süreçleri aynı sanır.", "discriminator": "Soruda davranışın ardından ödül veya ceza geçiyorsa edimseldir."}}]}}

ALTIN REFERANS 2 (biçim örneği — içeriği kopyalama):
{{"concepts": ["Yığın", "Kuyruk"], "pairs": [{{"a": "Yığın", "b": "Kuyruk", "similarities": ["İkisi de eleman ekleme ve çıkarma işlemlerini sırayla yapar."], "differences": [{{"aspect": "çıkış sırası", "a": "son giren ilk çıkar", "b": "ilk giren ilk çıkar"}}, {{"aspect": "tipik kullanım", "a": "geri alma işlemleri", "b": "sıra bekleme işlemleri"}}], "confusion": "Her ikisinde de ekleme ve çıkarma uçlardan yapıldığı için öğrenci uçları karıştırır.", "discriminator": "Soruda 'geri al' veya 'son işlem' geçiyorsa yığındır."}}]}}

TESLİM ÖNCESİ KONTROL: zorunlu ikililerin tamamı var mı, her ikilide en az 1 benzerlik ve 2 fark var mı,
aspect değerleri tek ölçüt mü, discriminator kalıbı uygulanmış mı, çıktı tek JSON nesnesi mi?

KARŞILAŞTIRILACAK KAVRAMLAR:
{concepts}

ZORUNLU İKİLİLER (her biri için tam olarak bir kayıt üret):
{pairs}

DERS BAĞLAMI:
{context_md}"""
)
