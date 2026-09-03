# ruff: noqa: E501 — prompt şablonları doğal dil metnidir
"""Flashcard üretim prompt'ları (Yetenek 09)."""

FLASHCARD_BATCH_PROMPT = """Aşağıda bir ders notunun "{topic}" bölümü, anahtar terimleri ve quiz soruları var.

KURALLAR:
1. SADECE sağlanan not bölümü ve kaynaklardan kart üret; kaynaklarda olmayan bilgi EKLEME.
2. İki tip kart üret: "qa" (soru→cevap) ve "term" (terim→tanım); konu başına 5–15 kart hedefle.
3. Her kart en az bir atıf taşıyacak (citations alanı); atıf yalnızca ATIF LİSTESİ'ndeki id'lerden seçilecek.
4. Kart cümleleri kısa, net, öğrenci seviyesinde Türkçe olacak.
5. Yalnızca JSON döndür ve şemaya birebir uy: {{"cards": [{{"topic": "...", "front": "...", "back": "...", "type": "qa", "citations": [{{"id": 1}}]}}]}}
6. type yalnızca "qa" ya da "term" olabilir; front soru/terim, back cevap/tanım metnidir.
7. {dil_talimati}

NOT BÖLÜMÜ:
{note_section}

ANAHTAR TERİMLER:
{keywords}

QUIZ SORULARI:
{questions}

ATIF LİSTESİ:
{citations_json}
"""
