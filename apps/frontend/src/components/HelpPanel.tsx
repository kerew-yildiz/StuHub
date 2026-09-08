import { MagnifyingGlass, Question } from '@phosphor-icons/react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useHelpStore } from '../stores/helpStore'

interface HelpEntry {
  id: string
  group: string
  title: string
  body: string
}

// Görev odaklı, aranabilir yardım içeriği — ders sayfasındaki 4 bölümle aynı
// yapıyı kullanır (2026-09-08 kritik incelemede "Jordan/ilk-kullanıcı" ve
// "Yardım ve Dokümantasyon" bulgusu: hiçbir yerde aranabilir yardım yoktu).
const HELP_ENTRIES: HelpEntry[] = [
  {
    id: 'coverage',
    group: 'Genel',
    title: 'Kaynak kapsaması nedir?',
    body: 'Üretilen notun, yüklediğin kitabın hangi sayfalarını kaynak olarak kullandığını gösterir. Sarı bir uyarı görürsen, not eski/artık var olmayan bir kaynağa atıf yapıyor demektir — notu yeniden oluşturmayı dene.',
  },
  {
    id: 'streak',
    group: 'Genel',
    title: 'Streak (gün serisi) nasıl çalışır?',
    body: 'Her gün not üretme, quiz çözme, kart tekrarlama ya da materyale soru sorma gibi bir etkinlik yaptığında streak\'in artar. Günlük hedefe (varsayılan 3 etkinlik) ulaşınca halka dolar.',
  },
  {
    id: 'indexing',
    group: 'Genel',
    title: 'Kitap ile Sunum arasındaki fark ne?',
    body: 'Kitap (PDF) yüklediğinde arka planda indekslenir (sayfa sayfa aranabilir hale gelir) — bu birkaç dakika sürebilir. Sunum (guide slide) hiç indekslenmez, doğrudan not üretiminin taslağı/rehberi olarak kullanılır; bu yüzden anında "Kullanıma hazır" görünür.',
  },
  {
    id: 'shortcuts',
    group: 'Genel',
    title: 'Klavye kısayolları',
    body: 'Ctrl/Cmd+K: herhangi bir dönem/derse hızlı git. Ders sayfasında 1-4 tuşları: Öğren/Pratik Yap/Sınava Hazırlan/Ödev bölümleri arası geçiş. Esc: açık pencereyi/onay kutusunu kapatır.',
  },
  {
    id: 'overview',
    group: 'Öğren',
    title: 'Genel Bakış',
    body: "Chapter'ları ve materyalleri (kitap/sunum) buradan eklersin, düzenlersin, silersin. Her chapter'ın notu, kartları ve quiz'i buradan açılır.",
  },
  {
    id: 'guide',
    group: 'Öğren',
    title: 'Rehber',
    body: 'Hocanın sunumundan (guide slide) otomatik çıkarılan konu özetini gösterir — notun hangi konu sırasını izlediğini görmek için.',
  },
  {
    id: 'study',
    group: 'Öğren',
    title: 'Karşılaştır & Sözlük',
    body: 'İki konuyu yan yana karşılaştırır (örn. "İd vs Ego") ve derste geçen terimlerin tanımlarını sözlük gibi listeler.',
  },
  {
    id: 'quiz',
    group: 'Pratik Yap',
    title: 'Genel Quiz',
    body: "Dersin tüm chapter notlarından tek seferlik, karışık (çoktan seçmeli/doğru-yanlış/boşluk doldurma/açık uçlu) geniş bir quiz üretir.",
  },
  {
    id: 'cards',
    group: 'Pratik Yap',
    title: 'Bugünün Kartları',
    body: 'Aralıklı tekrar (spaced repetition) algoritmasına göre bugün tekrar etmen gereken flashcard\'ları listeler.',
  },
  {
    id: 'feed',
    group: 'Pratik Yap',
    title: 'Kaydırarak Quiz',
    body: 'Sosyal medya akışı gibi, kaydırarak ilerleyen kısa soru-cevap formatı — pasif tekrar için.',
  },
  {
    id: 'ask',
    group: 'Pratik Yap',
    title: 'Materyale Sor',
    body: 'Yüklediğin kitap/sunuma doğrudan soru sorarsın; yanıt hangi sayfadan geldiğini kaynak göstererek verir.',
  },
  {
    id: 'exam',
    group: 'Sınava Hazırlan',
    title: 'Sınav Planı',
    body: 'Sınav tarihini girersin; geri sayım başlar ve kalan güne göre chapter tekrarların dengeli dağıtılır.',
  },
  {
    id: 'heatmap',
    group: 'Sınava Hazırlan',
    title: 'Zayıf Konular',
    body: 'Quizlerde en çok hata yaptığın konuları bir ısı haritasında gösterir — nereye daha çok zaman ayırman gerektiğini görürsün.',
  },
  {
    id: 'errors',
    group: 'Sınava Hazırlan',
    title: 'Hatalarım',
    body: 'Tüm quizlerde yanlış cevapladığın sorular tek yerde birikir; aynı konuda birden fazla hata yaptıysan işaretlenir.',
  },
  {
    id: 'smart',
    group: 'Sınava Hazırlan',
    title: 'Bugün Ne Çalışsam',
    body: 'Unutma eğrisi ve hata geçmişine bakarak bugün hangi konuya öncelik vermen gerektiğini önerir.',
  },
  {
    id: 'essay',
    group: 'Ödev',
    title: 'Ödev Değerlendir',
    body: 'Yazdığın bir ödev/makaleyi ders materyaline dayalı olarak değerlendirir, eksik/hatalı noktaları gösterir.',
  },
  {
    id: 'draft',
    group: 'Ödev',
    title: 'Ödev Taslak Koçu',
    body: 'Bitmemiş bir ödev taslağına puan vermeden, yalnızca yönlendirici geri bildirim verir — henüz teslim etmeden önce yön bulman için.',
  },
]

