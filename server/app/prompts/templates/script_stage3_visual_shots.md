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

只允许输出:
{
  "shots": [
    {
      "shot_number": 1,
      "scene_number": 1,
      "beat_type": "HOOK",
      "narration": "震惊！...",
      "visual_prompt": "...",
      "video_prompt": "...",
      "duration": 3.0
    }
  ]
}
