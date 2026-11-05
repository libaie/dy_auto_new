/**
 * 自动标定 — 为新分辨率设备采集 image 模板
 *
 * 工作流程：
 * 1. 查找可通过语义控件/已验证图片确认的 action，排除纯坐标猜测
 * 2. 确认页面、目标及窗口稳定，将屏幕 bounds 换算为截图范围再裁剪
 * 3. 上传来源选择器与应用版本，创建对应 resolution_profile 的图片策略
 *
 * 调用时机：selectorLoader.init() 完成后，若 _cache 中缺少 action（无匹配 profile）
 *
 * 页面验证：每页采集前通过 uiOperator.detectPage() 验证当前页面指纹，
 * 避免无人值守时将错误页面截图上传为模板。
 */

var selectorLoader = require("./selector-loader");
var apiClient = require("./api-client");
var uiOperator = require("./ui-operator");
var logger = require("../utils/logger");
var screenContext = require("./screen-context");

var TAG = "标定";

function ensureDirPath(dir) {
  if (!dir) return false;
  try {
    var f = new java.io.File(String(dir));
    if (!f.exists()) f.mkdirs();
    return f.exists() && f.isDirectory();
  } catch (e) {
    logger.warn(TAG, "目录创建失败: " + dir + " - " + e.message);
    return false;
  }
}

