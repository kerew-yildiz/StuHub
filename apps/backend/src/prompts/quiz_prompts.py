# ruff: noqa: E501 — prompt şablonları doğal dil metnidir
"""Bölüm quizi üretim prompt'ları (Yetenek 03)."""

QUIZ_BATCH_PROMPT = """Aşağıdaki ders notu bölümünden "{topic}" hakkında TAM 5 çoktan seçmeli soru üret.

KURALLAR:
1. Sorular SADECE sağlanan not bölümü ve atıf listesindeki kaynaklardan üretilecek.
2. SEVİYE DAĞILIMI (Bloom): 5 soruyu şu dağılımla üret:
   - 2 soru "hatırla/anla": tanım, ayırt etme, ilişki kurma.
   - 2 soru "uygula/çözümle": verilen bir duruma/örneğe kuralı uygulama, nedeni bulma,
     parçalara ayırma, iki kavramın farkını ayırt etme.
   - 1 soru "değerlendir": bir iddiayı/kararı kaynağa dayanarak yargılama (ör. "hangisi
     doğru bir uygulamadır / hangi çıkarım kaynakla çelişir").
3. Her sorunun 4 seçeneği olacak. ÇELDİRİCİ KURALI: yanlış seçenekler aşağıdaki kaynaklardan türetilecek —
   (a) konuyla karıştırılan başka bir kavram, (b) eksik/yarım kalmış ifade,
   (c) doğru olguyu yanlış bağlama taşıma, (d) yaygın öğrenci yanılgısı.
   Komik, bariz yanlış, "hepsi doğru", "hiçbiri" gibi şıklar YASAK.
   Aynı çeldirici tipini iki soruda tekrar etme.
4. Her soru en az bir atıf taşıyacak (citations alanı; yalnızca ATIF LİSTESİ'ndeki id'ler kullanılacak).
5. Geribildirim: yanlış geribildirim "Doğru cevap: X. Neden: <tek cümle, doğru olanın neden doğru
   olduğunu açıklar>. Yanılgı: <seçilen şık neden cazip ve nerede yanlış>. [kaynak: [n] sayfa/slide]"
   biçiminde olacak. Doğru geribildirim yalnızca "Doğru!" DEĞİL; doğru cevabın neden doğru olduğunu
   bir cümleyle pekiştirecek.
6. Madde kökü en fazla 2 cümle olsun; tek soruda tek bilgi ölçülsün (bilişsel yük).
7. Yalnızca JSON döndür: {{"topic": "...", "questions": [{{"topic": "...", "question": "...", "options": ["","","",""], "correct_index": 0, "explanation": "...", "feedback_correct": "Doğru! ...", "feedback_wrong": "Doğru cevap: X. Neden: ... Yanılgı: ...", "citations": [{{"id": 1}}]}}]}}
8. Doğru cevap index dağılımı dengeli olsun (aynı şık en fazla 2 kez doğru olabilir).
9. {dil_talimati}

NOT BÖLÜMÜ:
{note_section}

ATIF LİSTESİ:
{citations_json}
{kazanimlar}"""
