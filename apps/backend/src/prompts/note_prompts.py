# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Not üretimi prompt şablonları (Yetenek 02 §Prompt Şablonu + Yetenek 06 doğrulama)."""

from .common import KAYNAK_DISI_BILGI_YASAGI

TOPIC_EXTRACTION_PROMPT = """Sen bir ders notu asistanısın. Aşağıdaki ders sunumu (guide slides) içeriğinden, not üretilecek konu listesini çıkar.

SUNUM:
{slides}
{kazanimlar}
KURALLAR:
1. Her konu için kısa ve net bir başlık yaz (en fazla 8 kelime).
2. BÖLME ÖLÇÜTÜ: bir konu, öğrencinin tek oturumda işleyebileceği büyüklükte olmalı. Bir konu
   8'den fazla yeni terim içeriyorsa veya slaytların yarısından fazlasına yayılıyorsa, onu
   anlamlı alt parçalara böl. Birbirinden bağımsız iki kavramı tek konuda birleştirme.
3. keywords: konuyla ilgili anahtar terimler (3-8 adet; öğrencinin sınavda görmesi muhtemel terimleri seç).
   {dil_talimati}
4. confusable_with: bu konunun içeriğiyle KARIŞTIRILMASI MUHTEMEL diğer konu başlıkları (yoksa boş liste).
   Ölçüt: aynı dersin içinde benzer isimli, benzer süreçli veya zıt işlevli konular.
5. slide_refs: konunun geçtiği slide numaraları.
6. Yalnızca JSON döndür, şu şema ile:
{{"topics": [{{"topic": "...", "keywords": ["...", "..."], "slide_refs": [1, 2], "confusable_with": ["..."]}}]}}
"""

NOTE_GENERATION_PROMPT = (
    """Sen bir üniversite ders notu yazarısın. Aşağıda ders sunumunun "{topic}" konusundaki rehber içeriği ve ders kitabından alınan kaynak parçaları var.

KURALLAR:
1. """
    + KAYNAK_DISI_BILGI_YASAGI
    + """
2. "{topic}" konusunu eksiksiz ve anlaşılır biçimde açıkla; öğrenci seviyesine uygun yaz. {dil_talimati}
3. Her bilgi parçasının sonuna kaynak atıf numarasını [n] biçiminde koy (n: KAYNAKLAR listesindeki numara).
4. Not "{topic}" KONUSUNU anlatır, sunumu anlatmaz: REHBER (sunum) yalnızca destekleyici malzemedir.
   "Sunumda ... listelenir/verilir", "Slayt N'de ...", "[Slide N]" gibi sunumu anlatan ifadeler YASAK;
   rehberdeki bilgiyi kendi cümlelerinle tanım + neden-sonuç/karşılaştırma/örnek içeren bir açıklamaya
   çevir. Her kavram maddesi 2-3 cümlelik bağımsız bir açıklama olsun; çıplak madde listesi bırakma.
5. YAPI (bu sırayla ve bu etiketlerle üret):
   a) Kısa giriş: konunun ne olduğu ve neden önemli olduğu (2-3 cümle).
   b) **Kavramlar**: her kavram tek bir madde olsun; kavram adı **kalın** yazılsın.
      Bir madde en fazla 3 satır olsun — uzun içeriği alt maddelere ayır.
   c) **Neden böyle?** (en fazla 3 madde): konunun kritik olguları için nedensel açıklama.
      Her madde "Neden ... ?" sorusu ile başlasın, cevabı tek paragraf olsun ve [n] atfı taşısın.
      Soruların cevabı kaynaklarda YOKSA o maddeyi hiç yazma.
   d) **Kendini sına** (3 soru): konuyu okuyup geçen öğrencinin cevaplayabileceği, kaynaklardan
      doğrulanabilir kısa cevaplı sorular. Her sorunun cevabını HEMEN ALTINA "**Cevap:**" olarak yaz.
      Sorular konuyu olduğu gibi tekrar ettirmesin; "neden", "ne olurdu", "hangisi farklı" tipinde olsun.
   e) **Hatırlatıcı**: konunun en kritik 3-5 bilgisini TEK SATIR özetler halinde ver.
6. Bilişsel yük: kavram yoğunluğu yüksek bölümlerde paragrafları kısa tut; gereksiz tekrar, süs
   cümlesi, giriş/geçiş nezaket ifadesi YAZMA. Her cümle bilgi taşımalı.
7. Bölümü tam olarak "### {topic}" başlığıyla başlat (başka bir markdown başlığı KULLANMA; alt
   bölümleri yukarıdaki **kalın** etiketlerle ayır).

KONU: {topic}

REHBER (sunum):
{slide_content}

KAYNAKLAR:
{numbered_sources}
{kazanimlar}
ÇIKTI: Markdown not bölümü (inline atıflı, "Kendini sına" bölümü dahil).
"""
)