var calibrator = {
  /**
   * 运行标定流程
   * @param {Object} options
   *   - pageKey: string (可选) — 只标定指定页面的 actions
   *     "search" | "video" | "comment" | "profile" | "dm"
   *   - unattended: boolean (内部) — 自动触发时跳过 toast 导航提示
   * @returns {{ captured: number, uploaded: number, errors: string[] }}
   */
  run: function (options) {
    options = options || {};
    var geometry = screenContext.read();
    if (!geometry) return { captured: 0, uploaded: 0, errors: ["无法获取设备几何信息"] };
    var resolution = geometry.width + "x" + geometry.height;
    var unattended = !!options.unattended;
    logger.info(TAG, "开始标定, 分辨率=" + resolution + (unattended ? " (自动)" : " (手动)"));

    var results = { captured: 0, uploaded: 0, errors: [] };

    // 五个页面分组，按顺序引导用户导航
    var pages = [
      { key: "search",  label: "请打开抖音搜索页（点击搜索图标进入搜索）", detectKey: "search" },
      { key: "video",   label: "请打开一个视频（进入视频详情页）",        detectKey: "video" },
      { key: "comment", label: "请打开视频评论区（点击评论按钮进入评论区）", detectKey: "comment" },
      { key: "profile", label: "请进入一个用户主页（点击头像进入个人主页）", detectKey: "profile" },
      { key: "dm",      label: "请打开私信聊天页（点击私信按钮进入私信）",   detectKey: "dm" },
    ];

    for (var pi = 0; pi < pages.length; pi++) {
      var page = pages[pi];
      if (options.pageKey && options.pageKey !== page.key) continue;
      var targets = this._collectObservableActions(page.key);
      if (options.actions) targets = targets.filter(function (target) { return options.actions.indexOf(target.action_name) !== -1; });
      if (targets.length === 0) {
        logger.info(TAG, "页面[" + page.key + "] 无可确认的目标策略，跳过");
        continue;
      }

      // 页面指纹验证——无人值守时不依赖用户手动导航
      if (unattended) {
        if (!this._verifyPage(page.detectKey)) {
          logger.warn(TAG, "自动标定: 页面[" + page.key + "] 指纹不匹配，跳过");
          continue;
        }
        logger.info(TAG, "自动标定: 页面[" + page.key + "] 指纹验证通过");
      } else {
        toast(page.label + " (" + (pi + 1) + "/" + pages.length + ")");
        logger.info(TAG, "等待导航到: " + page.key + " (" + targets.length + " 个元素)");
        sleep(5000);
        if (!this._verifyPage(page.detectKey)) {
          logger.warn(TAG, "手动标定: 页面[" + page.key + "] 指纹不匹配，跳过");
          continue;
        }
      }

      // 采集当前页面元素
      var uploads = [];
      for (var i = 0; i < targets.length; i++) {
        var t = targets[i];
        try {
          var templateData = this._captureTemplate(t, resolution);
          if (templateData) {
            uploads.push(templateData);
            results.captured++;
            logger.info(TAG, "[" + page.key + "] " + t.action_name + " (" + (i + 1) + "/" + targets.length + ")");
          }
        } catch (e) {
          results.errors.push(t.action_name + ": " + e.message);
          logger.warn(TAG, "采集失败: " + t.action_name + " - " + e.message);
        }
      }

      // 每页采集完立即上传
      if (uploads.length > 0) {
        try {
          var uploadResult = apiClient.uploadCalibration(uploads, resolution);
          if (uploadResult && uploadResult.uploaded) {
            results.uploaded += uploadResult.uploaded;
          }
        } catch (e) {
          results.errors.push("上传失败(" + page.key + "): " + e.message);
        }
      }

      logger.info(TAG, "页面[" + page.key + "] 完成: " + uploads.length + " 个模板");
    }

    toast("标定完成！采集=" + results.captured + " 上传=" + results.uploaded);
    logger.info(TAG, "标定完成: 采集=" + results.captured + ", 上传=" + results.uploaded + ", 错误=" + results.errors.length);
    return results;
  },

  /**
   * 验证当前页面指纹匹配目标页面
   * 通过 uiOperator.detectPage() 返回的 page_detect 名称模糊匹配
   */
  _verifyPage: function (detectKey) {
    try {
      var detected = uiOperator.detectPage();
      if (!detected) return false;
      return detected.indexOf(detectKey) !== -1;
    } catch (e) {
      logger.warn(TAG, "页面验证异常: " + e.message);
      return false;
    }
  },

  /**
   * 收集具备观测依据的动作；coordinate 不是元素存在的证据。
   */
  _collectObservableActions: function (pageKey) {
    var targets = [];
    var cache = selectorLoader._cache;

    // Page → action mapping for filtering
    var pageActions = {
      "search": ["search_tab", "search_button", "search_video_tab", "sort_button", "search_video_list"],
      "video": ["video_comment_btn", "like_button", "video_author_avatar", "off_video", "comment_off_btn", "is_shopping_cart"],
      "comment": ["comment_author_avatar", "comment_submit", "comment_list", "video_comment_input", "comment_reply_button", "comment_input"],
      "profile": ["follow_button", "dm_entry_btn", "user_nickname", "user_is_private", "is_follow"],
      "dm": ["dm_input", "dm_send"],
    };

    for (var actionName in cache) {
      if (!cache.hasOwnProperty(actionName)) continue;
      var sel = cache[actionName];
      if (!sel.strategies || sel.purpose === "page_detect" || sel.purpose === "extract") continue;

      // Filter by page if specified
      if (pageKey) {
        var allowed = false;
        for (var pk in pageActions) {
          if (!pageActions.hasOwnProperty(pk)) continue;
          if (pk === pageKey && pageActions[pk].indexOf(actionName) !== -1) {
            allowed = true;
            break;
          }
        }
        if (!allowed) continue;
      }

      for (var i = 0; i < sel.strategies.length; i++) {
        var st = sel.strategies[i];
        if (st.type !== "coordinate" && st.type !== "package" && (st.conditions || ["text", "id", "desc", "className", "chain", "image"].indexOf(st.type) !== -1)) {
          targets.push({
            action_name: actionName,
            selector: sel,
          });
          break;
        }
      }
    }
    return targets;
  },

  _findObservedBounds: function (target) {
    if (!target || !target.selector || !target.selector.strategies) return null;
    var strategies = target.selector.strategies.slice().sort(function (a, b) { return (a.priority || 0) - (b.priority || 0); });
    for (var i = 0; i < strategies.length; i++) {
      var strategy = strategies[i];
      if (strategy.type === "coordinate" || strategy.type === "package") continue;
      if (strategy.type === "image") {
        var imageTarget = uiOperator._findByStrategy(strategy);
        // A single best image match need not be unique. Only a matcher that
        // explicitly verified uniqueness may seed a new automatic template.
        if (imageTarget && imageTarget.isImage && imageTarget.unique === true) {
          var imageBounds = screenContext.rect(imageTarget.bounds);
          if (imageBounds) return imageBounds;
        }
        continue;
      }
      var candidates = uiOperator._findManyByStrategy(strategy) || [];
      var observed = [];
      for (var ci = 0; ci < candidates.length; ci++) {
        var candidate = candidates[ci];
        if (!candidate || candidate.isCoordinate || candidate.isPress || candidate.isPackage || !uiOperator._isOnScreen(candidate)) continue;
        try {
          var candidateBounds = screenContext.rect(candidate.bounds());
          if (candidateBounds) observed.push(candidateBounds);
        } catch (e) {}
      }
      if (observed.length === 1) return observed[0];
    }
    return null;
  },

  /**
   * 截图并裁剪模板区域
   * @returns {{ action_name, filename, data: bytes } | null}
   */
  _captureTemplate: function (target, resolution) {
    var before = screenContext.read();
    var bounds = this._findObservedBounds(target);
    if (!before || !bounds) return null;
    var actionName = target.action_name;
    var screen = images.captureScreen();
    if (!screen) {
      logger.warn(TAG, "截图失败: " + actionName);
      return null;
    }

    var tpl = null;
    try {
      var ctx = screenContext.read(screen);
      if (!ctx || !ctx.captureValid || ctx.signature !== before.signature || ctx.width + "x" + ctx.height !== resolution) return null;
      var afterBounds = this._findObservedBounds(target);
      if (!afterBounds || JSON.stringify(afterBounds) !== JSON.stringify(bounds)) return null;
      var visible = screenContext.intersect(bounds, ctx.contentBounds);
      if (!visible || JSON.stringify(visible) !== JSON.stringify(bounds)) return null;
      var center = { x: (bounds.left + bounds.right) / 2, y: (bounds.top + bounds.bottom) / 2 };
      if (!screenContext.isUsablePoint(center, ctx)) return null;
      if ((bounds.right - bounds.left) * (bounds.bottom - bounds.top) > ctx.width * ctx.height * 0.2) return null;
      for (var bi = 0; bi < ctx.blockedBounds.length; bi++) {
        if (screenContext.intersect(bounds, ctx.blockedBounds[bi])) return null;
      }
      var topLeft = screenContext.screenToCapture({ x: bounds.left, y: bounds.top }, ctx);
      var bottomRight = screenContext.screenToCapture({ x: bounds.right - 1, y: bounds.bottom - 1 }, ctx);
      if (!topLeft || !bottomRight) return null;
      var left = Math.min(topLeft.x, bottomRight.x), top = Math.min(topLeft.y, bottomRight.y);
      var width = Math.abs(bottomRight.x - topLeft.x) + 1, height = Math.abs(bottomRight.y - topLeft.y) + 1;
      if (width < 2 || height < 2) return null;
      tpl = images.clip(screen, left, top, width, height);
      if (!tpl) return null;

      var sourceResolution = ctx.captureWidth + "x" + ctx.captureHeight;
      var filename = String(actionName).replace(/[^A-Za-z0-9_.-]/g, "_") + "@" + sourceResolution + "_" + Date.now() + ".png";
      var tmpPath = "/sdcard/dy_auto/templates/" + resolution + "/" + filename;
      ensureDirPath("/sdcard/dy_auto/templates/" + resolution + "/");
      images.save(tpl, tmpPath, "png", 80);
      var data = files.readBytes(tmpPath);

      return {
        action_name: actionName,
        filename: filename,
        data: data,
        resolution: resolution,
        source_selector_id: target.selector.id,
        source_selector_version: target.selector.version,
        source_platform_version: target.selector.platform_version || "default",
        source_resolution_profile: target.selector.resolution_profile || "default",
        platform_version: String(selectorLoader._douyinVersion || target.selector.platform_version || "default"),
        source_resolution: sourceResolution,
        source_density: ctx.density * (ctx.captureRotation === 90 || ctx.captureRotation === 270 ? ctx.captureHeight / ctx.width : ctx.captureWidth / ctx.width),
      };
    } finally {
      if (tpl) tpl.recycle();
      screen.recycle();
    }
  },
};

module.exports = calibrator;
