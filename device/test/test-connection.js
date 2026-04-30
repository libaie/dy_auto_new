// device/test-connection.js
// AutoJS6 连接测试脚本 - 自包含，无 require 依赖

function log(level, msg) {
    var ts = new Date().toLocaleTimeString();
    console.log("[" + ts + "] [" + level + "] " + msg);
}

log("INFO", "=== 设备连接测试开始 ===");

// 1. 设备基本信息
log("INFO", "--- 1. 设备信息 ---");
log("INFO", "设备型号: " + device.model);
log("INFO", "设备品牌: " + device.brand);
log("INFO", "系统版本: " + device.release);
log("INFO", "分辨率: " + device.width + " x " + device.height);
log("INFO", "设备序列号: " + device.serial);

// 2. 屏幕状态
log("INFO", "--- 2. 屏幕状态 ---");
log("INFO", "屏幕是否亮: " + device.isScreenOn());
try {
    log("INFO", "当前Activity: " + currentActivity());
} catch (e) {
    log("WARN", "获取Activity失败: " + e.message);
}
try {
    log("INFO", "当前包名: " + currentPackage());
} catch (e) {
    log("WARN", "获取包名失败: " + e.message);
}

// 3. UI 控件树测试
log("INFO", "--- 3. UI 控件树测试 ---");
try {
    var root = className("android.widget.FrameLayout").findOne(3000);
    if (root) {
        log("INFO", "UI 控件树根节点找到: " + root.className());
        var clickables = clickable(true).find();
        log("INFO", "可点击控件数量: " + clickables.length);
        for (var i = 0; i < Math.min(clickables.length, 10); i++) {
            var c = clickables[i];
            log("INFO", "  [" + i + "] " + c.className() + " text=" + c.text() + " desc=" + c.desc());
        }
    } else {
        log("WARN", "未找到根节点，可能无障碍服务未开启");
    }
} catch (e) {
    log("ERROR", "UI控件树获取失败: " + e.message);
}

// 4. 抖音检测
log("INFO", "--- 4. 抖音检测 ---");
try {
    var pkg = "com.ss.android.ugc.aweme";
    var pm = context.getPackageManager();
    var info = pm.getPackageInfo(pkg, 0);
    log("INFO", "抖音已安装: " + pkg + " version=" + info.versionName);
} catch (e) {
    log("WARN", "抖音未安装或获取失败: " + e.message);
}

// 5. 屏幕文字采样
log("INFO", "--- 5. 屏幕文字采样 ---");
try {
    var textNodes = textMatches(".+").find();
    log("INFO", "屏幕文字控件数量: " + textNodes.length);
    for (var i = 0; i < Math.min(textNodes.length, 15); i++) {
        log("INFO", "  [" + i + "] \"" + textNodes[i].text() + "\"");
    }
} catch (e) {
    log("ERROR", "文字采样失败: " + e.message);
}

log("INFO", "=== 设备连接测试完成 ===");
