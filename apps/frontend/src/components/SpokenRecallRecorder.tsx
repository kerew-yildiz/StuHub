import { CheckCircle, Microphone, Stop, WarningCircle, XCircle } from '@phosphor-icons/react'
import { useRef, useState } from 'react'

import { submitRecall, type RecallResult } from '../api/recall'

export interface SpokenRecallRecorderProps {
  chapterId: number
}

/** Mikrofonla "konuşarak tekrar" — kaydı mevcut notun konularıyla karşılaştırır
 * (Plan #47). Tarayıcı `MediaRecorder` API'si kullanılır, yeni paket YOK. */
export function SpokenRecallRecorder({ chapterId }: SpokenRecallRecorderProps) {
  const [recording, setRecording] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<RecallResult | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const handleStopped = async () => {
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
    if (blob.size === 0) {
      setError('Kayıt boş. Tekrar dene.')
      return
    }
    setBusy(true)
    try {
      setResult(await submitRecall(chapterId, blob))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ses kaydı değerlendirilemedi.')
    } finally {
      setBusy(false)
    }
  }

  const startRecording = async () => {
    setError('')
    setResult(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        void handleStopped()
      }
      recorder.start()
      recorderRef.current = recorder
      setRecording(true)
    } catch {
      setError('Mikrofona erişilemedi. Tarayıcı izinlerini kontrol et.')
    }
  }

  const stopRecording = () => {
    recorderRef.current?.stop()
    setRecording(false)
  }

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center gap-2 text-sm font-semibold text-stuhub-text-secondary">
        <Microphone size={18} weight="bold" />
        Konuşarak Tekrar
      </div>
      <p className="mt-1 text-sm text-stuhub-text-secondary">
        Konuyu kendi cümlelerinle anlat, notunla ne kadar örtüştüğünü gör.
      </p>

      <div className="mt-4">
        {!recording ? (
          <button
            type="button"
            onClick={() => void startRecording()}
            disabled={busy}
            className="btn-primary"
          >
            {busy ? 'Değerlendiriliyor…' : 'Kayda Başla'}
          </button>
        ) : (
          <button type="button" onClick={stopRecording} className="btn-primary flex items-center gap-2">
            <Stop size={16} weight="fill" />
            Kaydı Bitir
          </button>
        )}
      </div>

      {error && <p className="mt-3 text-sm text-stuhub-error">{error}</p>}

      {result && (
        <div className="mt-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-stuhub-text-secondary">Dökümün</h3>
            <p className="mt-1 rounded-control bg-stuhub-glass-2 p-3 text-sm">{result.transcript}</p>
          </div>
          {result.covered_topics.length > 0 && (
            <div>
              <h3 className="flex items-center gap-1 text-sm font-semibold text-stuhub-success">
                <CheckCircle size={16} /> Kapsanan Konular
              </h3>
              <ul className="mt-1 list-disc space-y-1 pl-6 text-sm">
                {result.covered_topics.map((topic) => (
                  <li key={topic}>{topic}</li>
                ))}
              </ul>
            </div>
          )}
          {result.missed_topics.length > 0 && (
            <div>
              <h3 className="flex items-center gap-1 text-sm font-semibold text-stuhub-error">
                <XCircle size={16} /> Atlanan Konular
              </h3>
              <ul className="mt-1 list-disc space-y-1 pl-6 text-sm">
                {result.missed_topics.map((topic) => (
                  <li key={topic}>{topic}</li>
                ))}
              </ul>
            </div>
          )}
          {result.covered_topics.length === 0 && result.missed_topics.length === 0 && (
            <p className="flex items-center gap-1 text-sm text-stuhub-text-secondary">
              <WarningCircle size={16} /> Bu bölüm için tanımlı konu bulunamadı.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default SpokenRecallRecorder