const GROUP_ORDER = ['Genel', 'Öğren', 'Pratik Yap', 'Sınava Hazırlan', 'Ödev']

export function HelpPanel() {
  const open = useHelpStore((s) => s.open)
  const toggle = useHelpStore((s) => s.toggle)
  const close = useHelpStore((s) => s.close)
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const typing =
        target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA' || target?.isContentEditable
      if (event.key === '?' && !typing) {
        event.preventDefault()
        toggle()
      } else if (event.key === 'Escape' && open) {
        close()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, toggle, close])

  useEffect(() => {
    if (open) {
      setQuery('')
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  const grouped = useMemo(() => {
    const q = query.trim().toLocaleLowerCase('tr')
    const filtered = q
      ? HELP_ENTRIES.filter(
          (e) =>
            e.title.toLocaleLowerCase('tr').includes(q) || e.body.toLocaleLowerCase('tr').includes(q),
        )
      : HELP_ENTRIES
    return GROUP_ORDER.map((group) => ({
      group,
      entries: filtered.filter((e) => e.group === group),
    })).filter((g) => g.entries.length > 0)
  }, [query])

  return (
    <>
      <button
        type="button"
        onClick={toggle}
        aria-label="Yardım"
        title="Yardım (?)"
        className="glass-panel-subtle glass-interactive flex h-8 w-8 shrink-0 items-center justify-center rounded-control text-stuhub-text-secondary"
      >
        <Question size={16} weight="bold" aria-hidden="true" />
      </button>

      {open && (
        <div
          role="presentation"
          className="fixed inset-0 z-[100] flex items-start justify-center bg-black/50 p-4 pt-[10vh] backdrop-blur-sm"
          onClick={close}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Yardım"
            className="glass-panel flex max-h-[75vh] w-full max-w-lg flex-col overflow-hidden p-0"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center gap-2 border-b border-stuhub-border px-4 py-3">
              <MagnifyingGlass size={18} className="shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Yardımda ara… (örn. streak, kapsama, kısayol)"
                aria-label="Yardımda ara"
                className="w-full bg-transparent text-sm text-stuhub-text placeholder:text-stuhub-text-muted focus:outline-none"
              />
              <kbd className="shrink-0 rounded-control border border-stuhub-border px-1.5 py-0.5 text-xs text-stuhub-text-muted">
                Esc
              </kbd>
            </div>
            <div className="overflow-y-auto p-4">
              {grouped.length === 0 && (
                <p className="py-6 text-center text-sm text-stuhub-text-secondary">Sonuç yok.</p>
              )}
              {grouped.map(({ group, entries }) => (
                <div key={group} className="mb-5 last:mb-0">
                  <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-stuhub-text-muted">
                    {group}
                  </h3>
                  <div className="space-y-3">
                    {entries.map((entry) => (
                      <div key={entry.id}>
                        <p className="text-sm font-medium text-stuhub-text">{entry.title}</p>
                        <p className="mt-0.5 text-sm text-stuhub-text-secondary">{entry.body}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
