/**
 * 自动标定 — 为新分辨率设备采集 image 模板
 *
 * 工作流程：
 * 1. 遍历所有选择器，找出有 coordinate 策略的 action
 * 2. 对每个 coordinate 策略，截图 → 按 x_percent/y_percent 裁剪区域 → 保存 PNG
 * 3. 批量上传到服务端，自动创建对应 resolution_profile 的选择器行
 *
 * 调用时机：selectorLoader.init() 完成后，若 _cache 中缺少 action（无匹配 profile）
 */

var selectorLoader = require("./selector-loader");
var apiClient = require("./api-client");
var uiOperator = require("./ui-operator");
var logger = require("../utils/logger");

var TAG = "标定";

var calibrator = {
  /**
   * 运行标定流程
   * @param {Object} options
   *   - pageKey: string (可选) — 只标定指定页面的 actions
   *     "search" | "video" | "comment" | "profile" | "dm"
   * @returns {{ captured: number, uploaded: number, errors: string[] }}
   */
  run: function (options) {
    options = options || {};
    var resolution = device.width + "x" + device.height;
    logger.info(TAG, "开始标定, 分辨率=" + resolution);

    var results = { captured: 0, uploaded: 0, errors: [] };

    // 收集所有有 coordinate 策略的 action
    var targets = this._collectCoordinateActions(options.pageKey);
    if (targets.length === 0) {
      logger.info(TAG, "未找到需要标定的 coordinate 策略");
      return results;
    }
    logger.info(TAG, "找到 " + targets.length + " 个待标定 action");

    // 逐个截图裁剪
    var uploads = [];
    for (var i = 0; i < targets.length; i++) {
      var t = targets[i];
      try {
        var templateData = this._captureTemplate(t.action_name, t.x_percent, t.y_percent, resolution);
        if (templateData) {
          uploads.push(templateData);
          results.captured++;
          logger.info(TAG, "已采集: " + t.action_name + " (" + (i + 1) + "/" + targets.length + ")");
        }
      } catch (e) {
        results.errors.push(t.action_name + ": " + e.message);
        logger.warn(TAG, "采集失败: " + t.action_name + " - " + e.message);
      }
    }

    // 批量上传
    if (uploads.length > 0) {
      try {
        var uploadResult = apiClient.uploadCalibration(uploads, resolution);
        if (uploadResult && uploadResult.uploaded) {
          results.uploaded = uploadResult.uploaded;
        }
      } catch (e) {
        results.errors.push("上传失败: " + e.message);
        logger.warn(TAG, "标定上传失败: " + e.message);
      }
    }

    logger.info(TAG, "标定完成: 采集=" + results.captured + ", 上传=" + results.uploaded);
    return results;
  },

  /**
   * 收集所有包含 coordinate 策略的 action
   */
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
      files.ensureDir("/sdcard/dy_auto/templates/" + resolution + "/");
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
