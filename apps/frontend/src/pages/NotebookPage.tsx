import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { slidesApi, type Slide } from '../api/slides'
import { GuideSlidesForm } from '../components/GuideSlidesForm'

type LoadState = 'loading' | 'ready' | 'error'

/** Chapter detay sayfası — guide slides + (Faz 3+ not/quiz butonları). */
export function NotebookPage() {
  const { courseId, chapterId } = useParams<{ courseId: string; chapterId: string }>()
  const numericChapterId = Number(chapterId)

  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [slides, setSlides] = useState<Slide[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!numericChapterId) return
    setState('loading')
    try {
      const [chapterData, slideList] = await Promise.all([
        chaptersApi.get(numericChapterId),
        slidesApi.listByChapter(numericChapterId),
      ])
      setChapter(chapterData)
      setSlides(slideList)
      setState('ready')
    } catch {
      setState('error')
      setError('Chapter yüklenemedi. Lütfen tekrar deneyin.')
    }
  }, [numericChapterId])

  useEffect(() => {
    void load()
  }, [load])

  const handleUpload = async (file: File) => {
    await slidesApi.upload(numericChapterId, file)
    await load()
  }

  const handleDeleteSlide = async (slideId: number) => {
    if (!window.confirm('Bu slide silinecek. Emin misin?')) return
    try {
      await slidesApi.remove(slideId)
      setSlides((prev) => prev.filter((s) => s.id !== slideId))
    } catch {
      setError('Slide silinemedi. Lütfen tekrar deneyin.')
    }
  }

  return (
    <section>
      <Link
        to={`/dersler/${courseId ?? ''}`}
        className="text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:text-stuhub-text"
      >
        ← Derse dön
      </Link>
      <div className="mt-2">
        <h1 className="text-3xl font-semibold">{chapter?.title ?? 'Chapter'}</h1>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-sm bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      {state === 'loading' && (
        <p className="mt-8 text-sm text-stuhub-text-secondary">Yükleniyor…</p>
      )}

      {/* Guide slides */}
      <div className="mt-8">
        <h2 className="text-xl font-semibold">Guide Slides</h2>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          Hocanın sunumu — not üretiminin rehberi. PDF ya da PPTX yükleyebilirsin.
        </p>
        <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-5">
          <GuideSlidesForm onUpload={handleUpload} />
        </div>

        <div className="mt-5 space-y-3">
          {slides.length === 0 && (
            <p className="text-sm text-stuhub-text-secondary">
              Henüz slide yok. Yukarıdan sunum yükleyerek başla.
            </p>
          )}
          {slides.map((slide) => (
            <details
              key={slide.id}
              className="rounded-md border border-stuhub-border bg-stuhub-surface"
            >
              <summary className="flex cursor-pointer items-center justify-between px-5 py-3 font-medium">
                <span>
                  Slide {slide.slide_no}
                  {slide.content_text ? '' : ' (metin yok)'}
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    void handleDeleteSlide(slide.id)
                  }}
                  className="rounded-sm px-2 py-1 text-sm text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
                  aria-label={`Slide ${slide.slide_no} sil`}
                >
                  Sil
                </button>
              </summary>
              {slide.content_text && (
                <div className="border-t border-stuhub-border px-5 py-3 text-sm leading-relaxed text-stuhub-text-secondary">
                  {slide.content_text}
                </div>
              )}
            </details>
          ))}
        </div>
      </div>

      {/* Faz 3+ üretim butonları (hazırlık) */}
      <div className="mt-10 flex gap-4">
        <button
          type="button"
          disabled
          className="rounded-sm bg-stuhub-surface px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
          title="Faz 3'te geliyor"
        >
          Not Oluştur (Faz 3)
        </button>
        <button
          type="button"
          disabled
          className="rounded-sm bg-stuhub-surface px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
          title="Faz 4'te geliyor"
        >
          Quiz (Faz 4)
        </button>
      </div>
    </section>
  )
}
