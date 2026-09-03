# ruff: noqa: E501 — prompt şablonları doğal dil metnidir
"""Bölüm quizi üretim prompt'ları (Yetenek 03)."""

QUIZ_BATCH_PROMPT = """Aşağıdaki ders notu bölümünden "{topic}" hakkında TAM 5 çoktan seçmeli soru üret.

KURALLAR:
1. Sorular SADECE sağlanan not bölümü ve atıf listesindeki kaynaklardan üretilecek.
2. Her sorunun 4 seçeneği olacak; çeldiriciler makul ve aynı kaynaklardan türetilmiş olacak (komik/bariz yanlış yasak).
3. Her soru en az bir atıf taşıyacak (citations alanı; yalnızca ATIF LİSTESİ'ndeki id'ler kullanılacak).
4. Doğru/yanlış geribildirim metinlerini yaz; yanlış geribildirim "Doğru cevap: X. Açıklama: ... [kaynak: [n] sayfa/slide]" biçiminde atıflı olacak.
5. Yalnızca JSON döndür: {{"topic": "...", "questions": [{{"topic": "...", "question": "...", "options": ["","","",""], "correct_index": 0, "explanation": "...", "feedback_correct": "Doğru! ...", "feedback_wrong": "Doğru cevap: X. Açıklama: ...", "citations": [{{"id": 1}}]}}]}}
6. Doğru cevap index dağılımı dengeli olsun (aynı şık en fazla 2 kez doğru olabilir).
7. {dil_talimati}

NOT BÖLÜMÜ:
{note_section}

ATIF LİSTESİ:
{citations_json}
"""
