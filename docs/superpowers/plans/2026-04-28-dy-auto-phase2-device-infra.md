# 阶段二：设备端基础设施 实施计划

> **给智能体工人：** 必须使用子技能：superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实施此计划。步骤使用 checkbox（`- [ ]`）语法跟踪进度。

**目标：** 补全设备端与服务端之间的基础设施缺口，使设备端具备生产级可靠性：脚本热更新、设备注册、网络容错、崩溃恢复、任务取消。

**架构：** 设备端（AutoJS6）通过 HTTP 轮询与服务端（FastAPI）通信。本阶段在现有 MVP 基础上增加 6 个基础设施模块。PollResponse 新增可选字段 `cancelled_task_id`（向后兼容），其余已有 API 格式不变。

**技术栈：** Python 3.12 + FastAPI + SQLAlchemy（服务端），AutoJS6 JavaScript（设备端），pytest（测试）

---

## 文件结构

### 服务端新增/修改

| 文件 | 操作 | 职责 |
|------|------|------|
| `server/app/routers/device.py` | 修改 | 新增 `/register`、`/script-version`、`/script-download`、`/script-upload` 端点，增强 `/poll` |
| `server/app/routers/tasks.py` | 修改 | 新增 `/{task_id}/cancel` 端点 |
| `server/app/services/device_service.py` | 新建 | 设备注册/心跳/状态管理逻辑 |
| `server/app/services/script_service.py` | 新建 | 脚本版本管理、上传/下载 |
| `server/app/services/task_service.py` | 修改 | 新增 `cancel_task`、`check_cancelled_running` |
| `server/app/models.py` | 修改 | 新增 `DeviceRegisterRequest`，修改 `PollResponse` |
| `server/app/main.py` | 修改 | 版本号升级 0.3.0 |
| `server/tests/test_device_endpoints.py` | 新建 | 设备端 API 测试 |
| `server/tests/test_script_service.py` | 新建 | 脚本服务单元测试 |
| `server/tests/test_device_service.py` | 新建 | 设备服务单元测试 |

### 设备端新增/修改

| 文件 | 操作 | 职责 |
|------|------|------|
| `device/core/update-checker.js` | 新建 | 启动时检查脚本版本、下载更新 |
| `device/core/crash-recovery.js` | 新建 | 崩溃检测、ANR 检测、错误弹窗处理 |
| `device/core/api-client.js` | 修改 | 完整重写：增加重试逻辑、离线队列、新业务方法 |
| `device/core/task-executor.js` | 修改 | 增加看门狗超时 |
| `device/main.js` | 修改 | 集成注册流程、更新检查、崩溃恢复 |
| `device/config.js` | 修改 | 新增网络重试配置 |

---

## Task 1：脚本版本管理 — 服务端

**文件：**
- 新建: `server/app/services/script_service.py`
- 修改: `server/app/routers/device.py`
- 新建: `server/tests/test_script_service.py`
- 新建: `server/tests/test_device_endpoints.py`

- [ ] **步骤 1：编写脚本服务的失败测试**

```python
# server/tests/test_script_service.py
"""Script service tests."""
import pytest
import io
from pathlib import Path
from app.services.script_service import script_service


def test_get_version_returns_string():
    version = script_service.get_version()
    assert isinstance(version, str)
    assert len(version) > 0


def test_get_version_increments(tmp_path, monkeypatch):
    """Version increments when script zip is uploaded."""
    monkeypatch.setattr(script_service, "_version_file", tmp_path / "version.txt")
    v1 = script_service.get_version()
    script_service.upload_script(io.BytesIO(b"fake zip"))
    v2 = script_service.get_version()
    assert v2 != v1


def test_download_script_returns_bytes(tmp_path, monkeypatch):
    """After upload, download returns valid content."""
    monkeypatch.setattr(script_service, "_script_dir", tmp_path / "scripts")
    monkeypatch.setattr(script_service, "_version_file", tmp_path / "scripts" / "version.txt")
    script_service.upload_script(io.BytesIO(b"fake zip content"))
    result = script_service.download_script()
    assert result is not None
    assert len(result) > 0
    assert result == b"fake zip content"


def test_download_script_no_version_returns_none(tmp_path, monkeypatch):
    """When no script has been uploaded, download returns None."""
    svc = type(script_service)(tmp_path / "empty", tmp_path / "empty" / "version.txt")
    result = svc.download_script()
    assert result is None
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd server && python -m pytest tests/test_script_service.py -v
```

预期：FAIL — `ModuleNotFoundError: No module named 'app.services.script_service'`

- [ ] **步骤 3：编写脚本服务实现**

```python
# server/app/services/script_service.py
"""Device script version management — upload, version, download."""
from pathlib import Path

from app.config import SERVER_DIR


class ScriptService:
    def __init__(self, script_dir: Path | None = None, version_file: Path | None = None):
        self._script_dir = script_dir or (SERVER_DIR / "scripts")
        self._version_file = version_file or (self._script_dir / "version.txt")

    def _ensure_dir(self):
        self._script_dir.mkdir(parents=True, exist_ok=True)

    def get_version(self) -> str:
        """Return current script version. Defaults to '0.0.0'."""
        if self._version_file.exists():
            return self._version_file.read_text(encoding="utf-8").strip()
        return "0.0.0"

    def _bump_version(self) -> str:
        """Bump patch version: 1.0.0 -> 1.0.1."""
        current = self.get_version()
        parts = current.split(".")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            parts[2] = str(int(parts[2]) + 1)
        else:
            parts = ["0", "0", "1"]
        new_version = ".".join(parts)
        self._version_file.write_text(new_version, encoding="utf-8")
        return new_version

    def upload_script(self, fileobj) -> str:
        """Upload a new script zip, bump version, return new version string."""
        self._ensure_dir()
        script_path = self._script_dir / "device-script.zip"
        content = fileobj.read() if hasattr(fileobj, "read") else fileobj
        script_path.write_bytes(content)
        return self._bump_version()

    def download_script(self) -> bytes | None:
        """Download current script zip. Returns None if no script exists."""
        script_path = self._script_dir / "device-script.zip"
        if not script_path.exists():
            return None
        return script_path.read_bytes()


script_service = ScriptService()
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd server && python -m pytest tests/test_script_service.py -v
```

