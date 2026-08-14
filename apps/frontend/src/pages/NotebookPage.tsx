import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { getNote, streamNoteGeneration, type SavedNote } from '../api/notes'
import { getQuiz, streamQuizGeneration, type Quiz } from '../api/quizzes'
import { slidesApi, type Slide } from '../api/slides'
import { GuideSlidesForm } from '../components/GuideSlidesForm'
import { NoteViewer } from '../components/NoteViewer'
import { QuizPlayer } from '../components/QuizPlayer'

type LoadState = 'loading' | 'ready' | 'error'

/** Chapter detay sayfası — guide slides + not üretimi + bölüm quizi (Faz 2/3/4). */
export function NotebookPage() {
  const { courseId, chapterId } = useParams<{ courseId: string; chapterId: string }>()
  const numericChapterId = Number(chapterId)

  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [slides, setSlides] = useState<Slide[]>([])
  const [note, setNote] = useState<SavedNote | null>(null)
  const [quiz, setQuiz] = useState<Quiz | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')

  // üretim durumu
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusMessage, setStatusMessage] = useState('')
  const [liveContent, setLiveContent] = useState('')

  // quiz durumu
  const [quizGenerating, setQuizGenerating] = useState(false)
  const [quizProgress, setQuizProgress] = useState(0)
  const [quizMessage, setQuizMessage] = useState('')
  const [quizKey, setQuizKey] = useState(0)

  const load = useCallback(async () => {
    if (!numericChapterId) return
    setState('loading')
    try {
      const [chapterData, slideList, existingNote, existingQuiz] = await Promise.all([
        chaptersApi.get(numericChapterId),
        slidesApi.listByChapter(numericChapterId),
        getNote(numericChapterId),
        getQuiz(numericChapterId),
      ])
      setChapter(chapterData)
      setSlides(slideList)
      setNote(existingNote)
      setQuiz(existingQuiz)
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

  const handleGenerate = async () => {
    setGenerating(true)
    setProgress(0)
    setStatusMessage('Hazırlanıyor…')
    setLiveContent('')
    setError('')
    await streamNoteGeneration(numericChapterId, {
      onStatus: (percent, message) => {
        setProgress(percent)
        setStatusMessage(message)
      },
      onDelta: (text) => setLiveContent((prev) => prev + text),
      onDone: (savedNote) => {
        setNote(savedNote)
        setLiveContent('')
        setProgress(100)
        setStatusMessage('Not hazır.')
        setGenerating(false)
      },
      onError: (message) => {
        setError(message)
        setGenerating(false)
      },
    })
  }

  const handleGenerateQuiz = async () => {
    setQuizGenerating(true)
    setQuizProgress(0)
    setQuizMessage('Hazırlanıyor…')
    setError('')
    await streamQuizGeneration(numericChapterId, {
      onStatus: (percent, message) => {
        setQuizProgress(percent)
        setQuizMessage(message)
      },
      onDone: (newQuiz) => {
        setQuiz(newQuiz)
        setQuizKey((k) => k + 1)
        setQuizGenerating(false)
        setQuizMessage('')
      },
      onError: (message) => {
        setError(message)
        setQuizGenerating(false)
      },
    })
  }

  const canGenerate = slides.length > 0
  const canGenerateQuiz = note !== null

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

      {/* Not üretimi */}
      <div className="mt-10">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Not</h2>
          <button
            type="button"
            onClick={() => void handleGenerate()}
            disabled={generating || !canGenerate}
            className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-50"
            title={canGenerate ? '' : 'Önce guide slides yükle'}
          >
            {generating ? 'Üretiliyor…' : 'Not Oluştur'}
          </button>
        </div>

        {generating && (
          <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-5">
            <p className="text-sm font-medium">{statusMessage}</p>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-stuhub-border">
              <div
                className="h-full bg-stuhub-accent transition-all duration-300"
                style={{ width: `${Math.max(progress, 2)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-stuhub-text-secondary">
              {Math.round(progress)}% tamamlandı
            </p>
            {liveContent && (
              <pre className="mt-4 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-sm bg-stuhub-bg p-3 text-sm text-stuhub-text-secondary">
                {liveContent}
              </pre>
            )}
          </div>
        )}

        {!generating && note && <NoteViewer note={note} />}
        {!generating && !note && !error && (
          <p className="mt-4 text-sm text-stuhub-text-secondary">
            Henüz not yok. Guide slides yükleyip “Not Oluştur” ile başla.
          </p>
        )}
      </div>

      {/* Bölüm quizi */}
      <div className="mt-10">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Quiz</h2>
          <button
            type="button"
            onClick={() => void handleGenerateQuiz()}
            disabled={quizGenerating || !canGenerateQuiz}
            className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-50"
            title={canGenerateQuiz ? '' : 'Önce not oluştur'}
          >
            {quizGenerating ? 'Üretiliyor…' : quiz ? 'Quiz\'i Yenile' : 'Quiz Oluştur'}
          </button>
        </div>

        {quizGenerating && (
          <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-5">
            <p className="text-sm font-medium">{quizMessage}</p>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-stuhub-border">
              <div
                className="h-full bg-stuhub-accent transition-all duration-300"
                style={{ width: `${Math.max(quizProgress, 2)}%` }}
              />
            </div>
          </div>
        )}

        {!quizGenerating && quiz && <QuizPlayer key={quizKey} quiz={quiz} />}
        {!quizGenerating && !quiz && !error && (
          <p className="mt-4 text-sm text-stuhub-text-secondary">
            Henüz quiz yok. Not oluşturup “Quiz Oluştur” ile başla.
          </p>
        )}
      </div>
    </section>
  )
}

