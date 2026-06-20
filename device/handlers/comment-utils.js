// device/handlers/comment-utils.js
// 评论相关共享工具 — search-collect 和 reply-comment 的公共方法
// 消除代码重复和循环依赖

var uiOperator = require("../core/ui-operator");
var selectorLoader = require("../core/selector-loader");
var selectorResolver = require("../core/selector-resolver");
var logger = require("../utils/logger");

var TAG = "评论工具";

var commentUtils = {

  /**
   * 打开评论区 — 统一实现，合并 search-collect 和 reply-comment 的最佳行为
   * @returns {boolean}
   */
  openComments: function () {
    // 1. 先检测评论区是否已打开
    var items = uiOperator.findElements("comment_list", 500, true);
    if (items && items.length > 0) {
      logger.debug(TAG, "评论区已打开 (" + items.length + " 条可见)");
      return true;
    }

    // 2. 点击视频评论按钮，指数退避重试
    for (var retry = 0; retry < 3; retry++) {
      var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
      if (commentBtn) {
        uiOperator.clickElement(commentBtn);
        sleep(1500);
        items = uiOperator.findElements("comment_list", 2000, true);
        if (items && items.length > 0) {
          logger.debug(TAG, "评论区已打开 (" + items.length + " 条)");
          return true;
        }
      }
      if (retry < 2) sleep(1000 * Math.pow(2, retry));  // 2s, 4s
    }

    // 3. 兜底：back() 关闭可能误触的弹窗后重试 comment_btn
    back(); sleep(800);
    commentBtn = uiOperator.findElement("video_comment_btn", 2000);
    if (commentBtn) {
      uiOperator.clickElement(commentBtn);
      sleep(1500);
      items = uiOperator.findElements("comment_list", 1000, true);
      if (items && items.length > 0) return true;
    }

    logger.warn(TAG, "评论区打开失败");
    return false;
  },

  /**
   * 预检评论数 — 从评论按钮 desc 解析数字，零评论提前跳过
   * @param {UiObject} commentBtn
   * @returns {{count: number, rawDesc: string}} count=-1 表示未知
   */
  preCheckCommentCount: function (commentBtn) {
    var result = { count: -1, rawDesc: "" };
    if (!commentBtn || commentBtn.isImage || commentBtn.isCoordinate) return result;
    try {
      result.rawDesc = commentBtn.desc() || "";
      var numMatch = result.rawDesc.match(/(\d+)/);
      if (numMatch) {
        result.count = parseInt(numMatch[1]);
      } else if (result.rawDesc.length > 0) {
        result.count = 0;
      }
    } catch (e) {}
    return result;
  },

  /**
   * 解析单条评论
   * @param {UiObject} item - 评论项元素
   * @param {Object} [handler] - 可选，BaseHandler 实例
   * @returns {Object|null}
   */
  parseCommentItem: function (item, handler) {
    var findChild = (handler && handler._findChildBySelector)
      ? function (p, a) { return handler._findChildBySelector(p, a); }
      : function (p, a) { return selectorResolver.findChildBySelector(p, a); };
    var extractVal = (handler && handler._extractChildValue)
      ? function (el, a, fb) { return handler._extractChildValue(el, a, fb); }
      : function (el, a, fb) { return selectorResolver.extractChildValue(el, a, fb); };

    try {
      // 昵称
      var nicknameEl = findChild(item, "comment_author");
      var nickname = nicknameEl ? extractVal(nicknameEl, "comment_author", "unknown") : null;
      if (!nickname) {
        nicknameEl = item.findOne(clickable(true).className("android.widget.TextView"));
        nickname = nicknameEl ? extractVal(nicknameEl, "comment_author", "unknown") : "unknown";
      }

      // 评论文本
      var textEl = findChild(item, "comment_text");
      var text = textEl ? extractVal(textEl, "comment_text", "") : "";
      if (!text) {
        var textViews = item.find(className("android.widget.TextView"));
        var maxLen = 0;
        for (var i = 0; i < textViews.length; i++) {
          var t = textViews[i].text() || "";
          if (t.length > maxLen && t !== nickname) {
            maxLen = t.length;
            textEl = textViews[i];
          }
        }
        text = textEl ? extractVal(textEl, "comment_text", "") : "";
      }
      if (!text) return null;

      // 时间
      // selector 可能误匹配父级元素导致 text() 返回拼接后的全文本
      // 如 "昵称,评论文本,3小时前, · 广东,回复 按钮,"，需从中提取时间片段
      var timeEl = findChild(item, "comment_time");
      var rawTime = timeEl ? extractVal(timeEl, "comment_time", "") : "";
      var timeStr = commentUtils._cleanTimeStr(rawTime);

      // 是否作者
      var isAuthor = false;
      try {
        var authorEl = findChild(item, "comment_is_author");
        if (!authorEl) authorEl = item.findOne(text("作者"));
        if (authorEl) isAuthor = true;
      } catch (e) { /* ignore */ }

      return {
        nickname: nickname,
        text: text,
        time: timeStr,
        isAuthor: isAuthor,
        replyBtn: findChild(item, "comment_reply_button"),
        commentAuthorAvatarEl: findChild(item, "comment_author_avatar"),
      };
    } catch (e) {
      logger.warn(TAG, "解析评论项出错: " + e.message);
      return null;
    }
  },

  /**
   * 解析评论时间 — 支持 "刚刚"/"X分钟前"/"X小时前"/"X天前"/"昨天"/"前天"/"MM-DD"/"YYYY-MM-DD"
   * @param {string} timeStr
   * @returns {Date|null}
   */
  /**
   * 将评论原始时间字符串转为北京时间 ISO 格式 (YYYY-MM-DDTHH:mm:ss+08:00)
   * 用于上报服务端，替换相对时间如 "19分钟前"
   */
  toBeijingTime: function (timeStr) {
    if (!timeStr) return "";
    var parsed = this.parseTime(timeStr);
    if (!parsed) return timeStr;
    var y = parsed.getFullYear();
    var mo = ("0" + (parsed.getMonth() + 1)).slice(-2);
    var d = ("0" + parsed.getDate()).slice(-2);
    var h = ("0" + parsed.getHours()).slice(-2);
    var mi = ("0" + parsed.getMinutes()).slice(-2);
    var s = ("0" + parsed.getSeconds()).slice(-2);
    return y + "-" + mo + "-" + d + "T" + h + ":" + mi + ":" + s + "+08:00";
  },

  parseTime: function (timeStr) {
	    if (!timeStr) return null;
	    var now = new Date();

	    if (timeStr.indexOf('刚刚') != -1) return now;

	    var yearMatch = timeStr.match(/(\d+)\s*年前/);
	    if (yearMatch) return new Date(now.getTime() - parseInt(yearMatch[1]) * 365 * 24 * 60 * 60 * 1000);

	    var monthMatch = timeStr.match(/(\d+)\s*个月前/);
	    if (monthMatch) return new Date(now.getTime() - parseInt(monthMatch[1]) * 30 * 24 * 60 * 60 * 1000);

	    var weekMatch = timeStr.match(/(\d+)\s*周前/);
	    if (weekMatch) return new Date(now.getTime() - parseInt(weekMatch[1]) * 7 * 24 * 60 * 60 * 1000);

	    var dayMatch = timeStr.match(/(\d+)\s*天前/);
	    if (dayMatch) return new Date(now.getTime() - parseInt(dayMatch[1]) * 24 * 60 * 60 * 1000);

	    var hourMatch = timeStr.match(/(\d+)\s*小时前/);
	    if (hourMatch) return new Date(now.getTime() - parseInt(hourMatch[1]) * 60 * 60 * 1000);

	    var minMatch = timeStr.match(/(\d+)\s*分钟前/);
	    if (minMatch) return new Date(now.getTime() - parseInt(minMatch[1]) * 60 * 1000);

	    var secMatch = timeStr.match(/(\d+)\s*秒前/);
	    if (secMatch) return new Date(now.getTime() - parseInt(secMatch[1]) * 1000);

	    if (timeStr.indexOf('昨天') != -1) {
	      var yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
	      var hmMatch = timeStr.match(/(\d{1,2}):(\d{2})/);
	      if (hmMatch) yesterday.setHours(parseInt(hmMatch[1]), parseInt(hmMatch[2]), 0, 0);
	      return yesterday;
	    }

	    if (timeStr.indexOf('前天') != -1) {
	      var dayBefore = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 2);
	      var hm2 = timeStr.match(/(\d{1,2}):(\d{2})/);
	      if (hm2) dayBefore.setHours(parseInt(hm2[1]), parseInt(hm2[2]), 0, 0);
	      return dayBefore;
	    }

	    var ymdMatch = timeStr.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
	    if (ymdMatch) return new Date(parseInt(ymdMatch[1]), parseInt(ymdMatch[2]) - 1, parseInt(ymdMatch[3]));

	    // MM-DD / MM-DD HH:MM — 按当年算若为未来日期则回退一年
	    function _fixFuture(d) {
	      if (d > now) d.setFullYear(d.getFullYear() - 1);
	      return d;
	    }

	    var mdtMatch = timeStr.match(/^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$/);
	    if (mdtMatch) {
	      return _fixFuture(new Date(now.getFullYear(), parseInt(mdtMatch[1]) - 1, parseInt(mdtMatch[2]),
	                                 parseInt(mdtMatch[3]), parseInt(mdtMatch[4]), 0));
	    }

	    var mdMatch = timeStr.match(/^(\d{1,2})-(\d{1,2})$/);
	    if (mdMatch) {
	      return _fixFuture(new Date(now.getFullYear(), parseInt(mdMatch[1]) - 1, parseInt(mdMatch[2])));
	    }

	    logger.warn(TAG, '无法解析时间: ' + timeStr);
	    return null;
	  },

	/**
	 * 从被污染的 time_str 中提取真正的时间片段
	 * 当 comment_time selector 误匹配父元素时，text() 返回拼接全文本
	 * 如 "昵称,评论文本,3小时前, · 广东,回复 按钮," → "3小时前"
	 */
	_cleanTimeStr: function (raw) {
	  if (!raw) return "";
	  if (raw.length <= 15 && raw.indexOf(",") === -1) return raw;
	  var patterns = [
	    /\d+年前/, /\d+个月前/, /\d+周前/, /\d+天前/, /\d+小时前/, /\d+分钟前/, /\d+秒前/,
	    /刚刚/, /昨天\s*\d{1,2}:\d{2}/, /前天\s*\d{1,2}:\d{2}/,
	    /\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}/, /\d{4}-\d{1,2}-\d{1,2}/,
	    /\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}/, /\d{1,2}-\d{1,2}/,
	  ];
	  for (var i = 0; i < patterns.length; i++) {
	    var m = raw.match(patterns[i]);
	    if (m) return m[0];
	  }
	  return raw;
	},

