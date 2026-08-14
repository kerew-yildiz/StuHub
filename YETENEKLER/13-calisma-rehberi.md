# Yetenek 13 — Çalışma Rehberi

> **Sahibi:** Çalışma Rehberi Ajanı (`AJANLAR/19-calisma-rehberi-ajani.md`). Bu dosya, chapter ve ders seviyesi özet + kavram haritası üretim sözleşmesidir.

## Amaç
Chapter notundan özet, anahtar terim listesi ve sınav odakları çıkarmak; opsiyonel kavram haritası üretmek; ders seviyesinde bunları tek rehberde birleştirmek.

## Girdiler
- Chapter notu: `content_md` (**retrieval YOK** — not zaten atıflıdır; yeni kaynak araması yapılmaz).
- Model: DeepSeek chat API (JSON modu — `chat_json`).

## Adım Adım İş Akışı

### 1. Chapter özeti
- `content_md` tek girdi; çıktı şeması:
  ```json
  {
    "summary_md": "Chapter özeti (kısa markdown)...",
    "key_terms": ["terim1", "terim2"],
    "exam_focus": ["sınavda öne çıkacak nokta1", "..."]
  }
  ```
- `key_terms` yalnızca notta geçen terimlerden oluşur; terimler not atıflarına işaret edebilir (atıf ile gösterilebilir).

### 2. Kavram haritası (opsiyonel)
```json
{
  "nodes": [ { "id": "n1", "label": "Fosfolipid çift katman", "importance": 3 } ],
  "edges": [ { "from": "n1", "to": "n2", "label": "oluşturur" } ]
}
```
- `nodes` **yalnız notta geçen kavramlar**; `edges` bu düğümler arası ilişkiler.
- Harita **çevrimsiz (DAG)** olmalıdır (topolojik sıralama ile doğrulanır).

### 3. Ders seviyesi rehber
- Chapter rehberleri LLM ile **birleştirilir** (tek rehber); `generation_logs` kind=`guide`.
- Chapter özetleri girdi, ders özeti + ortak `key_terms`/`exam_focus` çıktı.

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Haritada çevrim tespiti | Döngü kırılır (en düşük önemli kenar atılır) veya yeniden üretim |
| Notta olmayan kavram (düğüm) | Düğüm reddedilir (yalnız not kavramları) |
| JSON şema ihlali | `_extract_json` onarımı; başarısızsa yeniden üretim |
| Not boş/özetlenemez | "Önce not oluştur" rehber mesajı |

## Kabul Kriterleri
- Özet şeması (`summary_md` + `key_terms` + `exam_focus`) geçerli
- Kavram haritası çevrimsiz (DAG); düğümler yalnız not kavramları
- Terimler not atıflarına işaret edebilir (atıf gösterimi mümkün)
- Ders rehberi chapter rehberlerinin LLM birleşimi; `generation_logs` kind=`guide`
