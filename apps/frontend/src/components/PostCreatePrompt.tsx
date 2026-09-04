import { X } from '@phosphor-icons/react'
import { useEffect } from 'react'

interface PostCreatePromptProps {
  title: string
  description: string
  onClose: () => void
  children: React.ReactNode
}

/** "Az önce oluşturuldu, şimdi materyal ekle" pop-up'ı — yeni ders/chapter oluşturulunca
 * kullanıcıyı bir sonraki mantıksal adıma (kitap/sunum yükleme) yönlendirir. Uygulama son
 * kullanıcı için "ne yapacağım şimdi" belirsizliğini azaltmak için; her zaman atlanabilir. */
export function PostCreatePrompt({ title, description, onClose, children }: PostCreatePromptProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="post-create-prompt-title"
        className="glass-panel w-full max-w-lg p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="post-create-prompt-title" className="text-lg font-semibold">
              {title}
            </h2>
            <p className="mt-1 text-sm text-stuhub-text-secondary">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-control p-1.5 text-stuhub-text-secondary transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-glass-1-hover hover:text-stuhub-text active:scale-[0.98]"
            aria-label="Kapat"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <div className="mt-4">{children}</div>
        <button
          type="button"
          onClick={onClose}
          className="mt-4 text-sm font-medium text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:text-stuhub-text"
        >
          Şimdi değil, sonra eklerim
        </button>
      </div>
    </div>
  )
}
