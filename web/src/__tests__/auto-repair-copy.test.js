import { describe, expect, it } from 'vitest'
import { autoRepairStatusLabel, autoRepairTypeLabel, safeAutoRepairText } from '../constants/autoRepairCopy.js'

describe('auto repair copy', () => {
  it('uses readable Chinese fallback for mojibake user-facing text', () => {
    expect(safeAutoRepairText('瀹歌尪顔囪ぐ鏇烆吀閺屻儱褰傞悳', '专家发现待补充')).toBe('专家发现待补充')
    expect(autoRepairStatusLabel('blocked')).toBe('需要人工处理')
    expect(autoRepairTypeLabel('storyboard_missing_references')).toBe('分镜参考信息缺失')
  })
})