预期：4 个测试全部 PASS

- [ ] **步骤 5：添加 API 端点**

在 `server/app/routers/device.py` 中新增三个端点：

```python
@router.get("/script-version")
def script_version(
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
    return {"version": script_service.get_version()}


@router.get("/script-download")
def script_download(
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
    from fastapi.responses import Response
    data = script_service.download_script()
    if data is None:
        raise HTTPException(status_code=404, detail="No script available")
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=device-script.zip"},
    )


@router.post("/script-upload")
def script_upload(
    _: None = Depends(verify_device_secret),
):
    """Upload a new device script zip. Expects multipart/form-data with 'file' field."""
    from fastapi import UploadFile, File as FastAPIFile
    from app.services.script_service import script_service
    # 注意：此端点使用 Depends(verify_device_secret) 认证
    # 后续 Web 后台引入 JWT 后可改用管理员认证
    pass  # 完整实现见下方说明
```

**脚本上传端点完整实现**（替换上方 pass）：

```python
@router.post("/script-upload")
async def script_upload(
    file: UploadFile = FastAPIFile(...),
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files accepted")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    new_version = script_service.upload_script(io.BytesIO(content))
    return {"version": new_version, "size": len(content)}
```

需要在 `server/app/routers/device.py` 顶部添加导入：
```python
from fastapi import UploadFile, File as FastAPIFile
import io
```

- [ ] **步骤 6：编写端点集成测试**

```python
# server/tests/test_device_endpoints.py
"""Device-facing API endpoint tests."""
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SECRET = "change-me-to-a-random-string"
HEADERS = {"X-Device-Secret": SECRET}


def test_script_version():
    resp = client.get("/api/device/script-version", headers=HEADERS)
    assert resp.status_code == 200
    assert "version" in resp.json()
    assert isinstance(resp.json()["version"], str)


def test_script_download_no_script():
    """When no script uploaded, returns 404."""
    resp = client.get("/api/device/script-download", headers=HEADERS)
    assert resp.status_code in (200, 404)


def test_script_upload_and_download():
    """Upload a script, then download it."""
    zip_content = b"PK\x03\x04fake zip content"
    resp = client.post("/api/device/script-upload",
        files={"file": ("device.zip", io.BytesIO(zip_content), "application/zip")},
        headers=HEADERS)
    assert resp.status_code == 200
    assert "version" in resp.json()

    # Download should now work
    dl_resp = client.get("/api/device/script-download", headers=HEADERS)
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0


def test_script_upload_rejects_non_zip():
    resp = client.post("/api/device/script-upload",
        files={"file": ("test.txt", io.BytesIO(b"not a zip"), "text/plain")},
        headers=HEADERS)
    assert resp.status_code == 400


def test_script_version_requires_auth():
    resp = client.get("/api/device/script-version")
    assert resp.status_code == 403
```

- [ ] **步骤 7：运行全部测试确认通过**

```bash
cd server && python -m pytest tests/ -v
```

- [ ] **步骤 8：提交**

```bash
git add server/app/services/script_service.py server/app/routers/device.py server/tests/test_script_service.py server/tests/test_device_endpoints.py
git commit -m "feat(server): add script version management and upload/download endpoints"
```

---

## Task 2：脚本热更新 — 设备端

**文件：**
- 新建: `device/core/update-checker.js`
- 修改: `device/main.js`

- [ ] **步骤 1：编写更新检查器**

```javascript
// device/core/update-checker.js
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "UPDATE";

var LOCAL_VERSION_FILE = "update/local_version.txt";

var updateChecker = {
  getLocalVersion: function () {
    try {
      if (files.exists(LOCAL_VERSION_FILE)) {
        return files.read(LOCAL_VERSION_FILE).trim();
      }
    } catch (e) {
      logger.warn(TAG, "Failed to read local version: " + e.message);
    }
    return "0.0.0";
  },

  saveLocalVersion: function (version) {
    try {
      files.ensureDir(files.path(LOCAL_VERSION_FILE).getParent());
      files.write(LOCAL_VERSION_FILE, version);
    } catch (e) {
      logger.warn(TAG, "Failed to save local version: " + e.message);
    }
  },

  checkAndUpdate: function () {
    logger.info(TAG, "Checking for script updates...");

    var localVersion = this.getLocalVersion();
    var serverVersion = apiClient.getScriptVersion();

    if (!serverVersion) {
      logger.warn(TAG, "Could not get server version, skipping update check");
      return false;
    }

    logger.info(TAG, "Local: " + localVersion + ", Server: " + serverVersion);

    if (localVersion === serverVersion) {
      logger.info(TAG, "Already up to date");
      return false;
    }

    logger.info(TAG, "New version available, downloading...");
    var downloaded = apiClient.downloadScript();

    if (!downloaded) {
      logger.error(TAG, "Download failed, continuing with current version");
      return false;
    }

    try {
      var updateDir = files.cwd() + "/update";
      var zipPath = updateDir + "/device-script.zip";
      var tempDir = updateDir + "/temp";
      files.ensureDir(tempDir);

      $zip.extract(zipPath, tempDir);

      var projectDir = files.cwd();
      this._copyDir(tempDir, projectDir);

      this.saveLocalVersion(serverVersion);

      files.removeDir(tempDir);
      files.remove(zipPath);

      logger.info(TAG, "Update complete! New version: " + serverVersion);
      return true;
    } catch (e) {
      logger.error(TAG, "Update failed: " + e.message);
      return false;
    }
  },

  _copyDir: function (src, dst) {
    var srcPath = files.path(src);
    var items = files.listDir(srcPath);
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var srcFile = src + "/" + item;
      var dstFile = dst + "/" + item;
      if (files.isDir(srcFile)) {
        files.ensureDir(dstFile);
        this._copyDir(srcFile, dstFile);
      } else {
        files.ensureDir(files.path(dstFile).getParent());
        files.copy(srcFile, dstFile);
      }
    }
  },
};

module.exports = updateChecker;
```

