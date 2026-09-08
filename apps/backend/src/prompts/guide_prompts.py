"""Çalışma rehberi prompt şablonları (Yetenek 13)."""

from __future__ import annotations

from .common import dil_talimati  # noqa: F401 — geriye uyumlu yeniden dışa aktarım

SUMMARY_PROMPT = """Sen bir üniversite ders asistanısın. Aşağıda bir ders notunun TAM metni var.

GÖREV: Öğrenci için bir ÇALIŞMA REHBERİ üret.

KURALLAR:
1. SADECE notta geçen bilgileri kullan; notta olmayan bilgi EKLEME.
2. {dil_talimati}
3. Şu JSON şemasına birebir uy (``` işareti kullanma):
{{
  "summary_md": "kısa bölüm özeti (markdown, madde işaretli, 200-400 kelime)",
  "key_terms": ["anahtar terimler (5-15 adet, her biri 1-4 kelime)"],
  "exam_focus": ["sınavda çıkması muhtemel odak noktaları (3-8 adet, cümle halinde)"]
}}

NOT METNİ:
{note_md}
"""

CONCEPT_MAP_PROMPT = """Sen bir üniversite ders asistanısın. Aşağıda bir ders notunun TAM metni var.

GÖREV: Notun kavram haritasını üret (yönlü, çevrimsiz — DAG).

KURALLAR:
1. Yalnızca notta GEÇEN kavramları düğüm yap; hayali kavram EKLEME.
2. Kenarlar "A → B" = "A, B'nin önkoşulu/üst kavramı" anlamında; çevrim OLUŞTURMA.
3. {dil_talimati}
4. Şu JSON şemasına birebir uy (``` işareti kullanma):
{{
  "nodes": [{{"id": "k1", "label": "kavram adı", "importance": 1}}],
  "edges": [{{"from": "k1", "to": "k2", "label": "ilişki (2-4 kelime)"}}]
}}
- nodes: 5-20 düğüm; importance 1 (düşük) - 3 (çekirdek).
- edges: her kenarın from/to değeri nodes içindeki bir id olmalı.

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
2. Her ikili için en az 1 benzerlik, en az 2 ayırt edici fark ve öğrencilerin bu
   ikilide en sık karıştırdığı noktayı yaz.
3. Farklarda "aspect" karşılaştırma ölçütüdür (ör. "bellek karmaşıklığı"); "a" ve "b"
   sırasıyla ikilinin birinci ve ikinci kavramına ait değerdir.
4. {dil_talimati}
5. Şu JSON şemasına birebir uy (``` işareti kullanma):
{{
  "concepts": ["kavram adları (girdiyle aynı sırada)"],
  "pairs": [
    {{
      "a": "birinci kavram",
      "b": "ikinci kavram",
      "similarities": ["ortak nokta (1-4 adet, cümle halinde)"],
      "differences": [{{"aspect": "ölçüt (1-4 kelime)", "a": "a'daki durum", "b": "b'deki durum"}}],
      "confusion": "bu ikilide en sık karıştırılan nokta (tek cümle)"
    }}
  ]
}}

DERS BAĞLAMI:
{context_md}
"""
