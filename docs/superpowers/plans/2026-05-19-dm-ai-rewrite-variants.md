# DM私信AI润色 + 变体轮替 + 发送节奏 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 蓝V私信安全引流——AI润色消息1/3，变体轮替破内容指纹，7min间隔+日75条上限控节奏。

**Architecture:** DMSequence 加 `variants` JSON 列 → 服务端 AI 端点(复用现有 SSE 模式) → poll 下发 variants → 设备端变体轮替 + cooldown + 日上限。

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy / Vue 3 / AutoJS (Rhino ES5.1)

**前置条件:** A线(多分辨率Profile)全部已实现，无需新开发。

---

## 文件改动范围

| 文件 | 改动 |
|---|---|
| `server/app/db_models.py` | DMSequence 加 `variants` 列 |
| `server/app/routers/dm_sequences.py` | 加 `/generate` + `/{id}/variants` |
| `server/app/routers/device.py:496` | poll 加 `variants` 字段 |
| `server/app/services/industry_profile_service.py` | 新建 — 合规Profile加载器 |
| `server/app/data/industry_profiles/*.json` | 新建 — 6个行业合规配置 |
| `web/src/views/DMSequenceManagePage.vue` | 行业下拉 + AI按钮 + 变体预览 |
| `device/handlers/search-base.js` | `resolveMessages` 变体轮替 + KV存储 |
| `device/handlers/reply-comment.js` | cooldown + 日上限 + VIDEO_TIMEOUT调整 |

---

### Task 1: DB — DMSequence 加 variants 列

**Files:**
- Modify: `server/app/db_models.py` (DMSequence 类, ~line 325)

- [ ] **Step 1: 添加 variants 列**

在 `server/app/db_models.py` 的 `DMSequence` 类中，`messages` 列之后新增：

```python
variants = Column(JSON, nullable=True)
# 结构: [
#   [{"order":1,"content":"...","delay_ms":2000}, {"order":2,...}, {"order":3,...}],
#   [{"order":1,...}, ...],  # 变体2
#   ...
# ]
# nullable=True — 无变体时为 NULL，向后兼容
```

- [ ] **Step 2: 验证列存在**

```bash
cd server && python -c "
from app.database import SessionLocal
from app.db_models import DMSequence
db = SessionLocal()
# 检查列是否在表定义中
print('variants' in DMSequence.__table__.columns)
# 确认现有序列的 variants 是 None
seqs = db.query(DMSequence).all()
for s in seqs:
    assert s.variants is None, f'序列 {s.id} variants 非空: {s.variants}'
print(f'OK: {len(seqs)} 条序列，variants 均为 None')
db.close()
"
```

- [ ] **Step 3: Commit**

```bash
git add server/app/db_models.py
git commit -m "feat: add variants JSON column to DMSequence"
```

---

### Task 2: 行业合规Profile — 6个JSON文件 + 加载器

**Files:**
- Create: `server/app/data/industry_profiles/health.json`
- Create: `server/app/data/industry_profiles/beauty.json`
- Create: `server/app/data/industry_profiles/education.json`
- Create: `server/app/data/industry_profiles/travel.json`
- Create: `server/app/data/industry_profiles/secondhand.json`
- Create: `server/app/data/industry_profiles/general.json`
- Create: `server/app/services/industry_profile_service.py`

- [ ] **Step 1: 创建目录和6个Profile JSON文件**

`server/app/data/industry_profiles/health.json`:
```json
{
  "industry": "health",
  "label": "大健康",
  "sensitive_words": ["根治","根除","治愈","100%有效","包治","永不复发","药到病除","神效","特效药","偏方","处方","开药","诊断","治疗","问诊","用药","遵医嘱","消炎","杀菌","排毒","减肥","壮阳","补肾","改善睡眠","增强免疫力","微信号","手机号","加好友","扫码","一对一咨询","在线问诊"],
  "extreme_words": ["最","第一","唯一","顶级","全网","国家级","万能","史无前例"],
  "style_guide": "专业科普型——以健康知识分享者姿态出现，不卖货、不承诺效果、不制造焦虑",
  "system_prompt": "你是抖音蓝V大健康账号的私信话术助手。遵守：1.仅作健康知识分享，不提供个性化医疗建议 2.不使用疗效承诺词语 3.不制造紧迫感 4.不引导离开抖音平台 5.语气自然专业如真人聊天 6.不夸大不恐吓不制造健康焦虑",
  "hook_patterns": ["健康知识问答","行业数据引用","误区纠正","价值预告"],
  "cta_patterns": ["了解更多","查看详情","学习资料"]
}
```

