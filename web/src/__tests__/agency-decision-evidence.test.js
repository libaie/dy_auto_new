import { describe, expect, it } from 'vitest'
import { decisionLogText } from '../components/agency/agencyExpertLabels.js'

describe('decision log evidence preservation', () => {
  it.each([
    'shot-001: missing end frame',
    '镜头 shot-001 缺少结束帧',
    'provider_timeout: request abc_123 failed',
  ])('keeps diagnostic evidence containing identifiers: %s', evidence => {
    expect(decisionLogText(evidence, 'evidence', '暂无证据')).toBe(evidence)
  })

  it('uses the empty fallback only when there is no evidence', () => {
    expect(decisionLogText(null, 'evidence', '暂无证据')).toBe('暂无证据')
    expect(decisionLogText('  ', 'evidence', '暂无证据')).toBe('暂无证据')
  })
})
