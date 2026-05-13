// 诊断脚本 v4 — 通用页面诊断
var _cwd = "/storage/emulated/0/脚本/device/";
var _load = function(mod) { return require(_cwd + mod); };

var logger = _load("utils/logger");
var config = _load("config");
var selectorLoader = _load("core/selector-loader");
var uiOperator = _load("core/ui-operator");
var TAG = "诊断";

logger.info(TAG, "======= 加载选择器 =======");
try {
  selectorLoader.init();
  logger.info(TAG, "版本: " + selectorLoader.getVersion());
} catch (e) {
  logger.warn(TAG, "加载失败: " + e.message);
}

// 测试所有选择器
var allActions = [
  "search_tab", "search_suggestion_list", "search_video_tab", "search_video_list", "search_button",
  "sort_button", "sort_latest", "sort_most_liked", "sort_default",
  "video_comment_btn", "video_comment_input", "comment_list", "comment_input",
  "comment_author", "comment_text", "comment_time", "comment_author_avatar",
  "comment_reply_button", "comment_like_count", "comment_reply_count", "comment_dislike_count", "comment_location",
  "like_button", "follow_button", "dm_entry_btn", "dm_input", "dm_send",
  "is_comment_view", "is_video_view", "is_user_view",
  "user_nickname", "user_douyin_id", "user_likes_count", "user_follow_count",
  "user_fans_count", "user_works_count", "user_gender", "user_age", "user_ip_location", "user_is_private",
  "back_btn", "off_video"
];

logger.info(TAG, "======= 选择器匹配测试 =======");
var ok = 0, fail = 0;
for (var a = 0; a < allActions.length; a++) {
  var name = allActions[a];
  var sel = selectorLoader.get(name);
  if (!sel) continue;
  var el = uiOperator.findElement(name, 500);
  if (el) {
    ok++;
    var txt = ""; try { txt = (el.text() || el.desc() || "").substring(0, 25); } catch (e2) {}
    logger.info(TAG, "  [OK] " + name + " '" + txt + "'");
  } else {
    fail++;
    logger.info(TAG, "  [NO] " + name);
  }
}
logger.info(TAG, "匹配: " + ok + " / 未匹配: " + fail);

// UI 摘要
logger.info(TAG, "======= 页面控件 =======");
var tvs = className("android.widget.TextView").find();
var btns = className("android.widget.Button").find();
logger.info(TAG, "TextView: " + tvs.length + "  Button: " + btns.length);

for (var i = 0; i < Math.min(tvs.length, 25); i++) {
  try {
    var b = tvs[i].bounds();
    if (!b || b.left < 0) continue;
    var txt = (tvs[i].text() || "").substring(0, 40);
    var dsc = (tvs[i].desc() || "").substring(0, 40);
    if (txt || dsc) logger.info(TAG, "  TV '" + txt + "' desc='" + dsc + "'");
  } catch (e) {}
}
for (var j = 0; j < Math.min(btns.length, 10); j++) {
  try {
    var bb = btns[j].bounds();
    if (!bb || bb.left < 0) continue;
    logger.info(TAG, "  BTN '" + (btns[j].text()||"").substring(0,30) + "' desc='" + (btns[j].desc()||"").substring(0,30) + "'");
  } catch (e) {}
}

// RV
var rvs = className("androidx.recyclerview.widget.RecyclerView").find();
if (rvs.length === 0) rvs = className("android.support.v7.widget.RecyclerView").find();
logger.info(TAG, "RecyclerView: " + rvs.length);
for (var r = 0; r < rvs.length; r++) {
  var rb = rvs[r].bounds();
  if (rb) {
    logger.info(TAG, "  RV#" + r + " children=" + rvs[r].children().length + " bounds=(" + rb.left+","+rb.top+","+rb.right+","+rb.bottom+") h=" + rb.height());
  }
}

logger.info(TAG, "======= 完成 =======");