`server/app/data/industry_profiles/beauty.json`:
```json
{
  "industry": "beauty",
  "label": "医美",
  "sensitive_words": ["术前术后","效果对比","100%","永久","无创","无痛","零风险","整形","整容","隆胸","隆鼻","抽脂","瘦脸针","玻尿酸","肉毒素","童颜","逆龄","返老还童"],
  "extreme_words": ["最","第一","唯一","顶级","永久","绝不反弹"],
  "style_guide": "美学观点型——以审美分享者姿态出现，不承诺手术效果、不展示前后对比",
  "system_prompt": "你是抖音蓝V医美账号的私信话术助手。遵守：1.仅分享审美观点和保养知识 2.不承诺手术/治疗效果 3.不展示术前术后对比 4.不使用绝对化效果描述 5.语气专业亲和 6.不制造容貌焦虑",
  "hook_patterns": ["审美趋势","保养知识","误区纠正","行业科普"],
  "cta_patterns": ["了解更多","查看案例","了解详情"]
}
```

`server/app/data/industry_profiles/education.json`:
```json
{
  "industry": "education",
  "label": "教育",
  "sensitive_words": ["包过","保录取","包上岸","100%通过","考试答案","真题泄露","内部指标","走后门","买证","代考","替考","免考","包毕业","包就业","官方认证","教育部认证"],
  "extreme_words": ["最","第一","唯一","保过","100%","绝对"],
  "style_guide": "学习干货型——以知识分享者姿态出现，不承诺考试结果",
  "system_prompt": "你是抖音蓝V教育账号的私信话术助手。遵守：1.仅分享学习方法和干货 2.不承诺考试通过率或录取结果 3.不使用包过/保录取等违规词 4.不贩卖焦虑(如'再不学就晚了') 5.语气鼓励积极向上 6.多做价值输出少做营销",
  "hook_patterns": ["知识痛点","学习方法","考试技巧","行业前景"],
  "cta_patterns": ["了解更多","试听课程","领取资料"]
}
```

`server/app/data/industry_profiles/travel.json`:
```json
{
  "industry": "travel",
  "label": "旅游",
  "sensitive_words": ["强制消费","零负团费","购物团","黑导游","无证经营","非法一日游","低价陷阱","虚假宣传","天价","宰客"],
  "extreme_words": ["最","第一","唯一","全网最低","绝美","必去"],
  "style_guide": "旅行灵感型——以旅行分享者姿态出现，不夸大不误导",
  "system_prompt": "你是抖音蓝V旅游账号的私信话术助手。遵守：1.分享旅行灵感和目的地信息 2.不做虚假宣传或夸大描述 3.不承诺具体价格(价格随时变动) 4.不贬低其他目的地 5.语气轻松愉悦 6.强调体验价值而非价格",
  "hook_patterns": ["小众目的地","旅行攻略","季节推荐","体验分享"],
  "cta_patterns": ["查看行程","了解更多","获取攻略"]
}
```

`server/app/data/industry_profiles/secondhand.json`:
```json
{
  "industry": "secondhand",
  "label": "二手买卖",
  "sensitive_words": ["假一赔十","绝对正品","正品保证","专柜验货","原单","尾单","工厂货","水货","A货","高仿","1:1","走私","海关罚没"],
  "extreme_words": ["最","第一","唯一","全网最低","秒杀价","亏本"],
  "style_guide": "好物分享型——以闲置分享者姿态出现，不过度承诺商品品质",
  "system_prompt": "你是抖音蓝V闲置物品账号的私信话术助手。遵守：1.如实描述物品状况 2.不做假一赔十等过度承诺 3.不引流到站外交易 4.不售卖违禁品 5.语气真诚自然 6.强调物品使用价值",
  "hook_patterns": ["使用场景","物品故事","性价比","实用推荐"],
  "cta_patterns": ["查看详情","了解更多","看看实物"]
}
```

