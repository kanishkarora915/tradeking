/**
 * TRADEKING VIX Engine — Constants & Zone Definitions
 */

export const ZONES = [
  {
    id: 'EXPLOSIVE',
    label: 'EXPLOSIVE',
    min: 24,
    max: 100,
    color: '#FF3B30',
    bgDim: 'rgba(255, 59, 48, 0.12)',
    action: 'Max edge — buy aggressively, ITM preferred',
    strikeBias: 'ITM strikes preferred — pay up for delta',
  },
  {
    id: 'HOT',
    label: 'HOT',
    min: 18,
    max: 24,
    color: '#FF9F0A',
    bgDim: 'rgba(255, 159, 10, 0.12)',
    action: 'Good buyer edge — ATM/ITM strikes',
    strikeBias: 'ATM strikes — best risk/reward',
  },
  {
    id: 'NEUTRAL',
    label: 'NEUTRAL',
    min: 13,
    max: 18,
    color: '#FFD60A',
    bgDim: 'rgba(255, 214, 10, 0.12)',
    action: 'Wait for momentum confirm, ATM if forced',
    strikeBias: 'ATM only, OTM avoid',
  },
  {
    id: 'DEAD',
    label: 'DEAD ZONE',
    min: 0,
    max: 13,
    color: '#8E8E93',
    bgDim: 'rgba(142, 142, 147, 0.12)',
    action: 'Avoid buying — theta kills you',
    strikeBias: 'Avoid all option buying',
  },
]

export const EMA_FAST_ALPHA = 0.4
export const EMA_SLOW_ALPHA = 0.15
export const ROC_SPIKE_THRESHOLD = 1.2  // %
export const EMA_CROSS_BUFFER = 0.15
export const MAX_TICKS = 120

export const COLORS = {
  bg: '#0C0E14',
  cardBg: '#0F1117',
  border: '#1E2130',
  text: '#F5F5F7',
  textDim: '#8E8E93',
  accent: '#0A84FF',
  green: '#30D158',
  red: '#FF3B30',
  orange: '#FF9F0A',
  yellow: '#FFD60A',
}
