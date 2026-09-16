# StuHub — Design Implementation Handoff

Bu teslim, `gpt-rapor-final(1).md` içindeki kanonik UI/UX sözleşmesini mevcut StuHub source tree üzerine uygular.

## Ana değişiklikler

- Dark-only monochrome glassmorphism ve canonical token sistemi.
- Montserrat font asset'leri frontend ve PDF export tarafında bundle edildi.
- Gerçek StuHub logo asset'i entegre edildi.
- İkon sistemi Lucide React'e geçirildi (`lucide-react`).
- Global / Dönem / Ders / Chapter navigation shell yeniden kuruldu.
- Collapsed sidebar + feature hover popout + mobile drawer davranışı eklendi.
- Header: hamburger, centered search, help, notification, profile, browser fullscreen.
- Focus Mode ve browser Fullscreen ayrımı korundu.
- Course / Chapter dashboard'ları ve secondary feature alanları canonical yapıya taşındı.
- Chapter normal Quiz akışı, Swipe Quiz'ten ayrı bir API ve workspace olarak eklendi.
- Gerçek çalışma oturumlarından son 7 günlük haftalık çalışma verisi eklendi.
- PDF export print-safe off-white görünüm, bundle edilmiş Montserrat ve logo/footer katmanı kullanacak şekilde güncellendi.
- Accessibility, reduced motion, disabled, empty/error/loading ve nested-scroll/card kuralları token seviyesinde uygulandı.

## Doğrulama

- Backend Python kaynakları `compileall` ile sözdizimi açısından doğrulandı.
- Frontend 127 TypeScript/TSX dosyası TypeScript parser ile sözdizimi açısından doğrulandı.
- Full frontend `tsc -b --noEmit` çalıştırılamadı çünkü teslim ortamında npm dependency tree kurulu değildi; eksik `@testing-library/jest-dom` ve `@types/node` bildirildi.
- Backend pytest çalıştırılamadı çünkü teslim ortamında `aiosqlite` kurulu değildi.
- Son ZIP'e local `node_modules`, build cache ve Python `__pycache__` dahil edilmez.

## Kurulum

Frontend:

```bash
cd apps/frontend
npm install
npm run typecheck
npm run test
npm run build
```

Backend:

```bash
cd apps/backend
uv sync
```

Lucide dependency `package.json`/`package-lock.json` içinde `lucide-react` olarak bulunur.