`server/app/data/industry_profiles/general.json`:
```json
{
  "industry": "general",
  "label": "通用",
  "sensitive_words": ["微信号","手机号","加好友","扫码","加群","QQ","最","第一","唯一","全网最低","秒杀","免费领取","点击有惊喜"],
  "extreme_words": ["最","第一","唯一","顶级","全网","国家级"],
  "style_guide": "自然聊天型——真实用户语气，不营销化",
  "system_prompt": "你是抖音蓝V账号的私信话术助手。遵守：1.语气自然如真人聊天 2.不引导离开抖音平台 3.不使用极限词和夸大宣传 4.不发送骚扰内容 5.内容有价值不纯营销",
  "hook_patterns": ["价值分享","问题帮助","行业资讯"],
  "cta_patterns": ["了解更多","查看详情","关注账号"]
}
```

- [ ] **Step 2: 创建合规Profile加载器**

`server/app/services/industry_profile_service.py`:
```python
"""行业合规Profile加载器 — 从 JSON 文件加载，LRU 缓存"""
import json
import os
from functools import lru_cache

PROFILES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "industry_profiles"
)


@lru_cache(maxsize=8)
def load_profile(industry: str) -> dict:
    """加载行业合规Profile，文件不存在时回退到 general.json"""
    path = os.path.join(PROFILES_DIR, f"{industry}.json")
    if not os.path.exists(path):
        path = os.path.join(PROFILES_DIR, "general.json")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_industries() -> list[dict]:
    """返回可用行业列表供前端下拉使用"""
    result = []
    try:
        for fname in sorted(os.listdir(PROFILES_DIR)):
            if fname.endswith(".json"):
                with open(os.path.join(PROFILES_DIR, fname), "r", encoding="utf-8") as f:
                    profile = json.load(f)
                    result.append({"key": profile["industry"], "label": profile["label"]})
    except FileNotFoundError:
        pass
    return result
```

- [ ] **Step 3: 验证加载器**

```bash
cd server && python -c "
from app.services.industry_profile_service import load_profile, list_industries

# 加载大健康Profile
p = load_profile('health')
assert p['industry'] == 'health'
assert p['label'] == '大健康'
assert len(p['sensitive_words']) > 10
print('health OK:', p['label'], '| 敏感词:', len(p['sensitive_words']))

# 回退到通用
p2 = load_profile('nonexistent')
assert p2['industry'] == 'general'
print('fallback OK:', p2['label'])

# 列出所有行业
industries = list_industries()
assert len(industries) == 6
for ind in industries:
    print(' -', ind['key'], ':', ind['label'])
print('All OK: 6 industries loaded')
"
```

- [ ] **Step 4: Commit**

```bash
git add server/app/data/industry_profiles/ server/app/services/industry_profile_service.py
git commit -m "feat: add 6 industry compliance profiles + loader"
```

---

### Task 3: 服务端 — AI 生成序列端点

**Files:**
- Modify: `server/app/routers/dm_sequences.py` (新加 2 个端点)

- [ ] **Step 1: 添加 `POST /api/dm-sequences/generate` 端点**

在 `server/app/routers/dm_sequences.py` 中添加：