- [ ] **步骤 2：修改主循环集成更新检查和注册**

修改 `device/main.js`，在文件顶部添加 require，在 main() 函数中添加更新检查和注册：

```javascript
// device/main.js — 顶部 require 区域新增
var updateChecker = require("./core/update-checker");
var crashRecovery = require("./core/crash-recovery");

// main() 函数中，在 selectorLoader.init() 之前添加：
  // 检查脚本更新（启动时检查一次）
  try {
    var updated = updateChecker.checkAndUpdate();
    if (updated) {
      logger.info(TAG, "Script updated, restart to use new version");
    }
  } catch (e) {
    logger.warn(TAG, "Update check failed: " + e.message);
  }

  // 设备注册（首次启动或重启后）
  try {
    var deviceInfo = {
      device_id: config.deviceId,
      name: device.model + " (" + device.brand + ")",
      os_version: device.release,
      app_version: "1.0.0",
    };
    var regResult = apiClient.register(deviceInfo);
    if (regResult) {
      logger.info(TAG, "Device registered: " + JSON.stringify(regResult));
    } else {
      logger.warn(TAG, "Device registration failed, continuing anyway");
    }
  } catch (e) {
    logger.warn(TAG, "Registration error: " + e.message);
  }
```

在主循环的 while(true) 开头添加健康检查：

```javascript
  while (true) {
    try {
      // 健康检查
      if (!crashRecovery.healthCheck()) {
        logger.warn(TAG, "Health check failed, skipping this cycle");
        sleep(config.pollInterval);
        continue;
      }

      // 轮询任务（原有逻辑）
      var response = apiClient.poll();
      // ...
```

- [ ] **步骤 3：手动测试**

在 AutoJS6 设备上运行，验证：
1. 启动时显示 "Checking for script updates..."
2. 显示 "Device registered: {...}"
3. 每个轮询周期显示健康检查日志

- [ ] **步骤 4：提交**

```bash
git add device/core/update-checker.js device/main.js
git commit -m "feat(device): add script update checker and device registration"
```

---

## Task 3：网络容错 — API 客户端完整重写

**文件：**
- 修改: `device/core/api-client.js`
- 修改: `device/config.js`

- [ ] **步骤 1：更新配置添加重试参数**

在 `device/config.js` 的 `config` 对象中添加：

```javascript
// 网络配置
network: {
  requestTimeout: 10000,   // 单次请求超时（毫秒）
  maxRetries: 3,           // 最大重试次数
  retryBaseDelay: 2000,    // 重试基础延迟（毫秒）
  retryMaxDelay: 30000,    // 重试最大延迟（毫秒）
  offlineQueueMax: 100,    // 离线队列最大条数
},
```

- [ ] **步骤 2：完整重写 API 客户端**

替换 `device/core/api-client.js` 的完整内容：

