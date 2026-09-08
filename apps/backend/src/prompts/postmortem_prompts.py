# ruff: noqa: E501 — prompt şablonları doğal dil metnidir
"""Sınav sonrası muhasebe özet prompt'u (Plan #44)."""

POSTMORTEM_SUMMARY_PROMPT = """Bir öğrenci "{exam_title}" sınavında aşağıdaki soruları kaçırdı;
her satırda soru ve öğrencinin kendi belirttiği kaçırma sebebi var:

{items}

Bu sebep dağılımına bakarak öğrenciye TEK CÜMLELİK, somut ve eyleme dönük bir çalışma
tavsiyesi yaz. Hangi sebep baskınsa ona odaklan: "bilmiyordum" → konuyu tekrar et,
"karıştırdım" → benzer kavramları ayırt eden pratik yap, "süre_yetmedi" → hız/zaman
yönetimi çalış, "dikkatsizlik" → cevap kontrol alışkanlığı edin.

{dil_talimati}

Yalnızca JSON döndür: {{"summary": "tek cümlelik tavsiye"}}
"""
