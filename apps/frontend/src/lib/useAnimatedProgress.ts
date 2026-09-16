import { useEffect, useRef, useState } from 'react'

/**
 * Hedef yüzdeye 1'er birim artarak animasyonla yaklaşır (sürekli ilerleme hissi).
 *
 * Performans notu: interval yalnızca hedefe ulaşılmamışken çalışır — hedefe
 * gelince interval temizlenir (önceden %100 sonrası da boşuna tick ediyordu;
 * sayfa başına 3-4 aktif örnek boşuna render üretiyordu). Hedef yukarı çekilirse
 * effect yeniden kurulup devam eder.
 */
export function useAnimatedProgress(target: number, stepMs = 45): number {
  const [display, setDisplay] = useState(0)
  const displayRef = useRef(0)

  useEffect(() => {
    if (displayRef.current >= target) return
    const id = setInterval(() => {
      const current = displayRef.current
      if (current >= target) {
        clearInterval(id)
        return
      }
      const next = Math.min(current + 1, target)
      displayRef.current = next
      setDisplay(next)
    }, stepMs)
    return () => clearInterval(id)
  }, [target, stepMs])

  return display
}