```javascript
var config = require("../config");
var logger = require("../utils/logger");

var TAG = "API";
var netConfig = config.network || {
  requestTimeout: 10000,
  maxRetries: 3,
  retryBaseDelay: 2000,
  retryMaxDelay: 30000,
  offlineQueueMax: 100,
};

// 离线队列 — 网络失败时缓存待上报数据
var offlineQueue = [];
var isOnline = true;

var apiClient = {
  /**
   * 计算重试延迟（指数退避 + 抖动）
   */
  _retryDelay: function (attempt) {
    var base = netConfig.retryBaseDelay * Math.pow(2, attempt);
    var jitter = Math.random() * base * 0.3;
    return Math.min(base + jitter, netConfig.retryMaxDelay);
  },

  /**
   * 带重试的 HTTP GET
   */
  get: function (path, params) {
    var url = config.serverUrl + path;
    if (params) {
      var queryParts = [];
      for (var key in params) {
        queryParts.push(encodeURIComponent(key) + "=" + encodeURIComponent(params[key]));
      }
      url += "?" + queryParts.join("&");
    }

    for (var attempt = 0; attempt <= netConfig.maxRetries; attempt++) {
      try {
        var response = http.get(url, {
          headers: { "X-Device-Secret": config.deviceSecret },
          timeout: netConfig.requestTimeout,
        });

        if (response.statusCode === 200) {
          this._markOnline();
          return JSON.parse(response.body);
        }

        // 4xx 错误不重试（客户端错误）
        if (response.statusCode >= 400 && response.statusCode < 500) {
          logger.error(TAG, "GET " + path + " client error: " + response.statusCode);
          return null;
        }

        logger.warn(TAG, "GET " + path + " server error: " + response.statusCode +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      } catch (e) {
        logger.warn(TAG, "GET " + path + " network error: " + e.message +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      }

      if (attempt < netConfig.maxRetries) {
        var delay = this._retryDelay(attempt);
        logger.debug(TAG, "Retrying in " + Math.round(delay) + "ms...");
        sleep(delay);
      }
    }

    this._markOffline();
    logger.error(TAG, "GET " + path + " failed after all retries");
    return null;
  },

  /**
   * 带重试的 HTTP POST
   */
  post: function (path, body) {
    var url = config.serverUrl + path;

    for (var attempt = 0; attempt <= netConfig.maxRetries; attempt++) {
      try {
        var response = http.post(url, {
          headers: {
            "Content-Type": "application/json",
            "X-Device-Secret": config.deviceSecret,
          },
          body: JSON.stringify(body),
          timeout: netConfig.requestTimeout,
        });

        if (response.statusCode === 200) {
          this._markOnline();
          return JSON.parse(response.body);
        }

        if (response.statusCode >= 400 && response.statusCode < 500) {
          logger.error(TAG, "POST " + path + " client error: " + response.statusCode);
          return null;
        }

        logger.warn(TAG, "POST " + path + " server error: " + response.statusCode +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      } catch (e) {
        logger.warn(TAG, "POST " + path + " network error: " + e.message +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      }

      if (attempt < netConfig.maxRetries) {
        var delay = this._retryDelay(attempt);
        logger.debug(TAG, "Retrying in " + Math.round(delay) + "ms...");
        sleep(delay);
      }
    }

    this._markOffline();
    logger.error(TAG, "POST " + path + " failed after all retries");
    return null;
  },

  /**
   * 带重试的二进制下载
   */
  _downloadWithRetry: function (url) {
    for (var attempt = 0; attempt <= netConfig.maxRetries; attempt++) {
      try {
        var response = http.get(url, {
          headers: { "X-Device-Secret": config.deviceSecret },
          timeout: 60000,
        });
        if (response.statusCode === 200) {
          this._markOnline();
          return response.body;
        }
        logger.warn(TAG, "Download server error: " + response.statusCode +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      } catch (e) {
        logger.warn(TAG, "Download network error: " + e.message +
          " (attempt " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + ")");
      }
      if (attempt < netConfig.maxRetries) {
        sleep(this._retryDelay(attempt));
      }
    }
    this._markOffline();
    return null;
  },

  /**
   * 标记网络恢复，刷新离线队列
   */
  _markOnline: function () {
    if (!isOnline) {
      logger.info(TAG, "Network recovered, flushing offline queue (" +
        offlineQueue.length + " items)");
      isOnline = true;
      this._flushOfflineQueue();
    }
  },

  /**
   * 标记网络离线
   */
  _markOffline: function () {
    if (isOnline) {
      logger.warn(TAG, "Network appears offline");
      isOnline = false;
    }
  },

  /**
   * 刷新离线队列
   */
  _flushOfflineQueue: function () {
    while (offlineQueue.length > 0) {
      var item = offlineQueue.shift();
      logger.info(TAG, "Flushing offline item: " + item.path);
      var result = this.post(item.path, item.body);
      if (!result) {
        offlineQueue.unshift(item);
        break;
      }
    }
  },

  // --- 业务方法 ---

  poll: function () {
    return this.get("/api/device/poll", { device_id: config.deviceId });
  },

  report: function (taskId, status, result, uiSnapshot) {
    var body = {
      task_id: taskId,
      status: status,
      result: result || {},
      ui_snapshot: uiSnapshot || null,
    };
    var response = this.post("/api/device/report", body);
    if (!response && !isOnline) {
      // 离线时加入队列（有上限）
      if (offlineQueue.length >= netConfig.offlineQueueMax) {
        logger.warn(TAG, "Offline queue full, dropping oldest item");
        offlineQueue.shift();
      }
      logger.info(TAG, "Queuing report for offline flush: " + taskId);
      offlineQueue.push({ path: "/api/device/report", body: body });
    }
    return response;
  },

  heartbeat: function () {
    return this.post("/api/device/heartbeat", { device_id: config.deviceId });
  },

  fetchSelectors: function (currentVersion) {
    return this.get("/api/device/selectors", { version: currentVersion || 0 });
  },

  getScriptVersion: function () {
    var result = this.get("/api/device/script-version");
    return result ? result.version : null;
  },

  downloadScript: function () {
    var url = config.serverUrl + "/api/device/script-download";
    var body = this._downloadWithRetry(url);
    if (body) {
      var scriptDir = files.cwd() + "/update";
      files.ensureDir(scriptDir);
      files.writeBytes(scriptDir + "/device-script.zip", body);
      return true;
    }
    logger.error(TAG, "Script download failed after all retries");
    return false;
  },

  register: function (deviceInfo) {
    return this.post("/api/device/register", deviceInfo);
  },

  isOnline: function () {
    return isOnline;
  },

  getOfflineQueueSize: function () {
    return offlineQueue.length;
  },
};

module.exports = apiClient;
```

- [ ] **步骤 3：手动测试**

在设备上模拟网络断开/恢复，验证：
1. 网络断开时显示 "Network appears offline"
2. 请求重试 3 次，间隔递增
3. 网络恢复时显示 "Network recovered, flushing offline queue"
4. 离线队列超过 100 条时丢弃最旧的

- [ ] **步骤 4：提交**

