// device/spike/01-test-capture.js
// Spike Task 1: 截图权限测试 + 页面截图采集
// 目标: 验证截图权限，采集 5 个目标页面的全屏截图
//
// 使用方法:
//   1. 在 AutoJS6 VSCode 中运行此脚本
//   2. 脚本会自动导航到各个页面并截图
//   3. 截图保存到 /sdcard/dy_auto/spike/

var SPIKE_DIR = "/sdcard/dy_auto/spike/";
var TEMPLATE_DIR = SPIKE_DIR + "templates/";

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

function ensureDir(path) {
    if (!files.exists(path)) {
        files.createWithDirs(path);
        log("INFO", "创建目录: " + path);
    }
}

function capturePage(name) {
    sleep(1500); // 等待页面稳定
    var img = images.captureScreen();
    if (!img) {
        log("ERROR", "截图失败: " + name);
        return null;
    }
    var path = SPIKE_DIR + name + ".png";
    images.save(img, path);
    log("INFO", "截图已保存: " + path + " (" + img.getWidth() + "x" + img.getHeight() + ")");
    return img;
}

// ============================================================
// 主流程
// ============================================================

log("INFO", "=== Spike Task 1: 截图采集 ===");

// 创建目录
ensureDir(SPIKE_DIR);
ensureDir(TEMPLATE_DIR);

// 1. 测试截图权限
log("INFO", "--- 测试截图权限 ---");
if (!images.requestScreenCapture()) {
    log("ERROR", "截图权限被拒绝，请在手机上授权");
    exit();
}
sleep(2000);

// 测试截图
var testImg = images.captureScreen();
if (!testImg) {
    log("ERROR", "截图返回 null，权限可能未正确授予");
    exit();
}
log("INFO", "截图权限OK: " + testImg.getWidth() + "x" + testImg.getHeight());
testImg.recycle();

// 确保在抖音
log("INFO", "--- 启动抖音 ---");
if (currentPackage() !== "com.ss.android.ugc.aweme") {
    app.launchApp("抖音");
    sleep(5000);
}
log("INFO", "当前包名: " + currentPackage());

// ============================================================
// 页面 1: 首页推荐
// ============================================================
log("INFO", "=== 页面 1/5: 首页推荐 ===");
// 先回到首页
back();
sleep(1000);
back();
sleep(1000);
// 点击底部"首页"tab
var homeTab = text("首页").findOnce() || desc("首页").findOnce();
if (homeTab) {
    homeTab.click();
    sleep(2000);
}
capturePage("page_home");

// ============================================================
// 页面 2: 搜索页
// ============================================================
log("INFO", "=== 页面 2/5: 搜索页 ===");
var searchBtn = text("搜索").findOnce() || desc("搜索").findOnce();
if (searchBtn) {
    searchBtn.click();
    sleep(2000);
    capturePage("page_search");
} else {
    log("WARN", "未找到搜索按钮，尝试点击搜索图标");
    // 尝试通过 id 找
    var searchIcon = desc("搜索").findOnce();
    if (searchIcon) {
        searchIcon.click();
        sleep(2000);
        capturePage("page_search");
    } else {
        log("ERROR", "无法进入搜索页");
    }
}

// ============================================================
// 页面 3: 搜索结果（搜索"美食"）
// ============================================================
log("INFO", "=== 页面 3/5: 搜索结果 ===");
var editBox = className("EditText").findOnce();
if (editBox) {
    editBox.click();
    sleep(300);
    editBox.setText("");
    sleep(200);
    setClip("美食");
    sleep(200);
    paste();
    sleep(1000);
    log("INFO", "输入文字: \"" + editBox.text() + "\"");

    // 点击搜索/联想词
    var rv = id("recycler_view").findOne(3000);
    if (rv) {
        var ch = rv.children();
        for (var i = 0; i < ch.length; i++) {
            var t = ch[i].findOne(text("美食"));
            if (t) {
                t.parent().parent().click();
                break;
            }
        }
    }
    sleep(3000);

    // 点击视频 tab（通过选择器系统）
    log("INFO", "视频 tab 需通过选择器配置");

    capturePage("page_search_result");
} else {
    log("ERROR", "未找到输入框");
}

// ============================================================
// 页面 4: 排序弹窗
// ============================================================
log("INFO", "=== 页面 4/5: 排序弹窗 ===");
try {
    var sortBtn = id("ivu").findOne(3000);
    if (sortBtn) {
        sortBtn.click();
        sleep(1500);
        capturePage("page_sort_popup");
    } else {
        log("WARN", "未找到排序按钮 (id=ivu)");
        // 尝试其他方式找排序按钮
        var sortText = text("排序").findOnce() || desc("排序").findOnce();
        if (sortText) {
            sortText.click();
            sleep(1500);
            capturePage("page_sort_popup");
        } else {
            log("ERROR", "无法打开排序弹窗");
        }
    }
} catch (e) {
    log("ERROR", "排序弹窗: " + e.message);
}

// ============================================================
// 页面 5: 视频详情（点击搜索结果中的第一个视频）
// ============================================================
log("INFO", "=== 页面 5/5: 视频详情 ===");
// 先关闭弹窗（如果还开着）
back();
sleep(1000);

// 点击搜索结果中的第一个视频
try {
    var firstVideo = className("android.widget.FrameLayout").clickable(true).findOne(3000);
    if (firstVideo) {
        firstVideo.click();
        sleep(3000);
        capturePage("page_video_detail");
    } else {
        log("WARN", "未找到可点击的视频，尝试直接点击屏幕中央");
        click(device.width / 2, device.height / 2);
        sleep(3000);
        capturePage("page_video_detail");
    }
} catch (e) {
    log("ERROR", "视频详情: " + e.message);
}

// ============================================================
// 完成
// ============================================================
log("INFO", "=== 截图采集完成 ===");
log("INFO", "截图保存在: " + SPIKE_DIR);
log("INFO", "下一步: 从截图中裁剪模板元素，保存到 " + TEMPLATE_DIR);
log("INFO", "");
log("INFO", "需要裁剪的模板:");
log("INFO", "  1. like_off.png     - 视频详情页的点赞按钮(未点赞状态)");
log("INFO", "  2. follow_btn.png   - 视频详情页的关注按钮");
log("INFO", "  3. search_input.png - 搜索页的搜索输入框");
log("INFO", "  4. sort_latest.png  - 排序弹窗中的'最新发布'选项");
log("INFO", "  5. tab_video.png    - 搜索结果页的'视频' tab");
log("INFO", "");
log("INFO", "裁剪方法: 在手机上用图片编辑器裁剪，或用下一个脚本自动裁剪");
