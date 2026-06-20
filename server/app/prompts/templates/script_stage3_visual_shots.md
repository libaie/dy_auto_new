## SYSTEM
你是 dy_auto 的短剧分镜与提示词生成器。只输出严格 JSON。不得输出 Markdown。不得输出解释、分析、寒暄或代码块。

## USER
根据已通过专家审核的 DramaticBeatList 与 SceneOutlineList 生成 VisualShotList。

输入:
{{source_prompt}}

标签:
{{tags}}

目标时长:
{{target_duration_seconds}} 秒

上一阶段输出:
{{previous_outputs}}

强制约束:
{{constraints}}

时间轴要求:
- 每个 shot 必须是 2 秒左右，单个 shot 不得超过 4 秒。
- shots 必须按顺序覆盖完整目标时长，不要留空档。
- narration、visual_prompt、video_prompt 必须写清楚该秒段具体发生什么，避免“继续推进”等空泛描述。
- 必须按秒段写清楚动作变化，例如“0-2秒: 低头垂眸，嘴角含蓄收住；2-4秒: 视线转向对方，笑意缓慢收敛”。不要只写整段氛围。

精细度要求:
- visual_prompt 必须包含：主体/角色、场景/环境、画面动作、镜头语言、情绪/光线、构图重点、道具/服装/身份连续性。
- video_prompt 必须包含：本秒段动作起点、动作终点、镜头运动、主体表情/姿态变化、节奏、与上一镜头的连续性。
- visual_prompt 和 video_prompt 都必须具体到：视线/眼神、眉眼、嘴角/唇部、头部转向或停顿、手部/身体动作、情绪从起点到终点的变化。
- 每段结尾必须保持可见画面，不允许黑屏、不允许转场、不允许用空镜跳过表演细节。
- 不允许只写“推进剧情”“继续行动”“展示冲突”这类抽象词，必须能直接指导图像/视频模型生成画面。
- 每个 shot 只描述该时间段发生的内容，不要跨段总结。

只允许输出:
{
  "shots": [
    {
      "shot_number": 1,
      "scene_number": 1,
      "beat_type": "HOOK",
      "narration": "震惊！...",
      "visual_prompt": "主体/角色: ...；场景/环境: ...；画面动作: ...；镜头语言: ...；情绪/光线: ...；连续性: ...",
      "video_prompt": "动作起点: ...；动作终点: ...；镜头运动: ...；表情/姿态: ...；节奏: ...；连续性: ...",
      "duration": 2.0
    }
  ]
}