```python
import json
import asyncio
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


class DMSequenceGenerateRequest(BaseModel):
    industry: str = Field(default="general", description="行业key: health/beauty/education/travel/secondhand/general")
    description: str = Field(..., min_length=5, max_length=500, description="大白话描述，如'推饮食指南软文，语气亲和可信'")
    link_url: str = Field(..., min_length=5, max_length=500, description="消息2的短链URL")


@router.post("/generate")
async def generate_dm_sequence(
    body: DMSequenceGenerateRequest,
    current_user: dict = Depends(require_role("admin")),
):
    """AI生成3条合规消息序列(SSE流式) — 复用现有提示词模板的生成模式"""
    from app.services.industry_profile_service import load_profile

    profile = load_profile(body.industry)

    system_prompt = profile["system_prompt"]
    sensitive_words_str = "、".join(profile["sensitive_words"])
    extreme_words_str = "、".join(profile["extreme_words"])
    style_guide = profile["style_guide"]

    async def generate():
        from app.services.ai_service import get_ai_service
        ai = get_ai_service()

        prompt = f"""你是一个专业的私信话术生成助手。

## 行业约束
- 行业: {profile['label']}
- 话术风格: {style_guide}
- 绝对禁用词(包含任一词即不合格): {sensitive_words_str}
- 极限词禁用: {extreme_words_str}

## 平台规则
{system_prompt}

## 任务
根据用户描述生成3条私信消息序列:
- 消息1: 建立信任的钩子，吸引用户注意，让用户愿意继续看
- 消息2: 用户提供的链接地址(原样保留，不修改)
- 消息3: 驱动点击的收口CTA，引导用户点击消息2的链接

要求:
1. 每条消息50-150字，语气自然像真人聊天
2. 消息1和消息3需要针对私信场景设计，不能像广告文案
3. 不出现任何禁用词或极限词
4. 返回纯JSON数组: [{{"order":1,"content":"...","delay_ms":2000}},{{"order":2,"content":"{body.link_url}","delay_ms":1500}},{{"order":3,"content":"...","delay_ms":2000}}]
5. delay_ms: 消息1用2000, 消息2用1500, 消息3用2000

用户描述: {body.description}"""

        yield json.dumps({"type": "start", "industry": body.industry, "label": profile["label"]}) + "\n"

        full = ""
        try:
            async for chunk in ai.stream_chat(prompt, system=system_prompt):
                full += chunk
                yield json.dumps({"type": "chunk", "content": chunk}) + "\n"
                await asyncio.sleep(0.01)
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"
            return

        # 提取JSON
        try:
            import re
            match = re.search(r"\[[\s\S]*\]", full)
            if match:
                messages = json.loads(match.group())
                # 合规后处理
                for msg in messages:
                    content = msg.get("content", "")
                    for word in profile["sensitive_words"]:
                        if word in content:
                            yield json.dumps({"type": "error", "message": f"生成内容含敏感词: {word}"}) + "\n"
                            return
                yield json.dumps({"type": "done", "messages": messages}) + "\n"
            else:
                yield json.dumps({"type": "error", "message": "AI返回格式异常，请重试"}) + "\n"
        except json.JSONDecodeError:
            yield json.dumps({"type": "error", "message": "JSON解析失败，请重试"}) + "\n"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
```

- [ ] **Step 2: 验证 generate 端点**

```bash
# 语法检查
cd server && python -c "
from app.routers.dm_sequences import router
print('router OK')
"
```

- [ ] **Step 3: 添加 `POST /api/dm-sequences/{id}/variants` 端点**

在同一个文件中：

```python
class VariantsGenerateRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=5, description="生成变体套数")


@router.post("/{seq_id}/variants")
async def generate_variants(
    seq_id: str,
    body: VariantsGenerateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    """基于已有messages生成N套变体 — 消息1和消息3做同义改写，消息2(短链)保持不变"""
    from app.services.industry_profile_service import load_profile

    seq = db.query(DMSequence).filter(DMSequence.id == seq_id).first()
    if not seq:
        raise HTTPException(404, "DM序列不存在")

    if not seq.messages or len(seq.messages) < 3:
        raise HTTPException(400, "DM序列至少需要3条消息才能生成变体")

    industry = getattr(seq, "industry", "general") or "general"
    profile = load_profile(industry)

    original_msg1 = seq.messages[0].get("content", "") if isinstance(seq.messages[0], dict) else ""
    original_msg2 = seq.messages[1]  # 短链，保持不变
    original_msg3 = seq.messages[2].get("content", "") if len(seq.messages) > 2 and isinstance(seq.messages[2], dict) else ""

    variants = []
    from app.services.ai_service import get_ai_service
    ai = get_ai_service()

    for vi in range(body.count):
        prompt = f"""请对以下私信话术做同义改写，保持核心意思不变，换用不同的表达方式。

## 约束
- 禁用词: {'、'.join(profile['sensitive_words'][:20])}
- {profile['style_guide']}
- 每条50-150字
- 不要改变原意和核心信息
- 语气自然像真人

原始消息1(钩子): {original_msg1}
原始消息3(收口): {original_msg3}

返回JSON: {{"msg1": "改写后的消息1", "msg3": "改写后的消息3"}}"""

        try:
            response = await ai.chat(prompt)
            result = json.loads(response)
            rewritten_msg1 = result.get("msg1", original_msg1)
            rewritten_msg3 = result.get("msg3", original_msg3)

            # 合规扫描
            ok = True
            for word in profile["sensitive_words"]:
                if word in rewritten_msg1 or word in rewritten_msg3:
                    ok = False
                    break
            if not ok:
                continue  # 跳过不合规变体

            variant = [
                {"order": 1, "content": rewritten_msg1, "delay_ms": seq.messages[0].get("delay_ms", 2000)},
                original_msg2,  # 消息2保持不变
                {"order": 3, "content": rewritten_msg3, "delay_ms": seq.messages[2].get("delay_ms", 2000) if len(seq.messages) > 2 else 2000},
            ]
            variants.append(variant)
        except Exception:
            continue

    if not variants:
        raise HTTPException(500, "无法生成合规变体，请调整原始话术后重试")

    seq.variants = variants
    db.commit()

    return {"ok": True, "variants_count": len(variants), "variants": variants}
```

