import { describe, expect, it } from 'vitest'
import {
  CURRENT_EXPERT_IDS,
  expertAvatar,
  expertName,
  phaseLabel,
  phaseText,
  skillText,
} from '../components/agency/agencyExpertLabels.js'

describe('agencyExpertLabels', () => {
  it('labels the story generator expert and story planning stage', () => {
    expect(CURRENT_EXPERT_IDS.has('story_generator')).toBe(true)
    expect(expertName('story_generator')).toBe('故事生成专家')
    expect(expertAvatar('story_generator')).toBe('故')
    expect(phaseLabel('story_planning')).toBe('故事规划')
    expect(phaseText(['story_planning'])).toBe('故事规划')
    expect(skillText({ expert_id: 'story_generator' })).toContain('整季故事')
  })
})
