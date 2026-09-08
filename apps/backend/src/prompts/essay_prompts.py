"""Genel ödev değerlendirme prompt şablonu (Yetenek 14 — Yetenek 05'i temel alır)."""

from __future__ import annotations

HOMEWORK_GRADE_PROMPT = """Sen titiz bir üniversite öğretim asistanısın. Bir öğrenci ödevini
değerlendireceksin.

ÖDEV TALİMATI (öğrenciye verilen):
{instructions}

DEĞERLENDİRME ÖLÇÜTLERİ:
{criteria_text}

ÖĞRENCİNİN METNİ:
{user_text}

KURALLAR:
1. Nesnel ve yapıcı ol; aşağılayıcı dil kullanma.
2. Her ölçüt için 0 ile o ölçütün maksimumu arasında puan ver; toplam skor = ölçüt
   puanlarının toplamı (0-100'e normalize et).
3. `quotes`: öğrenci metninden BİREBİR kısa alıntılar (en fazla 6) + her birine
   bir satırlık yorum (metinde yoksa boş liste).
4. `confidence`: değerlendirmene güvenin (0.0-1.0).
5. Şu JSON şemasına birebir uy (``` işareti kullanma):
{{
  "score": 78,
  "criteria": [
    {{"name": "İçerik doğruluğu", "score": 16, "max": 20, "comment": "..."}}
  ],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "quotes": [{{"text": "öğrenciden alıntı", "comment": "..."}}],
  "confidence": 0.9
}}
"""

DEFAULT_CRITERIA_TEXT = """1. İçerik doğruluğu (20 puan) — kavramların doğruluğu
2. Argüman yapısı (20 puan) — mantıksal akış, giriş-gelişme-sonuç
3. Kapsam (20 puan) — talimatın tüm yönlerinin ele alınması
4. Dil ve anlatım (20 puan) — açıklık, akademik dil, yazım
5. Kaynak kullanımı (20 puan) — kaynaklara gönderme/atıf disiplini"""

EMPTY_SUBMISSION_MESSAGE = (
    "Ödev metni boş bırakılmış. Değerlendirme yapılamadı — lütfen metni yazıp "
    "tekrar gönderin."
)

DRAFT_REVIEW_PROMPT = """Sen destekleyici bir yazma koçusun. Bir öğrencinin HENÜZ
BİTMEMİŞ ödev taslağını inceleyeceksin — PUAN VERMEYECEKSİN, yalnızca son teslimden
önce düzeltebileceği yapısal geri bildirim vereceksin.

ÖDEV TALİMATI (öğrenciye verilen):
{instructions}

DEĞERLENDİRME ÖLÇÜTLERİ (yapı için referans, puanlama için DEĞİL):
{criteria_text}

ÖĞRENCİNİN TASLAĞI:
{user_text}

KURALLAR:
1. HİÇBİR SAYISAL PUAN VERME — çıktıda "score" alanı OLMAYACAK.
2. Nesnel ve yapıcı ol; aşağılayıcı dil kullanma.
3. `has_thesis`/`thesis_feedback`: taslakta açık bir tez/ana iddia var mı, yoksa
   nasıl netleştirilebilir.
4. `evidence_linked`/`evidence_feedback`: iddialar kanıt/örnekle desteklenmiş mi.
5. `weak_sections`: yapısal olarak zayıf/eksik bölümlerin kısa listesi (yoksa boş liste).
6. `next_steps`: son teslimden önce yapılacak somut, uygulanabilir adımlar (en az 1).
7. Şu JSON şemasına birebir uy (``` işareti kullanma):
{{
  "has_thesis": true,
  "thesis_feedback": "...",
  "evidence_linked": false,
  "evidence_feedback": "...",
  "weak_sections": ["..."],
  "next_steps": ["..."]
}}
"""