- [ ] **Step 4: 验证完整端点**

```bash
cd server && python -c "
from app.routers.dm_sequences import router
# 确认新端点已注册
routes = [r.path for r in router.routes]
assert '/generate' in routes or '/api/dm-sequences/generate' in routes, f'generate endpoint missing: {routes}'
print('generate endpoint registered')
print('All endpoints:', routes)
"
```

- [ ] **Step 5: Commit**

```bash
git add server/app/routers/dm_sequences.py
git commit -m "feat: add DM sequence AI generate + variants endpoints"
```

---

### Task 4: 服务端 — poll response 下发 variants

**Files:**
- Modify: `server/app/routers/device.py:496`

- [ ] **Step 1: 修改 poll 列表推导式**

在 `server/app/routers/device.py` 第496行，将：
```python
dm_sequences_list = [{"id": s.id, "messages": s.messages} for s in dm_seqs] if dm_seqs else None
```
改为：
```python
dm_sequences_list = [
    {
        "id": s.id,
        "messages": s.messages,
        "variants": s.variants,
    }
    for s in dm_seqs
] if dm_seqs else None
```

- [ ] **Step 2: 验证**

```bash
cd server && python -c "
from app.main import app
print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add server/app/routers/device.py
git commit -m "feat: include variants in poll dm_sequences response"
```

---

### Task 5: 前端 — 行业下拉 + AI生成按钮 + 变体预览

**Files:**
- Modify: `web/src/views/DMSequenceManagePage.vue`

- [ ] **Step 1: 行业下拉选择器**

找到当前自由文本输入 (`<input>` with placeholder "如：健康")，替换为 `<select>`:

```html
<!-- 替换现有的行业输入框 -->
<div class="mb-4">
  <label class="block text-sm font-medium text-gray-300 mb-1">行业</label>
  <select
    v-model="form.industry"
    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:border-blue-500 focus:outline-none"
  >
    <option value="health">大健康</option>
    <option value="beauty">医美</option>
    <option value="education">教育</option>
    <option value="travel">旅游</option>
    <option value="secondhand">二手买卖</option>
    <option value="general">通用</option>
  </select>
</div>
```

- [ ] **Step 2: AI生成序列区域（创建模式）**

在消息列表编辑区上方添加：

```html
<!-- 仅创建模式显示 -->
<div v-if="!editingId" class="mb-4 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
  <h4 class="text-sm font-medium text-gray-300 mb-2">AI 智能生成序列</h4>
  <div class="mb-2">
    <input
      v-model="aiDescription"
      type="text"
      placeholder="大白话描述，如：推饮食指南软文，语气亲和可信"
      class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:border-blue-500 focus:outline-none"
    />
  </div>
  <div class="mb-3">
    <input
      v-model="aiLinkUrl"
      type="text"
      placeholder="短链URL（作为消息2）"
      class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:border-blue-500 focus:outline-none"
    />
  </div>
  <button
    @click="generateSequence"
    :disabled="!aiDescription || !aiLinkUrl || generating"
    class="px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:from-blue-500 hover:to-purple-500 transition-colors"
  >
    <span v-if="generating">AI 正在生成...</span>
    <span v-else>AI 生成序列</span>
  </button>
  <div v-if="generating" class="mt-2 text-xs text-gray-400">{{ generateStatus }}</div>
</div>
```

- [ ] **Step 3: AI生成逻辑（SSE流式）**

在 `<script setup>` 中添加：