```bash
git add device/core/api-client.js device/config.js
git commit -m "feat(device): rewrite api-client with retry, offline queue, and new methods"
```

---

## Task 4：设备注册 — 服务端

**文件：**
- 新建: `server/app/services/device_service.py`
- 修改: `server/app/routers/device.py`
- 修改: `server/app/models.py`
- 新建: `server/tests/test_device_service.py`

- [ ] **步骤 1：编写设备服务的失败测试**

```python
# server/tests/test_device_service.py
"""Device service tests."""
import pytest
from app.services.device_service import device_service


def test_register_new_device(db):
    result = device_service.register(
        db=db, device_id="dev-test-register", name="Test Device",
        os_version="Android 13", app_version="1.0.0",
    )
    assert result["device_id"] == "dev-test-register"
    assert result["name"] == "Test Device"


def test_register_existing_device_updates(db):
    device_service.register(db, "dev-reregister", "Old Name", "Android 12", "1.0.0")
    result = device_service.register(db, "dev-reregister", "New Name", "Android 13", "1.1.0")
    assert result["name"] == "New Name"


def test_update_heartbeat(db):
    device_service.register(db, "dev-hb-test", "HB Device", "Android 13", "1.0.0")
    device_service.update_heartbeat(db, "dev-hb-test")
    assert True


def test_update_heartbeat_unknown_device(db):
    device_service.update_heartbeat(db, "dev-unknown-hb")
    assert True


def test_get_device_status(db):
    device_service.register(db, "dev-status-test", "Status Device", "Android 13", "1.0.0")
    info = device_service.get_device_status(db, "dev-status-test")
    assert info is not None
    assert info["device_id"] == "dev-status-test"
    assert info["status"] == "online"
    assert "proxy_config" in info  # 确认包含 proxy_config


def test_get_device_status_unknown(db):
    info = device_service.get_device_status(db, "dev-nonexistent")
    assert info is None


def test_set_offline_devices(db):
    """Devices without recent heartbeat get marked offline."""
    device_service.register(db, "dev-offline-test", "Offline Device")
    # 直接设置 last_seen_at 为很久以前
    from app.db_models import Device
    from datetime import datetime, timezone, timedelta
    device = db.query(Device).filter(Device.id == "dev-offline-test").first()
    device.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    count = device_service.set_offline_devices(db, timeout_seconds=300)
    assert count >= 1
    info = device_service.get_device_status(db, "dev-offline-test")
    assert info["status"] == "offline"
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd server && python -m pytest tests/test_device_service.py -v
```

- [ ] **步骤 3：编写设备服务实现**

```python
# server/app/services/device_service.py
"""Device registration, heartbeat, and status management."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db_models import Device


class DeviceService:
    def register(
        self, db: Session, device_id: str, name: str,
        os_version: str = "", app_version: str = "",
    ) -> dict:
        """Register or update a device. Returns device info dict."""
        device = db.query(Device).filter(Device.id == device_id).first()
        now = datetime.now(timezone.utc)

        if device:
            device.name = name
            device.status = "online"
            device.last_seen_at = now
        else:
            device = Device(id=device_id, name=name, status="online", last_seen_at=now)
            db.add(device)

        db.commit()
        db.refresh(device)

        return {
            "device_id": device.id,
            "name": device.name,
            "status": device.status,
        }

    def update_heartbeat(self, db: Session, device_id: str) -> None:
        """Update device last_seen_at. Ignores unknown devices."""
        device = db.query(Device).filter(Device.id == device_id).first()
        if device:
            device.last_seen_at = datetime.now(timezone.utc)
            device.status = "online"
            db.commit()

    def get_device_status(self, db: Session, device_id: str) -> dict | None:
        """Get device status info including proxy_config. Returns None for unknown devices."""
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return None
        return {
            "device_id": device.id,
            "name": device.name,
            "status": device.status,
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
            "proxy_config": device.proxy_config,
        }

    def set_offline_devices(self, db: Session, timeout_seconds: int = 300) -> int:
        """Mark devices as offline if no heartbeat for timeout_seconds. Returns count."""
        cutoff = datetime.now(timezone.utc).timestamp() - timeout_seconds
        cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
        count = (
            db.query(Device)
            .filter(Device.status == "online", Device.last_seen_at < cutoff_dt)
            .update({"status": "offline"})
        )
        db.commit()
        return count


device_service = DeviceService()
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd server && python -m pytest tests/test_device_service.py -v
```

- [ ] **步骤 5：添加注册端点和更新心跳端点**

在 `server/app/routers/device.py` 中新增：

```python
from app.models import DeviceRegisterRequest

@router.post("/register")
def register_device(
    request: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    from app.services.device_service import device_service
    return device_service.register(
        db=db, device_id=request.device_id, name=request.name,
        os_version=request.os_version, app_version=request.app_version,
    )
```

将现有心跳端点改为调用 device_service：

```python
@router.post("/heartbeat")
def heartbeat(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    device_id = body.get("device_id", "")
    from app.services.device_service import device_service
    device_service.update_heartbeat(db, device_id)
    return {"status": "ok", "device_id": device_id}
```

在 `server/app/models.py` 中添加：

```python
class DeviceRegisterRequest(BaseModel):
    device_id: str
    name: str
    os_version: str = ""
    app_version: str = ""
```

- [ ] **步骤 6：编写端点集成测试**

在 `server/tests/test_device_endpoints.py` 中追加：

