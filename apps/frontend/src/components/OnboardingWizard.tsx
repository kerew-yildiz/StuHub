import { useState } from 'react'

import { coursesApi } from '../api/courses'
import { settingsApi } from '../api/settings'
import { termsApi } from '../api/terms'

interface OnboardingWizardProps {
  /** Dönem/dersler kurulunca (ya da atlanınca) TermsPage listeyi tazeler. */
  onComplete: () => void
}

type Step = 1 | 2 | 3

/** Adım göstergesi — 1/2/3 (aktif adım accent). */
function StepIndicator({ current }: { current: Step }) {
  return (
    <div className="flex items-center gap-2" role="group" aria-label={`Adım ${current}/3`}>
      {([1, 2, 3] as const).map((n) => (
        <span
          key={n}
          aria-hidden="true"
          className={`h-2 w-2 rounded-pill transition-colors duration-[var(--duration-micro)] ${n === current ? 'bg-stuhub-accent' : 'bg-stuhub-border'}`}
        />
      ))}
      <span className="text-xs text-stuhub-text-secondary">{current}/3</span>
    </div>
  )
}

/** 3 adımlı ilk kurulum — dönem + dersler + özet (YETENEKLER/15). */
export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const [step, setStep] = useState<Step>(1)
  const [termName, setTermName] = useState('')
  const [coursesText, setCoursesText] = useState('')
  const [instructor, setInstructor] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const parsedCourses = coursesText
    .split(',')
    .map((c) => c.trim())
    .filter(Boolean)

  const handleStep1Next = () => {
    if (!termName.trim()) {
      setError('Dönem adı boş olamaz.')
      return
    }
    setError('')
    setStep(2)
  }

  const handleStep2Next = () => {
    if (parsedCourses.length === 0) {
      setError('En az bir ders adı gir.')
      return
    }
    setError('')
    setStep(3)
  }

  const handleStart = async () => {
    setBusy(true)
    setError('')
    try {
      const term = await termsApi.create({ name: termName.trim() })
      for (const name of parsedCourses) {
        await coursesApi.create(term.id, {
          name,
          instructor: instructor.trim() || null,
        })
      }
      await settingsApi.set('onboarding_done', '1')
      onComplete()
    } catch {
      setError('Dönem kurulamadı. Lütfen tekrar deneyin.')
    } finally {
      setBusy(false)
    }
  }

  const handleSkip = async () => {
    setBusy(true)
    setError('')
    try {
      await settingsApi.set('onboarding_done', '1')
      onComplete()
    } catch {
      setError('Kaydedilemedi. Lütfen tekrar deneyin.')
    } finally {
      setBusy(false)
    }
  }

  const inputClass =
    'w-full rounded-control border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-[var(--duration-micro)] focus:border-stuhub-accent'

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold">Dönemini kur</h2>
        <StepIndicator current={step} />
      </div>
      <p className="mt-1 text-sm text-stuhub-text-secondary">
        {step === 1 && 'Bu dönem hangi dönem?'}
        {step === 2 && 'Bu dönem hangi dersleri alıyorsun?'}
        {step === 3 && 'Özet — onaylayıp başla.'}
      </p>

      {step === 1 && (
        <div className="mt-4">
          <label htmlFor="ob-term-name" className="mb-1 block text-sm font-medium">
            Dönem adı
          </label>
          <input
            id="ob-term-name"
            type="text"
            value={termName}
            onChange={(e) => setTermName(e.target.value)}
            placeholder="Örn. 2026 Bahar"
            className={inputClass}
          />
        </div>
      )}

      {step === 2 && (
        <div className="mt-4 space-y-4">
          <div>
            <label htmlFor="ob-courses" className="mb-1 block text-sm font-medium">
              Dersler (virgülle ayır)
            </label>
            <input
              id="ob-courses"
              type="text"
              value={coursesText}
              onChange={(e) => setCoursesText(e.target.value)}
              placeholder="Örn. Veri Yapıları, Analiz II"
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="ob-instructor" className="mb-1 block text-sm font-medium">
              Hoca (isteğe bağlı)
            </label>
            <input
              id="ob-instructor"
              type="text"
              value={instructor}
              onChange={(e) => setInstructor(e.target.value)}
              placeholder="Örn. Dr. A. Yılmaz"
              className={inputClass}
            />
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="mt-4">
          <p className="text-sm font-medium">{termName.trim()}</p>
          <ul className="mt-2 list-disc space-y-1 pl-6 text-sm text-stuhub-text-secondary">
            {parsedCourses.map((name) => (
              <li key={name}>
                {name}
                {instructor.trim() ? ` — ${instructor.trim()}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-4 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      <div className="mt-6 flex items-center gap-3">
        {step === 1 && (
          <button
            type="button"
            onClick={handleStep1Next}
            className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98]"
          >
            İleri
          </button>
        )}
        {step === 2 && (
          <>
            <button
              type="button"
              onClick={() => setStep(1)}
              className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
            >
              Geri
            </button>
            <button
              type="button"
              onClick={handleStep2Next}
              className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98]"
            >
              İleri
            </button>
          </>
        )}
        {step === 3 && (
          <>
            <button
              type="button"
              onClick={() => setStep(2)}
              className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
            >
              Geri
            </button>
            <button
              type="button"
              onClick={() => void handleStart()}
              disabled={busy}
              className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98] disabled:opacity-60 disabled:active:scale-100"
            >
              {busy ? 'Kuruluyor…' : 'Başlat'}
            </button>
          </>
        )}
        <button
          type="button"
          onClick={() => void handleSkip()}
          disabled={busy}
          className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
        >
          Atla
        </button>
      </div>
    </div>
  )
}