```javascript
import { ref } from 'vue'
import { useSavedPrompt } from '@/composables/useSavedPrompt'

const aiDescription = ref('')
const aiLinkUrl = ref('')
const generating = ref(false)
const generateStatus = ref('')

async function generateSequence() {
  if (!aiDescription.value || !aiLinkUrl.value) return
  generating.value = true
  generateStatus.value = '正在连接...'

  try {
    const response = await fetch('/api/dm-sequences/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getToken()}` },
      body: JSON.stringify({
        industry: form.industry || 'general',
        description: aiDescription.value,
        link_url: aiLinkUrl.value,
      }),
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const data = JSON.parse(line)
          if (data.type === 'start') {
            generateStatus.value = `AI 正在生成 ${data.label} 行业序列...`
          } else if (data.type === 'chunk') {
            generateStatus.value += data.content
          } else if (data.type === 'done') {
            form.messages = data.messages
            generateStatus.value = '生成完成！请检查并调整消息内容'
            generating.value = false
            return
          } else if (data.type === 'error') {
            generateStatus.value = '错误: ' + data.message
            generating.value = false
            return
          }
        } catch (e) {}
      }
    }
  } catch (e) {
    generateStatus.value = '连接失败: ' + e.message
  }
  generating.value = false
}
```

- [ ] **Step 4: 变体生成按钮 + 预览弹窗**

```html
<!-- 编辑模式，有 messages 时显示 -->
<button
  v-if="editingId && form.messages && form.messages.length >= 3"
  @click="generateVariants"
  :disabled="generatingVariants"
  class="px-4 py-2 bg-gradient-to-r from-green-600 to-teal-600 text-white rounded-lg text-sm font-medium disabled:opacity-50"
>
  <span v-if="generatingVariants">正在生成变体...</span>
  <span v-else>生成 {{ variantCount }} 套变体</span>
</button>
```

```javascript
const generatingVariants = ref(false)
const variantCount = ref(3)
const variantPreview = ref(null)  // 预览数据

