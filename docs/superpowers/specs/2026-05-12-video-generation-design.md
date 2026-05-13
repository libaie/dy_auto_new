# 关键词矩阵 → AI 短视频自动生成

> Phase 1+2：Pixelle-Video 部署 + 服务端视频生成服务。Phase 3+4 另开 spec。

## 背景

现有 dy_auto 具备关键词矩阵 → 搜索视频 → AI 分析评论 → 互动获客的能力。下一步：根据关键词 AI 生成原创短视频，为后续"发布→引流→互动"全闭环铺路。

## 约束

- GPU：单卡 RTX 3060 12GB，ComfyUI 一次只能串行处理一个视频（3-5min/条）
- Pixelle-Video 是独立 Python 服务，不能直接 import 为库
- 本 spec 只覆盖 Phase 1+2，Phase 3（设备发布）另开

---

## Phase 1：Pixelle-Video 部署

### 1.1 环境

```
GPU 机器（3060 12GB）：
  - Python 3.11+
  - ComfyUI（独立部署，含 FLUX/SDXL 模型）
  - Pixelle-Video（独立 FastAPI 服务）
  - FFmpeg
  - Playwright（HTML 模板渲染）
```

### 1.2 部署验证

```bash
# 1. 安装 Pixelle-Video
git clone https://github.com/AIDC-AI/Pixelle-Video.git
cd Pixelle-Video
uv sync

# 2. 配置 .env
LLM_API_KEY=sk-xxx          # DeepSeek API
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
TTS_ENGINE=edge-tts         # 免费本地 TTS，无需 GPU

# 3. 启动 ComfyUI（独立进程）
python main.py --port 8188

# 4. 启动 Pixelle-Video
uv run streamlit run web/app.py --server.port 8501

# 5. 验证：POST /api/video/generate/async
curl -X POST http://localhost:8501/api/video/generate/async \
  -d '{"text":"养生茶的功效与泡法","mode":"generate","n_scenes":5}'
```

### 1.3 验证标准

- [ ] 输入关键词，3-5 分钟内产出 1080x1920（竖屏）MP4
- [ ] 视频包含：AI 生成画面 + 配音 + 字幕 + 背景音乐
- [ ] API 返回 task_id，轮询获取完成状态和视频路径

---

## Phase 2：服务端视频生成服务

### 2.1 新增配置

`server/app/config.py` 或 `.env`：

```python
PIXELLE_VIDEO_URL = "http://localhost:8501"
PIXELLE_VIDEO_TIMEOUT = 600  # 10 分钟超时
```

### 2.2 新增 `video_service.py`

```python
# server/app/services/video_service.py
import httpx
from pathlib import Path

class VideoGenerationService:
    def __init__(self):
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=config.PIXELLE_VIDEO_URL,
                timeout=httpx.Timeout(30, connect=10),
            )
        return self._client

    async def generate_script(self, keyword: str, n_scenes: int = 5) -> dict:
        """调用 AI 根据关键词生成分镜脚本（使用项目已有 content_service AI）。"""
        ...

    async def submit_video_task(self, script: dict, template: str, voice: str, bgm: str) -> str:
        """POST /api/video/generate/async → 返回 pixelle_task_id。
        重试: 3次，指数退避。异常: httpx.ConnectError / HTTPStatusError → 日志 + raise。
        """
        ...

    async def poll_task(self, pixelle_task_id: str, timeout: int) -> dict | None:
        """轮询 GET /api/tasks/{pixelle_task_id} → 每 10s 一次，直到 completed/failed 或超时。
        返回: {status, video_path, duration} 或 None(超时)。
        video_path 需清洗：仅保留文件名，拼接项目视频目录，拒绝含 ../ 的路径。
        """
        ...

    def _sanitize_path(self, raw_path: str) -> Path:
        """只取文件名，拒绝路径遍历。视频统一存 server/data/videos/ 下。"""
        name = Path(raw_path).name
        return Path("server/data/videos") / name

    async def generate_video(self, keyword: str, n_scenes: int = 5) -> dict:
        """完整流水线（async）。返回: {success, video_path, title, duration, error?}"""
        ...
```

### 2.3 新增 `generate_video` 任务类型

**任务参数（params）：**

```json
{
  "keyword": "养生茶",
  "n_scenes": 5,
  "template": "1080x1920/image_default.html",
  "tts_voice": "zh-CN-XiaoxiaoNeural",
  "bgm_id": "calm_01"
}
```

**执行流程（服务端后台任务，不经过设备）：**

> generate_video 是纯服务端任务，不走设备 poll/claim 流程。创建时立即标记 RUNNING，启动 FastAPI BackgroundTasks 异步执行，完成后更新状态。

```
POST /api/tasks (type=generate_video) 创建任务
  → task_service.create_task(status="running", device_id=None)
  → BackgroundTasks: _execute_video_task(task_id, params)
      → video_service.generate_script(keyword)        # AI 生成脚本
      → video_service.submit_video_task(script)        # 提交 Pixelle-Video (httpx async)
      → while timeout:
          video_service.poll_task(task_id)             # 轮询 GET /api/tasks/{id}
      → 完成: GeneratedVideo 入库, task.result 写入
      → task_service.report_result("completed")
      → 失败: retry_count++, 超过3次标记 failed
  → WS broadcast task_updated

get_pending_task() 排除 generate_video 类型，防止设备误领取。
```

### 2.4 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/videos` | 已生成视频列表（管理端） |
| `GET` | `/api/videos/{video_id}` | 单个视频详情 |
| `GET` | `/api/videos/{video_id}/download` | 下载 MP4 文件 |
| `DELETE` | `/api/videos/{video_id}` | 删除视频 |

### 2.5 数据库

```python
class GeneratedVideo(Base):
    __tablename__ = "generated_videos"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    keyword = Column(String(200), nullable=False)
    title = Column(String(500))
    script = Column(JSON)           # 分镜脚本
    video_path = Column(String(500)) # 本地文件路径
    duration = Column(Float)         # 秒
    status = Column(String(20), default="pending")  # pending/processing/completed/failed
    pixelle_task_id = Column(String(100))  # Pixelle-Video 任务 ID
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
```

---

## 变更影响范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `server/.env` | 修改 | 新增 PIXELLE_VIDEO_URL 配置 |
| `server/app/config.py` | 修改 | 新增视频相关配置项 |
| `server/app/db_models.py` | 修改 | 新增 GeneratedVideo 模型 |
| `server/app/services/video_service.py` | **新建** | 视频生成服务 |
| `server/app/routers/videos.py` | **新建** | 视频管理 API |
| `server/app/main.py` | 修改 | 注册 videos router |
| `server/app/models.py` | 修改 | 新增 TaskType.generate_video + Pydantic 模型 |
| `server/app/services/task_service.py` | 修改 | `get_pending_task` 排除 generate_video（防止设备误领取）；`report_result` 对 generate_video 跳过 stats 递增 |

### 不上线的

- 前端视频管理页面（Phase 2.5，本 spec 先 API only）
- 设备端 publish handler（Phase 3，需要真机调试）
- 通道化视频任务（Phase 4，等发布 handler 就绪后）

---

## 自审

- 无 TBD / TODO
- Phase 1 与 Phase 2 边界清晰：P1 只管 Pixelle-Video 跑通，P2 是服务端代码
- 只新建 2 个文件（video_service.py, videos.py），改动 5 个现有文件
- 视频文件存储路径：`server/data/videos/{video_id}.mp4`
- 单个视频生成全程阻塞（等 ComfyUI 出片），不涉及并发队列
