# ruff: noqa: E501 — prompt şablonları doğal dil metnidir; satır uzunluğu kısıtı uygulanmaz
"""Sınav sonrası muhasebe özet prompt'u (v3 — direktif sertleştirme)."""

from .common import CIKTI_SOZLESMESI_JSON

POSTMORTEM_SUMMARY_PROMPT = (
    """Görevin: bir öğrencinin "{exam_title}" sınavında kaçırdığı soruların SEBEP DAĞILIMINA bakıp
TEK CÜMLELİK, somut ve eyleme dönük bir çalışma tavsiyesi yazmak.

"""
    + CIKTI_SOZLESMESI_JSON
    + """

ADIM ADIM YORDAM:
1. Listedeki sebepleri say. Hangi sebep en çok tekrar ediyorsa BASKIN sebep odur.
2. Baskın sebebe göre tavsiyeyi şu eşlemeden seç:
   - "bilmiyordum" → eksik konuyu yeniden çalışma ve kendini sınama adımı.
   - "karıştırdım" → karıştırılan ikiliyi ayırt eden pratik adımı.
   - "süre_yetmedi" → süre bölme ve hız denemesi adımı.
   - "dikkatsizlik" → cevap kontrol alışkanlığı adımı.
3. Tavsiyeyi TEK cümle yaz. Sayı veya süre içersin (ör. "10 soru", "15 dakika").
4. Sınavda geçen SOMUT konu adlarını kullan; "konuları tekrar et" gibi genel cümle YASAK.
5. Öğrenciyi suçlama; ne yapacağını söyle.

{dil_talimati}

ŞEMA: {{"summary": "tek cümlelik tavsiye"}}

ALTIN REFERANS 1 (baskın sebep: karıştırdım):
{{"summary": "Klasik ve edimsel koşullanmayı ayırt eden 10 örnek soru çöz ve her birinde ödül/ceza var mı diye işaretle."}}

ALTIN REFERANS 2 (baskın sebep: süre_yetmedi):
{{"summary": "Bellek ve öğrenme bölümünden 15 dakikalık 12 soruluk deneme yap ve her soruya en fazla 70 saniye ayır."}}

KAÇIRILAN SORULAR VE SEBEPLERİ:
{items}"""
)
