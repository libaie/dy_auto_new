/**
 * 自动标定 — 为新分辨率设备采集 image 模板
 *
 * 工作流程：
 * 1. 遍历所有选择器，找出有 coordinate 策略的 action
 * 2. 对每个 coordinate 策略，截图 → 按 x_percent/y_percent 裁剪区域 → 保存 PNG
 * 3. 批量上传到服务端，自动创建对应 resolution_profile 的选择器行
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

var TAG = "标定";

// 入参：dir 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 ensureDirPath 对应业务流程的处理结果。
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
  // 入参：options 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 run 对应业务流程的处理结果。
  run: function (options) {
    options = options || {};
    var resolution = device.width + "x" + device.height;
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
      var targets = this._collectCoordinateActions(page.key);
      if (targets.length === 0) {
        logger.info(TAG, "页面[" + page.key + "] 无 coordinate 策略，跳过");
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
          var templateData = this._captureTemplate(t.action_name, t.x_percent, t.y_percent, resolution);
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
  // 入参：detectKey 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 _verifyPage 对应业务流程的处理结果。
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
   * 收集所有包含 coordinate 策略的 action
   */
  // 入参：pageKey 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 _collectCoordinateActions 对应业务流程的处理结果。
  _collectCoordinateActions: function (pageKey) {
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
      if (!sel.strategies) continue;

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
        if (st.type === "coordinate" && typeof st.x_percent === "number" && typeof st.y_percent === "number") {
          targets.push({
            action_name: actionName,
            x_percent: st.x_percent,
            y_percent: st.y_percent,
          });
          break; // 每个 action 只取第一个 coordinate 策略
        }
      }
    }
    return targets;
  },

  /**
   * 截图并裁剪模板区域
   * @returns {{ action_name, filename, data: bytes } | null}
   */
  // 入参：actionName、xPercent、yPercent、resolution 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 _captureTemplate 对应业务流程的处理结果。
  _captureTemplate: function (actionName, xPercent, yPercent, resolution) {
    var screen = images.captureScreen();
    if (!screen) {
      logger.warn(TAG, "截图失败: " + actionName);
      return null;
    }

    var cx = Math.round(xPercent * device.width);
    var cy = Math.round(yPercent * device.height);

    // 裁剪区域：以坐标为中心，取 10% 最小维度的弹性区域（±20% padding）
    var cropSize = Math.round(Math.min(device.width, device.height) * 0.10);
    cropSize = Math.max(40, Math.min(cropSize, 120));
    var left = Math.max(0, cx - cropSize);
    var top = Math.max(0, cy - cropSize);
    var w = Math.min(cropSize * 2, screen.getWidth() - left);
    var h = Math.min(cropSize * 2, screen.getHeight() - top);

    var tpl = null;
    try {
      tpl = images.clip(screen, left, top, w, h);
      screen.recycle();
      if (!tpl) return null;

      var filename = actionName + "@" + resolution + ".png";
      var tmpPath = "/sdcard/dy_auto/templates/" + resolution + "/" + filename;
      ensureDirPath("/sdcard/dy_auto/templates/" + resolution + "/");
      images.save(tpl, tmpPath, "png", 80);
      var data = files.readBytes(tmpPath);
      tpl.recycle();

      return {
        action_name: actionName,
        filename: filename,
        data: data,
        resolution: resolution,
      };
    } catch (e) {
      if (tpl) tpl.recycle();
      if (screen) { try { screen.recycle(); } catch (e2) {} }
      throw e;
    }
  },
};

module.exports = calibrator;