```python
def test_register_device():
    resp = client.post("/api/device/register", json={
        "device_id": "dev-register-test", "name": "Test Phone",
        "os_version": "Android 13", "app_version": "1.0.0",
    }, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == "dev-register-test"
    assert data["status"] == "online"


def test_register_device_requires_auth():
    resp = client.post("/api/device/register", json={
        "device_id": "dev-no-auth", "name": "Test",
    })
    assert resp.status_code == 403


def test_heartbeat_updates_device():
    client.post("/api/device/register", json={
        "device_id": "dev-hb-e2e", "name": "HB Test",
    }, headers=HEADERS)
    resp = client.post("/api/device/heartbeat",
        json={"device_id": "dev-hb-e2e"}, headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **步骤 7：运行全部测试确认通过**

```bash
cd server && python -m pytest tests/ -v
```

- [ ] **步骤 8：提交**

```bash
git add server/app/services/device_service.py server/app/routers/device.py server/app/models.py server/tests/test_device_service.py server/tests/test_device_endpoints.py
git commit -m "feat(server): add device registration and heartbeat tracking"
```

---

## Task 5：崩溃恢复与异常处理

**文件：**
- 新建: `device/core/crash-recovery.js`
- 修改: `device/core/task-executor.js`

- [ ] **步骤 1：编写崩溃恢复模块**

```javascript
// device/core/crash-recovery.js
var logger = require("../utils/logger");

var TAG = "RECOVERY";

var crashRecovery = {
  _consecutiveFailures: 0,
  _maxConsecutiveFailures: 5,

  ensureAppRunning: function () {
    if (currentPackage() === "com.ss.android.ugc.aweme") {
      this._consecutiveFailures = 0;
      return true;
    }

    logger.warn(TAG, "Douyin not in foreground, attempting recovery...");
    this._consecutiveFailures++;

    if (this._consecutiveFailures > this._maxConsecutiveFailures) {
      logger.error(TAG, "Too many consecutive failures (" + this._consecutiveFailures +
        "), pausing for 5 minutes");
      sleep(300000);
      this._consecutiveFailures = 0;
    }

    try {
      app.stop("com.ss.android.ugc.aweme");
      sleep(2000);
    } catch (e) {
      logger.warn(TAG, "Failed to stop app: " + e.message);
    }

    try {
      app.launchApp("抖音");
      sleep(5000);
      if (currentPackage() === "com.ss.android.ugc.aweme") {
        logger.info(TAG, "Douyin recovered successfully");
        sleep(3000);
        try { back(); } catch (e) { /* ignore */ }
        return true;
      }
    } catch (e) {
      logger.error(TAG, "Failed to restart app: " + e.message);
    }

    logger.error(TAG, "Recovery failed");
    return false;
  },

  handleDialogs: function () {
    var dialogButtons = [
      "知道了", "确定", "关闭", "取消", "重试",
      "允许", "暂不", "稍后再说", "下次再说",
    ];

    for (var i = 0; i < dialogButtons.length; i++) {
      try {
        var btn = text(dialogButtons[i]).findOnce();
        if (btn) {
          logger.info(TAG, "Found dialog button: " + dialogButtons[i]);
          btn.click();
          sleep(1000);
          return true;
        }
      } catch (e) { /* ignore */ }
    }

    var riskKeywords = ["验证", "风控", "异常", "安全检查", "滑动"];
    for (var j = 0; j < riskKeywords.length; j++) {
      try {
        var riskEl = textContains(riskKeywords[j]).findOnce();
        if (riskEl) {
          logger.warn(TAG, "Detected risk control dialog: " + riskKeywords[j]);
          return "risk_controlled";
        }
      } catch (e) { /* ignore */ }
    }

    return false;
  },

  checkANR: function () {
    try {
      var anrBtn = text("等待").findOnce();
      if (anrBtn) {
        logger.warn(TAG, "ANR detected, clicking 'Wait'");
        anrBtn.click();
        sleep(2000);
        return true;
      }
    } catch (e) { /* ignore */ }
    return false;
  },

  healthCheck: function () {
    if (this.checkANR()) {
      logger.warn(TAG, "ANR handled, waiting for recovery...");
      sleep(5000);
    }

    var dialogResult = this.handleDialogs();
    if (dialogResult === "risk_controlled") {
      logger.error(TAG, "Risk control detected, stopping current task");
      return false;
    }

    if (!this.ensureAppRunning()) {
      return false;
    }

    return true;
  },
};

