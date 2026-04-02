/**
 * TRADEKING — Trap Alert Banner
 * Full-width pulsing banner when Engine 08 fires.
 */
import React from 'react'

export default function TrapAlertBanner({ signals }) {
  // Check if any index has an active trap
  const traps = []
  for (const [index, data] of Object.entries(signals || {})) {
    const trap = data?.trap
    if (trap?.active) {
      traps.push({ index, ...trap })
    }
  }

  if (traps.length === 0) return null

  return (
    <div style={{ flexShrink: 0 }}>
      {traps.map((trap) => {
        const isBull = trap.type === 'BULL_TRAP'
        return (
          <div
            key={trap.index}
            className={`trap-banner ${isBull ? 'trap-banner--bull' : 'trap-banner--bear'}`}
          >
            {isBull ? (
              <>&#9888; BULL TRAP DETECTED on {trap.index} at {trap.level?.toLocaleString()} — REVERSAL SIGNAL: PUT</>
            ) : (
              <>&#9889; BEAR TRAP DETECTED on {trap.index} at {trap.level?.toLocaleString()} — REVERSAL SIGNAL: CALL</>
            )}
            {trap.confidence && (
              <span style={{ marginLeft: 16, opacity: 0.7 }}>
                [{trap.confidence}]
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
