/** Konu ilerleme çemberi (sıkıntı: konular listesinde her konunun yanında yuvarlak
 * progress çemberi isteği). StreakRing'teki SVG halkanın kompakt, tek boyutlu hâli.
 * percent null → veri yok (boş halka, %0 dolu). */
export function TopicProgressRing({ percent, size = 22 }: { percent: number | null; size?: number }) {
  const radius = (size - 4) / 2
  const center = size / 2
  const circumference = 2 * Math.PI * radius
  const clamped = Math.min(Math.max(percent ?? 0, 0), 100)
  const offset = circumference - (clamped / 100) * circumference

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={percent == null ? 'İlerleme verisi yok' : `Konu ilerlemesi %${Math.round(clamped)}`}
      className="shrink-0"
    >
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke="var(--stuhub-border)"
        strokeWidth="2.5"
      />
      {percent != null && (
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--stuhub-accent)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${center} ${center})`}
          className="transition-[stroke-dashoffset] duration-300 ease-out"
        />
      )}
    </svg>
  )
}
