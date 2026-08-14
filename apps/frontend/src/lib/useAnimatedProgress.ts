import { useEffect, useRef, useState } from 'react'

/** Hedef yüzdeye 1'er birim artarak animasyonla yaklaşır (sürekli ilerleme hissi). */
export function useAnimatedProgress(target: number, stepMs = 45): number {
  const [display, setDisplay] = useState(0)
  const displayRef = useRef(0)

  useEffect(() => {
    const id = setInterval(() => {
      const current = displayRef.current
      if (current >= target) return
      const next = Math.min(current + 1, target)
      displayRef.current = next
      setDisplay(next)
    }, stepMs)
    return () => clearInterval(id)
  }, [target, stepMs])

  return display
}
