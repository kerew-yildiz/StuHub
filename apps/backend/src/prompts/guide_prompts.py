"""Çalışma rehberi prompt şablonları (Yetenek 13)."""

from __future__ import annotations

from .common import dil_talimati  # noqa: F401 — geriye uyumlu yeniden dışa aktarım

SUMMARY_PROMPT = """Sen bir üniversite ders asistanısın. Aşağıda bir ders notunun TAM metni var.

GÖREV: Öğrenci için bir ÇALIŞMA REHBERİ üret. Özet, not yerine GEÇMEZ — notu okumayı
atlatmayacak, aksine notu okumaya hazırlayacak biçimde yazılır.

KURALLAR:
1. SADECE notta geçen bilgileri kullan; notta olmayan bilgi EKLEME.
2. {dil_talimati}
3. Şu JSON şemasına birebir uy (``` işareti kullanma):
{{
  "summary_md": "bölümün iskeleti: her madde tek bir bilgi iddiası (en fazla 25 kelime). \
Süsleme, gevezelik, 'bu bölümde anlatılmaktadır' türü kalıp cümle YOK. 150-300 kelime. \
Metnin sonuna '### Kendini sına' bölümü ekle: notu okumadan cevaplamayı deneyeceğin 3-5 soru; \
her sorunun cevabını hemen altına '**Cevap:**' olarak yaz.",
  "key_terms": ["anahtar terimler (5-15 adet, her biri 1-4 kelime)"],
  "exam_focus": ["sınavda çıkması muhtemel odak noktaları (3-8 adet, cümle halinde)"]
}}

NOT METNİ:
{note_md}
"""

CONCEPT_MAP_PROMPT = """Sen bir üniversite ders asistanısın. Aşağıda bir ders notunun TAM metni var.

GÖREV: Notun kavram haritasını üret (yönlü, çevrimsiz — DAG) ve her kenarı ÖĞRENCİYE SORULACAK
BİR HATIRLAMA SORUSUNA çevir. Harita, öğrencinin üzerinde çalışacağı bir iskelet; özet metni değil.

KURALLAR:
1. Yalnızca notta GEÇEN kavramları düğüm yap; hayali kavram EKLEME.
2. Kenarlar "A → B" = "A, B'nin önkoşulu/üst kavramı" anlamında; çevrim OLUŞTURMA.
3. {dil_talimati}
4. Şu JSON şemasına birebir uy (``` işareti kullanma):
{{
  "nodes": [{{"id": "k1", "label": "kavram adı", "importance": 1}}],
  "edges": [{{"from": "k1", "to": "k2", "label": "ilişki (2-4 kelime)",
              "question": "Bu ilişkiyi yoklayan tek soru (cevabı kısa olacak)"}}]
}}
- nodes: 5-20 düğüm; importance 1 (düşük) - 3 (çekirdek).
- edges: her kenarın from/to değeri nodes içindeki bir id olmalı; her kenarda "question" zorunlu.

NOT METNİ:
{note_md}
"""

COURSE_SUMMARY_PROMPT = """Sen bir üniversite ders asistanısın. Aşağıda bir dersin TÜM
chapter notları var.

GÖREV: Dersin genel ÇALIŞMA REHBERİNİ üret (tüm chapter'ları kapsasın).

KURALLAR:
1. SADECE verilen notlardan yararlan; dış bilgi EKLEME.
2. {dil_talimati}
3. Şu JSON şemasına birebir uy (``` işareti kullanma):
{{
  "summary_md": "ders geneli özet (markdown, chapter başlıklı bölümler, 300-600 kelime)",
  "key_terms": ["dersin anahtar terimleri (10-25 adet)"],
  "exam_focus": ["sınav odakları (5-12 adet, cümle halinde)"]
}}

CHAPTAR NOTLARI:
{notes_md}
"""

COMPARISON_PROMPT = """Sen bir üniversite ders asistanısın. Öğrenci, sınavda birbirine
karıştırdığı kavramları yan yana görmek istiyor.

GÖREV: Aşağıdaki kavramları İKİLİ olarak karşılaştıran bir tablo üret.

KARŞILAŞTIRILACAK KAVRAMLAR:
{concepts}

ZORUNLU İKİLİLER (her biri için tam olarak bir kayıt üret, fazlasını üretme):
{pairs}

KURALLAR:
1. SADECE aşağıdaki ders bağlamında geçen bilgileri kullan; dış bilgi EKLEME.
2. Her ikili için en az 1 benzerlik, en az 2 ayırt edici fark ve öğrencilerin bu ikilide en sık
   karıştırdığı noktayı yaz.
3. "differences" alanında "aspect" karşılaştırma ölçütüdür (ör. "bellek karmaşıklığı"); "a" ve "b"
   sırasıyla ikilinin birinci ve ikinci kavramına ait değerdir. Her "aspect" TEK bir ölçüt olsun;
   "genel olarak", "yapısı" gibi belirsiz ölçütler kullanma.
4. "confusion": karıştırmanın MEKANİZMASINI yaz — öğrenci hangi yüzey benzerliğe (aynı isim kökü,
   benzer süreç, benzer sonuç) aldanıp yanlış kavramı seçiyor.
5. "discriminator": öğrencinin sınavda 5 saniyede uygulayabileceği TEK bir ayırt etme testi yaz
   (ör. "soruda 'geri dönüşü olmayan' ifadesi geçiyorsa A'dır").
6. {dil_talimati}
7. Şu JSON şemasına birebir uy (``` işareti kullanma):
{{
  "concepts": ["kavram adları (girdiyle aynı sırada)"],
  "pairs": [
    {{
      "a": "birinci kavram",
      "b": "ikinci kavram",
      "similarities": ["ortak nokta (1-4 adet, cümle halinde)"],
      "differences": [{{"aspect": "ölçüt (1-4 kelime)", "a": "a'daki durum", "b": "b'deki durum"}}],
      "confusion": "karıştırma mekanizması (tek cümle)",
      "discriminator": "5 saniyelik ayırt etme testi"
    }}
  ]
}}

DERS BAĞLAMI:
{context_md}
"""
