import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { TermTooltip } from './TermTooltip'

const TERMS = [
  { term: 'Yığın', definition: 'LIFO çalışan doğrusal veri yapısı.' },
  { term: 'Yığın belleği', definition: 'Çağrı çerçevelerinin tutulduğu alan.' },
  { term: 'Kuyruk', definition: 'FIFO çalışan doğrusal veri yapısı.' },
]

afterEach(() => {
  cleanup()
})

describe('TermTooltip', () => {
  it('terimi işaretler ve tanımını baloncukta gösterir', () => {
    render(<TermTooltip text="Kuyruk FIFO çalışır." terms={TERMS} />)

    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toHaveTextContent('FIFO çalışan doğrusal veri yapısı.')
    expect(screen.getByText('Kuyruk').getAttribute('aria-describedby')).toBe(tooltip.id)
  })

  it('büyük/küçük harf farkını yok sayar ama kelime içi parçaları eşleştirmez', () => {
    render(<TermTooltip text="kuyruk yapısı Kuyruklar arasında" terms={TERMS} />)

    // "kuyruk" eşleşir, "Kuyruklar" (kelime sınırı yok) eşleşmez → tek baloncuk.
    expect(screen.getAllByRole('tooltip')).toHaveLength(1)
    expect(screen.getByRole('tooltip')).toHaveTextContent('FIFO')
  })

  it('uzun terimi kısa terimin üstünde tutar', () => {
    render(<TermTooltip text="Yığın belleği taşabilir." terms={TERMS} />)

    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toHaveTextContent('Çağrı çerçevelerinin tutulduğu alan.')
    expect(screen.getByText('Yığın belleği')).toBeInTheDocument()
  })

  it('terim listesi boşsa metni olduğu gibi bırakır', () => {
    render(<TermTooltip text="Kuyruk FIFO çalışır." terms={[]} />)

    expect(screen.queryByRole('tooltip')).toBeNull()
    expect(screen.getByText('Kuyruk FIFO çalışır.')).toBeInTheDocument()
  })
})