COVERAGE_CHECK_PROMPT = """Aşağıdaki konu kontrol listesi ve üretilmiş not var. İki denetim yap:

A) KAPSAM: hangi konular notta YETERSİZ ya da EKSİK?
B) ÖĞRENME YAPISI: aşağıdaki bozukluklardan hangileri var?
   - "Kendini sına" bölümü yok/boş ya da soruların cevapları yazılmamış
   - Sorulardan biri yalnızca "…nedir?" biçiminde (konuyu tekrar ettiren, üst düzey düşünme istemeyen)
   - Atıfsız [n] iddia
   - Tek cümlede 3'ten fazla yeni kavram (bilişsel yük)
   - Aynı bilgiyi üç kez tekrarlayan paragraf

KONU LİSTESİ: {topics}

NOT:
{note}

Yalnızca JSON döndür:
{{"missing": ["konu başlığı", ...], "structure_issues": [{{"topic": "...", "issue": "kısa açıklama"}}]}}
(eksik/bozukluk yoksa ilgili liste boş)
"""

CITATION_CONFIRM_PROMPT = """Bir not parçasındaki alıntı, kaynak parçada birebir geçmiyor. Alıntı, kaynak parçanın içeriğini destekliyor mu?

ALINTI: {quote}

KAYNAK PARÇA: {chunk_text}

Yalnızca JSON döndür: {{"supported": true}} ya da {{"supported": false}}
"""

NOTE_GENERATION_WEB_PROMPT = """Sen bir üniversite ders notu yazarısın. Aşağıda "{topic}" konusundaki web kaynakları var.

KURALLAR:
1. SADECE sağlanan web kaynaklarını kullan; kaynaklarda olmayan bilgi EKLEME.
2. "{topic}" konusunu eksiksiz ve anlaşılır biçimde açıkla; öğrenci seviyesine uygun yaz. {dil_talimati}
3. Her bilgi parçasının sonuna kaynak atıf numarasını [n] biçiminde koy (n: KAYNAKLAR listesindeki numara).
4. Kaynak başlığından emin değilsen genel ifade kullan.
5. Madde işaretleri ve kısa paragraflar kullan; gereksiz tekrar yapma.
6. Bölümü tam olarak "### {topic}" başlığıyla başlat (başka başlık düzeyi/ifade kullanma).

KONU: {topic}

KAYNAKLAR:
{numbered_sources}
{kazanimlar}
ÇIKTI: Markdown not bölümü (inline atıflı).
"""

NOTE_SLIDE_ONLY_PROMPT = """Ders kitabı ve web'de kaynak bulunamadı. Aşağıdaki sunum (rehber) içeriğinden "{topic}" konusunu eksiksiz, öğrenci seviyesinde TAM bir not olarak yaz. Atıf ekleme ([n] kullanma). {dil_talimati}

KURALLAR:
1. Bölümü tam olarak "### {topic}" başlığıyla başlat (başka başlık düzeyi/ifade kullanma).
2. Not konuyu anlatır, sunumu anlatmaz: "Sunumda ... listelenir/verilir", "Slayt N'de ...",
   "[Slide N]" gibi sunumu anlatan ifadeler YASAK; rehberdeki maddeleri kendi cümlelerinle
   tanım + neden-sonuç/karşılaştırma/örnek içeren açıklamalara çevir. Her kavram en az 2-3
   cümleyle açıklanır; çıplak madde listesi bırakma.
3. Madde işaretleri ve kısa paragraflar kullan; gereksiz tekrar yapma.

REHBER:
{slide_content}
{kazanimlar}
ÇIKTI: Markdown not bölümü (atıfsız).
"""
