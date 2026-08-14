# Yetenek 15 — Öğrenme Alışkanlıkları (Streak + Onboarding)

> **Sahibi:** Ana Ajan (orchestrasyon) + Backend/Frontend Geliştirici Ajanları (`AJANLAR/14-backend-gelistirici-ajani.md`, `AJANLAR/13-frontend-gelistirici-ajani.md`); UI denetimi Stil Ajanı (`AJANLAR/02-stil-ajani.md`). Bu dosya, yerel streak/günlük hedef türetimi ve 3 adımlı onboarding sözleşmesidir.

## Amaç
Kullanıcının çalışma sıklığını **yerelde** ölçmek (streak + günlük hedef halkası) ve ilk kullanımda dönem/ders ağacını 3 adımda kurmak; **kişisel kalır** (leaderboard/paylaşım yok).

## activity_log Olayları
- Şema: `{ "date": "YYYY-MM-DD", "kind": "note|quiz|flashcard|chat", "count": 1, "course_id": null }`.
- Aynı gün + aynı `kind` olayları **`count` olarak birleştirilir**; `course_id` opsiyoneldir.
- Yazma noktaları:
  - `note`: not üretimi tamamlandığında
  - `quiz`: quiz/genel quiz denemesi gönderildiğinde
  - `flashcard`: kart review (Again/Hard/Good/Easy) yapıldığında
  - `chat`: chat mesajı gönderildiğinde

## Türetme (saf fonksiyon)
- **streak** = bugün etkinse bugünden, dün etkinse dünden geriye doğru **kesintisiz aktif gün** sayısı (bugün de dün de inaktifse 0).
- **günlük hedef** = `settings.daily_goal` (varsayılan **3 etkinlik**; etkinlik = ayrı `kind` sayısı değil, gün toplamı).
- **halka** = `bugünkü_count / hedef` (0–1+; hedef aşılırsa dolu gösterilir).

```json
{ "streak": 4, "daily_goal": 3, "today_count": 2, "ring": 0.67 }
```

## Onboarding (3 adım — dönem yokken)
1. **Dönem adı:** "Dönemine bir ad ver" → `terms.name`.
2. **Dersler:** "Bu dönem hangi dersleri alıyorsun?" (virgülle ayrılmış) → her biri için `courses` kaydı.
3. **Özet + başlat:** kurulacak dönem/ders listesi gösterilir; onayla başlat.
- Tamamlanınca bayrak: `settings.onboarding_done = true`.

## Hata Modları
| Durum | Davranış |
|-------|----------|
| Streak girdisi eksik/bozuk tarih | O gün atlanır; kesintisiz sayım etkilenmez |
| `daily_goal` ≤ 0 | Varsayılan 3'e düşülür |
| Onboarding yarıda kesildi | Kaldığı adımdan devam; `onboarding_done` set edilmez |
| Leaderboard/paylaşım isteği | Reddedilir (kişisel kalır — yol haritası Bölüm 7.6) |

## Kabul Kriterleri
- Streak/ring saf fonksiyon + deterministik (birim testli)
- `activity_log` yazma noktaları eksiksiz (note/quiz/flashcard/chat)
- Onboarding 3 adım; `onboarding_done` bayrağı set edilir
- Leaderboard/paylaşım yok (kişisel kalır)