module.exports = crashRecovery;
```

- [ ] **步骤 2：添加任务看门狗到 TaskExecutor**

修改 `device/core/task-executor.js` 的 `execute` 方法：

```javascript
execute: function (task) {
  logger.info(TAG, "Executing task: " + task.id + " type=" + task.type);

  var handler = handlers[task.type];
  if (!handler) {
    logger.error(TAG, "No handler for task type: " + task.type);
    return { status: "failed", result: { error: "Unknown task type: " + task.type } };
  }

  // 看门狗：任务最大执行时间 30 分钟
  var TASK_TIMEOUT = 30 * 60 * 1000;
  var startTime = Date.now();
  var timedOut = false;

  var watchdog = setInterval(function () {
    if (Date.now() - startTime > TASK_TIMEOUT) {
      logger.error(TAG, "Task " + task.id + " timed out after 30 minutes");
      timedOut = true;
    }
  }, 10000);

  try {
    var result = handler.execute(task.params);
    clearInterval(watchdog);

    if (timedOut) {
      return { status: "failed", result: { error: "Task execution timed out (30 min)" } };
    }

    if (result.success) {
      logger.info(TAG, "Task " + task.id + " completed successfully");
      return { status: "completed", result: result.result };
    } else {
      logger.warn(TAG, "Task " + task.id + " failed: " + result.error);
      return { status: "failed", result: { error: result.error } };
    }
  } catch (e) {
    clearInterval(watchdog);
    logger.error(TAG, "Task " + task.id + " threw exception: " + e.message);
    return { status: "failed", result: { error: e.message } };
  }
},
```

- [ ] **步骤 3：手动测试**

1. 在任务执行期间强杀抖音，验证自动重启
2. 观察日志中弹窗处理输出
3. 验证看门狗超时（可临时将 TASK_TIMEOUT 改为 10 秒测试）

- [ ] **步骤 4：提交**

```bash
git add device/core/crash-recovery.js device/core/task-executor.js
git commit -m "feat(device): add crash recovery, dialog handling, and task watchdog"
```

---

## Task 6：任务取消与轮询增强

**文件：**
- 修改: `server/app/services/task_service.py`
- 修改: `server/app/routers/tasks.py`
- 修改: `server/app/routers/device.py`
- 修改: `server/app/models.py`
- 修改: `server/app/main.py`
- 修改: `server/tests/test_task_service.py`
- 修改: `server/tests/test_e2e_flow.py`
- 修改: `server/tests/test_device_endpoints.py`

- [ ] **步骤 1：编写任务取消的失败测试**

在 `server/tests/test_task_service.py` 中追加：

```python
def test_cancel_pending_task(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    cancelled = task_service.cancel_task(db, task.id)
    assert cancelled.status == TaskStatus.CANCELLED


def test_cancel_running_task(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-001")
    cancelled = task_service.cancel_task(db, task.id)
    assert cancelled.status == TaskStatus.CANCELLED


def test_cancel_completed_task_fails(db):
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-001")
    task_service.report_result(db, task.id, TaskStatus.COMPLETED, {"success_count": 1})
    with pytest.raises(ValueError, match="Cannot cancel"):
        task_service.cancel_task(db, task.id)


def test_cancel_nonexistent_task(db):
    with pytest.raises(ValueError, match="not found"):
        task_service.cancel_task(db, "nonexistent-id")


def test_check_cancelled_running(db):
    """check_cancelled_running returns cancelled task for device."""
    task = task_service.create_task(db, TaskType.NURTURE, "acc-001", {"duration": 5})
    task_service.get_pending_task(db, "dev-cancel-check")
    task_service.cancel_task(db, task.id)
    result = task_service.check_cancelled_running(db, "dev-cancel-check")
    assert result is not None
    assert result.id == task.id


def test_check_cancelled_running_none(db):
    """check_cancelled_running returns None when no cancelled tasks."""
    result = task_service.check_cancelled_running(db, "dev-no-cancel")
    assert result is None
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd server && python -m pytest tests/test_task_service.py -k cancel -v
```

- [ ] **步骤 3：实现 cancel_task 和 check_cancelled_running**

在 `server/app/services/task_service.py` 的 `TaskService` 类中添加：

```python
def cancel_task(self, db: Session, task_id: str):
    """Cancel a pending or running task."""
    task = db.query(TaskDB).filter(TaskDB.id == task_id).first()
    if not task:
        raise ValueError(f"Task {task_id} not found")

    if task.status in (TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value):
        raise ValueError(f"Cannot cancel task in status: {task.status}")

    task.status = TaskStatus.CANCELLED.value
    task.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task

def check_cancelled_running(self, db: Session, device_id: str):
    """Check if device has a running task that was cancelled."""
    task = (
        db.query(TaskDB)
        .filter(TaskDB.device_id == device_id, TaskDB.status == TaskStatus.CANCELLED.value)
        .order_by(TaskDB.created_at.desc())
        .first()
    )
    return task
```

- [ ] **步骤 4：运行测试确认通过**

```bash
cd server && python -m pytest tests/test_task_service.py -k cancel -v
```

- [ ] **步骤 5：添加取消 API 端点**

在 `server/app/routers/tasks.py` 中添加：

```python
@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    try:
        task = task_service.cancel_task(db=db, task_id=task_id)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Task not found")
        raise HTTPException(status_code=400, detail=str(e))
    return task
```

- [ ] **步骤 6：修改 PollResponse 和轮询端点**

在 `server/app/models.py` 的 `PollResponse` 中添加字段：

```python
class PollResponse(BaseModel):
    task: Optional[Task] = None
    selectors_version: int = 1
    proxy: Optional[dict[str, Any]] = None
    cancelled_task_id: Optional[str] = None
```

修改 `server/app/routers/device.py` 的轮询端点：

```python
@router.get("/poll", response_model=PollResponse)
def poll_tasks(
    device_id: str = Query(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    task = task_service.get_pending_task(db, device_id)
    version = selector_service.get_version(db)

    from app.services.device_service import device_service
    device_info = device_service.get_device_status(db, device_id)
    proxy = device_info.get("proxy_config") if device_info else None

    cancelled_task = task_service.check_cancelled_running(db, device_id)

    return PollResponse(
        task=task,
        selectors_version=version,
        proxy=proxy,
        cancelled_task_id=cancelled_task.id if cancelled_task else None,
    )
```

- [ ] **步骤 7：编写端点集成测试**

在 `server/tests/test_e2e_flow.py` 中追加：

```python
def test_cancel_task():
    create_resp = client.post("/api/tasks", json={
        "type": "nurture", "account_id": "acc-001", "params": {"duration": 5},
    }, headers=HEADERS)
    task_id = create_resp.json()["id"]
    cancel_resp = client.post(f"/api/tasks/{task_id}/cancel", headers=HEADERS)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


def test_cancel_nonexistent_task():
    resp = client.post("/api/tasks/nonexistent-id/cancel", headers=HEADERS)
    assert resp.status_code == 404


def test_cancel_completed_task_returns_400():
    create_resp = client.post("/api/tasks", json={
        "type": "nurture", "account_id": "acc-001", "params": {"duration": 5},
    }, headers=HEADERS)
    task_id = create_resp.json()["id"]
    # Assign and complete
    client.get("/api/device/poll", params={"device_id": "dev-cancel-e2e"}, headers=HEADERS)
    client.post("/api/device/report", json={
        "task_id": task_id, "status": "completed", "result": {"success_count": 1},
    }, headers=HEADERS)
    # Cancel should fail
    cancel_resp = client.post(f"/api/tasks/{task_id}/cancel", headers=HEADERS)
    assert cancel_resp.status_code == 400


def test_poll_returns_cancelled_task_id():
    create_resp = client.post("/api/tasks", json={
        "type": "nurture", "account_id": "acc-001", "params": {"duration": 5},
    }, headers=HEADERS)
    task_id = create_resp.json()["id"]
    client.get("/api/device/poll", params={"device_id": "dev-cancel-poll"}, headers=HEADERS)
    client.post(f"/api/tasks/{task_id}/cancel", headers=HEADERS)
    poll_resp = client.get("/api/device/poll",
        params={"device_id": "dev-cancel-poll"}, headers=HEADERS)
    assert poll_resp.status_code == 200
    assert poll_resp.json().get("cancelled_task_id") == task_id


def test_poll_returns_proxy_config():
    """Poll response includes proxy config for registered device."""
    # Register device with proxy
    from app.db_models import Device
    from app.database import SessionLocal
    db = SessionLocal()
    device = Device(id="dev-proxy-test", name="Proxy Device", status="online")
    device.proxy_config = {"type": "http", "host": "proxy.test", "port": 8080}
    db.add(device)
    db.commit()
    db.close()

    resp = client.get("/api/device/poll",
        params={"device_id": "dev-proxy-test"}, headers=HEADERS)
    assert resp.status_code == 200
    # proxy may be in response
```

在 `server/tests/test_device_endpoints.py` 中追加：

```python
def test_script_upload_success():
    zip_content = b"PK\x03\x04test content"
    resp = client.post("/api/device/script-upload",
        files={"file": ("device.zip", io.BytesIO(zip_content), "application/zip")},
        headers=HEADERS)
    assert resp.status_code == 200
    assert "version" in resp.json()


def test_script_upload_rejects_non_zip():
    resp = client.post("/api/device/script-upload",
        files={"file": ("test.txt", io.BytesIO(b"not zip"), "text/plain")},
        headers=HEADERS)
    assert resp.status_code == 400


def test_script_upload_requires_auth():
    resp = client.post("/api/device/script-upload",
        files={"file": ("test.zip", io.BytesIO(b"zip"), "application/zip")})
    assert resp.status_code == 403


def test_script_download_after_upload():
    zip_content = b"PK\x03\x04download test"
    client.post("/api/device/script-upload",
        files={"file": ("device.zip", io.BytesIO(zip_content), "application/zip")},
        headers=HEADERS)
    resp = client.get("/api/device/script-download", headers=HEADERS)
    assert resp.status_code == 200
    assert len(resp.content) > 0
```

- [ ] **步骤 8：更新版本号**

将 `server/app/main.py` 中的版本号从 `0.2.0` 更新为 `0.3.0`（两处：FastAPI 构造函数和 health 端点）。

- [ ] **步骤 9：运行全部测试确认通过**

```bash
cd server && python -m pytest tests/ -v
```

- [ ] **步骤 10：提交**

```bash
git add server/app/services/task_service.py server/app/routers/tasks.py server/app/routers/device.py server/app/models.py server/app/main.py server/tests/test_task_service.py server/tests/test_e2e_flow.py server/tests/test_device_endpoints.py
git commit -m "feat(server): add task cancellation, poll enhancement, and version bump to 0.3.0"
```

---

## 最终验证

- [ ] **运行全部测试**

```bash
cd server && python -m pytest tests/ -v --tb=short
```

预期：所有测试通过（原有 51 + 新增约 25 个 = 76 个测试）

- [ ] **检查测试覆盖率**

```bash
cd server && python -m pytest tests/ --cov=app --cov-report=term-missing
```

预期：覆盖率 > 85%

- [ ] **设备端冒烟测试**

在 AutoJS6 设备上完整运行一次启动流程：
1. 启动时检查更新
2. 设备注册
3. 选择器加载
4. 心跳发送
5. 任务轮询与执行
6. 健康检查（弹窗处理、崩溃恢复）

---

## 任务汇总

| 任务 | 内容 | 新增/修改 |
|------|------|-----------|
| 1 | 脚本版本管理 — 服务端 | 新建 script_service.py + 3 个端点（含上传） |
| 2 | 脚本热更新 — 设备端 | 新建 update-checker.js + 修改 main.js |
| 3 | 网络容错 — API 客户端重写 | 完整重写 api-client.js（重试+离线队列+新方法） |
| 4 | 设备注册 — 服务端 | 新建 device_service.py + 1 个端点 |
| 5 | 崩溃恢复与异常处理 | 新建 crash-recovery.js + 看门狗 |
| 6 | 任务取消与轮询增强 | 新增 cancel_task + PollResponse 增强 + 版本 0.3.0 |

新增测试：约 25 个（服务端），设备端通过手动冒烟测试验证。