localPreFilter: function (text) {
    if (!text) return false;
    var stripped = text
      .replace(/\[[^\]]+\]/g, "")
      .replace(/[\s~!@#$%^&*()_+\-={}|:;<>?,./'"'""'、。！，《》]+/g, "")
      .replace(/[^一-龥a-zA-Z0-9]/g, "")
      .trim();
    return !!(stripped && stripped.length > 2);
  },

  /**
   * 按时效筛选评论
   * @param {Array} comments
   * @param {number} maxAgeDays
   * @returns {Array}
   */
  filterByTime: function (comments, maxAgeMs) {
    var now = new Date();
    var cutoff = (maxAgeMs === Infinity) ? new Date(0) : new Date(now.getTime() - maxAgeMs);
    var filtered = [];
    for (var i = 0; i < comments.length; i++) {
      var commentDate = commentUtils.parseTime(comments[i].time);
      if (!commentDate || commentDate >= cutoff) {
        filtered.push(comments[i]);
      }
    }
    return filtered;
  },

  /**
   * 采集用户主页数据 — 统一的字段提取逻辑
   * @param {Object} options - { avatarEl: UiObject|null, uploadAvatar: bool }
   * @returns {Object|null}
   */
  collectProfileData: function (options) {
    options = options || {};
    var data = { nickname: "", douyin_id: "", likes_count: "", follow_count: "",
      fans_count: "", works_count: "", gender: "", age: "", ip_location: "", is_private: "否" };
    if (options.fallbackNickname) data.nickname = options.fallbackNickname;

    var fields = {
      "user_nickname": "nickname", "user_douyin_id": "douyin_id",
      "user_likes_count": "likes_count", "user_follow_count": "follow_count",
      "user_fans_count": "fans_count", "user_works_count": "works_count",
      "user_gender": "gender", "user_age": "age", "user_ip_location": "ip_location"
    };
    var hasData = false;
    for (var actionName in fields) {
      try {
        var el = uiOperator.findElement(actionName, 2000);
        if (el) {
          var selector = selectorLoader.get(actionName);
          data[fields[actionName]] = (selector && selector.purpose === "extract")
            ? uiOperator.extractValue(el, selector) : (el.text() || "");
          if (data[fields[actionName]]) hasData = true;
        }
      } catch (e) {}
    }
    if (data.nickname) hasData = true;

    // 清除 IP 属地前缀
    if (data.ip_location) data.ip_location = data.ip_location.replace(/^[·•・\s]+/, "");

    // 数字清洗：万/千单位转换
    commentUtils._cleanNumericFields(data);

    // 检查私密账号
    try { if (uiOperator.findElement("user_is_private", 2000)) data.is_private = "是"; } catch (e) {}

    if (!hasData) return null;

    logger.info(TAG, "用户数据: " + data.nickname + " | 抖音号=" + data.douyin_id +
      " | 粉丝=" + data.fans_count + " | 获赞=" + data.likes_count);

    // 头像裁剪 + 上传（仅采集流程，回复流程跳过）
    if (options.avatarEl && options.uploadAvatar && data.douyin_id) {
      var avatarBase64 = commentUtils._cropCircularAvatar(options.avatarEl);
      if (avatarBase64) {
        try { require("../core/api-client").uploadUserAvatar(data.douyin_id, avatarBase64); } catch (e) {}
      }
    }

    return data;
  },

  /**
   * 数字字段清洗 — 处理 "1.2万" / "3.5w" / "1,234" 等格式
   */
  _cleanNumericFields: function (data) {
    var numericFields = { likes_count: 1, follow_count: 1, fans_count: 1, works_count: 1 };
    for (var key in numericFields) {
      if (data[key]) {
        var raw = String(data[key]);
        var m = raw.match(/([\d.]+)\s*[万wW万]/);
        if (m) {
          data[key] = String(Math.round(parseFloat(m[1]) * 10000));
        } else {
          m = raw.match(/([\d.]+)\s*[千kK千]/);
          if (m) {
            data[key] = String(Math.round(parseFloat(m[1]) * 1000));
          } else {
            var digits = raw.replace(/[^\d]/g, "");
            data[key] = digits || "";
          }
        }
      }
    }
  },

  /**
   * 圆形头像裁剪 — 从当前屏幕截取头像区域的圆形裁剪
   * @param {UiObject} avatarEl
   * @returns {string|null} base64 PNG
   */
  _cropCircularAvatar: function (avatarEl) {
    if (!avatarEl || avatarEl.isImage || avatarEl.isCoordinate) return null;
    try {
      var avatarBounds = avatarEl.bounds();
      if (!avatarBounds) return null;

      var w = avatarBounds.right - avatarBounds.left;
      var h = avatarBounds.bottom - avatarBounds.top;
      var size = Math.min(w, h);
      var cx = avatarBounds.left + w / 2;
      var cy = avatarBounds.top + h / 2;
      var radius = size / 2;
      var left = Math.round(cx - radius);
      var top = Math.round(cy - radius);
      var sz = Math.round(size);

      var screen = null, squareImg = null, srcBitmap = null, outBitmap = null;
      try {
        screen = images.captureScreen();
        squareImg = images.clip(screen, left, top, sz, sz);
        if (squareImg) {
          srcBitmap = squareImg.getBitmap();
          outBitmap = android.graphics.Bitmap.createBitmap(
            sz, sz, android.graphics.Bitmap.Config.ARGB_8888
          );
          var canvas = new android.graphics.Canvas(outBitmap);
          var paint = new android.graphics.Paint();
          paint.setAntiAlias(true);
          paint.setFilterBitmap(true);
          canvas.drawCircle(radius, radius, radius, paint);
          paint.setXfermode(new android.graphics.PorterDuffXfermode(
            android.graphics.PorterDuff.Mode.SRC_IN
          ));
          canvas.drawBitmap(srcBitmap, 0, 0, paint);
          return images.toBase64(images.fromBitmap(outBitmap), "png");
        }
      } finally {
        if (outBitmap) outBitmap.recycle();
        if (srcBitmap) srcBitmap.recycle();
        if (squareImg) squareImg.recycle();
        if (screen) screen.recycle();
      }
    } catch (e) {
      logger.debug(TAG, "头像裁剪失败: " + e.message);
    }
    return null;
  },
};

module.exports = commentUtils;