async function generateVariants() {
  generatingVariants.value = true
  try {
    const res = await fetch(`/api/dm-sequences/${editingId.value}/variants`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getToken()}` },
      body: JSON.stringify({ count: variantCount.value }),
    })
    const data = await res.json()
    if (data.ok) {
      variantPreview.value = data.variants
      // 弹窗展示变体预览，用户勾选确认后 PUT 更新
    }
  } catch (e) {
    console.error('变体生成失败:', e)
  }
  generatingVariants.value = false
}
```

- [ ] **Step 5: Commit**

```bash
git add web/src/views/DMSequenceManagePage.vue
git commit -m "feat: add industry selector, AI generate, and variant preview to DMSequence page"
```

---

### Task 6: 设备端 — 变体轮替

**Files:**
- Modify: `device/handlers/search-base.js` (~line 505 `resolveMessages`)

- [ ] **Step 1: 添加 KV 存储辅助方法**

在 `resolveMessages` 之前添加：

```javascript
// ==== KV 持久化（设备重启恢复状态）====

/**
 * 获取缓存目录 — 兼容 Android 10+ scoped storage
 * 复用 api-client.js 的路径策略: 优先 getExternalFilesDir, 回退 /sdcard/
 */
SearchBaseHandler._getCacheDir = function () {
  try {
    var extDir = context.getExternalFilesDir(null);
    if (extDir) {
      var cacheDir = extDir.getAbsolutePath() + "/dy_auto_cache";
      files.ensureDir(cacheDir);
      return cacheDir;
    }
  } catch (e) {}
  var fallback = "/sdcard/dy_auto/cache";
  try { files.ensureDir(fallback); } catch (e2) {}
  return fallback;
};

SearchBaseHandler._storageGet = function (key, defaultVal) {
  try {
    var path = this._getCacheDir() + "/" + key + ".txt";
    if (files.exists(path)) {
      return parseInt(files.read(path).trim()) || defaultVal;
    }
  } catch (e) {}
  return defaultVal;
};

SearchBaseHandler._storageSet = function (key, val) {
  try {
    var path = this._getCacheDir() + "/" + key + ".txt";
    files.write(path, String(val));
  } catch (e) {}
};
```

- [ ] **Step 2: 改造 resolveMessages 加变体轮替**

将现有的 `resolveMessages` 函数中 `dm_sequence_id` 缓存命中部分改为：

```javascript
SearchBaseHandler.resolveMessages = function (params) {
  // 1. dm_messages 直接透传 (最高优先级)
  if (params.dm_messages && params.dm_messages.length > 0) {
    return params.dm_messages;
  }

  // 2. dm_sequence_id → 查缓存 → 变体轮替
  if (params.dm_sequence_id) {
    var cached = this._dmSeqCache && this._dmSeqCache[params.dm_sequence_id];
    if (cached) {
      // 有变体 → 轮替
      if (cached.variants && cached.variants.length > 0) {
        var storageKey = "dm_variant_idx_" + params.dm_sequence_id;
        var idx = this._storageGet(storageKey, 0);
        var picked = cached.variants[idx % cached.variants.length];
        this._storageSet(storageKey, (idx + 1) % cached.variants.length);
        return picked;
      }
      // 无变体 → 原逻辑
      return cached.messages;
    }
    logger.warn(TAG, "DM序列模板未命中: " + params.dm_sequence_id);
    return [];
  }

  // 3. content → 单条消息
  if (params.content) {
    return [{order: 1, content: params.content, delay_ms: 0}];
  }

  // 4-5. AI 生成 (现有逻辑不变)
  var count = params.count || 1;
  var videoText = "";
  try { videoText = this._extractVideoText ? this._extractVideoText() : ""; } catch (e) {}
  if (count > 1 && videoText) {
    var seq = aiAnalyzer.generateVideoDMSequence(videoText, count);
    if (seq && seq.length > 0) return seq;
  }
  var single = videoText ? aiAnalyzer.generateVideoDM(videoText) : "";
  return single ? [{order: 1, content: single, delay_ms: 0}] : [];
};
```

- [ ] **Step 3: 验证语法**

```bash
cd device && node -e "
// 模拟 AutoJS 环境
global.context = { getExternalFilesDir: function() { return null; } };
global.files = {
  ensureDir: function() {},
  exists: function() { return false; },
  read: function() { return '0'; },
  write: function() {},
  listDir: function() { return []; }
};

var SearchBaseHandler = require('./handlers/search-base');
console.log('resolveMessages:', typeof SearchBaseHandler.resolveMessages);
console.log('_storageGet:', typeof SearchBaseHandler._storageGet);
console.log('_storageSet:', typeof SearchBaseHandler._storageSet);
console.log('OK');
"
```

- [ ] **Step 4: Commit**

```bash
git add device/handlers/search-base.js
git commit -m "feat: add variant rotation + KV persistence to resolveMessages"
```

---

### Task 7: 设备端 — cooldown + 日上限

**Files:**
- Modify: `device/handlers/reply-comment.js` (~lines 54-57, 263-347)

- [ ] **Step 1: 调整 VIDEO_TIMEOUT 兼容 DM cooldown**

在 `_processComments` 函数开头（line 57 `VIDEO_TIMEOUT` 之后）添加：

```javascript
// 当有 DM 序列时，扩展视频超时以容纳 cooldown
var hasDMSequence = !!(params.dm_sequence_id || (params.dm_messages && params.dm_messages.length > 0));
var dmCooldownMs = params.inter_user_cooldown_ms || 7 * 60 * 1000;
if (hasDMSequence && dmCooldownMs > 0) {
  var maxDMsThisTask = params.max_dms || 10;
  VIDEO_TIMEOUT = Math.max(VIDEO_TIMEOUT, maxDMsThisTask * dmCooldownMs + 60000);
}
```

- [ ] **Step 2: 替换 line 266 的 hasDMSequence 定义**

删除 line 266 的局部 `var hasDMSequence` 声明（因为已在函数顶部定义）。

- [ ] **Step 3: 在 DM 发送成功后记录时间（两个路径）**

Line 297 之后（`_sendMessageSequence` 成功），以及在 fallback 路径 line 341 之后：

```javascript
// 在正常路径 line 297 附近:
if (sent && hasDMSequence) {
  this._lastDMSendTime = Date.now();
}

// 在 fallback 路径 line 342 附近:
if (sent2 && hasDMSequence) {
  this._lastDMSendTime = Date.now();
}
```

- [ ] **Step 4: 添加日DM计数器函数**

在 `_processComments` 函数内，`_reportProgress` 之后：

```javascript
// 日DM计数器
function _getServerDate() {
  // 优先用服务端日期（main.js catchUpPoll 设置）
  if (self._serverDate) return self._serverDate;
  var d = new Date();
  return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate();
}

function _getDailyDMCount() {
  var dateKey = _getServerDate();
  return SearchBaseHandler._storageGet("dm_daily_" + dateKey, 0);
}

function _incrementDailyDMCount() {
  var dateKey = _getServerDate();
  var current = SearchBaseHandler._storageGet("dm_daily_" + dateKey, 0);
  SearchBaseHandler._storageSet("dm_daily_" + dateKey, current + 1);

  // 清理3天前过期计数器
  try {
    var cacheDir = SearchBaseHandler._getCacheDir();
    var flist = files.listDir(cacheDir);
    var cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 3);
    var cutoffKey = "dm_daily_" + cutoff.getFullYear() + "-" + (cutoff.getMonth() + 1) + "-" + cutoff.getDate();
    for (var fi = 0; fi < flist.length; fi++) {
      if (flist[fi].indexOf("dm_daily_") === 0 && flist[fi] < cutoffKey) {
        try { files.remove(cacheDir + "/" + flist[fi]); } catch (e) {}
      }
    }
  } catch (e) {}

  return current + 1;
}
```

- [ ] **Step 5: 协调 maxDMs 与日上限**

在 line 229 `canDM` 之前：

```javascript
// 协调 per-task maxDMs 与日上限
var maxDaily = params.max_daily_dm || 75;
var todayRemaining = maxDaily - _getDailyDMCount();
var effectiveMaxDMs = Math.min(maxDMs, Math.max(0, todayRemaining));
if (effectiveMaxDMs <= 0) {
  logger.warn(TAG, "当日DM已达上限(" + maxDaily + ")，跳过私信");
  canDM = false;  // 不break，继续回复评论
}
// 之后 line 229 的 canDM 检查仍然生效:
// canDM = shouldDM && stats.dm_count < maxDMs;  ← maxDMs 保持不变
```

- [ ] **Step 6: DM发送成功后递增日计数器（两个路径）**

在正常路径 line 313 `stats.dm_count++` 之后，fallback 路径 line 358 `stats.dm_count++` 之后：

```javascript
if (hasDMSequence) {
  var dailyCount = _incrementDailyDMCount();
  logger.info(TAG, "当日DM: " + dailyCount + "/" + (params.max_daily_dm || 75));
}
```

- [ ] **Step 7: 语法检查**

```bash
cd device && node -e "require('./handlers/reply-comment'); console.log('OK')"
```

- [ ] **Step 8: Commit**

```bash
git add device/handlers/reply-comment.js
git commit -m "feat: add DM cooldown + daily limit + video timeout adjustment"
```

---

### Task 8: 服务端 — main.js 传递 server_date

**Files:**
- Modify: `device/main.js` (catchUpPoll 函数)

- [ ] **Step 1: poll response 中提取 server_date 并保存**

在 `catchUpPoll` 函数（~line 422）中，`response` 解构后添加：

```javascript
if (response.server_date) {
  SearchBaseHandler._serverDate = response.server_date;  // "2026-05-19"
}
```

服务端 `device.py` poll 返回中添加 `server_date` 字段：
```python
# device.py PollResponse 添加:
server_date: Optional[str] = None

# poll 端点构建响应时:
server_date=bj_now().strftime("%Y-%m-%d"),
```

- [ ] **Step 2: Commit**

```bash
git add device/main.js server/app/routers/device.py server/app/models.py
git commit -m "feat: add server_date to poll response for daily DM counter"
```

---

## 验证

```bash
# 后端全量语法检查
cd server && python -c "from app.main import app; print('OK')"

# variants 字段存在
cd server && python -c "
from app.db_models import DMSequence
print('variants' in DMSequence.__table__.columns)
"

# 行业Profile可加载
cd server && python -c "
from app.services.industry_profile_service import load_profile, list_industries
print('health:', load_profile('health')['label'])
print('industries:', [i['key'] for i in list_industries()])
"

# 设备端语法检查
cd device && node -e "require('./core/config'); require('./handlers/search-base'); require('./handlers/reply-comment'); console.log('All OK')"
```
