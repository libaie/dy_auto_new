// 设备更新检查模块，负责发现脚本版本变化并提示或触发更新。
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "UPDATE";

// 设备业务函数：处理 ensureDirPath 对应的抖音自动化动作、状态或安全边界。
// 入参：dir 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 ensureDirPath 对应业务流程的处理结果。
function ensureDirPath(dir) {
  if (!dir) return false;
  try {
    var f = new java.io.File(String(dir));
    if (!f.exists()) f.mkdirs();
    return f.exists() && f.isDirectory();
  } catch (e) {
    logger.warn(TAG, "Failed to create directory: " + dir + " - " + e.message);
    return false;
  }
}

// 设备业务函数：处理 parentDir 对应的抖音自动化动作、状态或安全边界。
// 入参：path 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 parentDir 对应业务流程的处理结果。
function parentDir(path) {
  var s = String(path || "");
  var idx = Math.max(s.lastIndexOf("/"), s.lastIndexOf("\\"));
  return idx > 0 ? s.substring(0, idx) : "";
}

// 设备业务函数：处理 extractZip 对应的抖音自动化动作、状态或安全边界。
// 入参：zipPath、destDir 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 extractZip 对应业务流程的处理结果。
function extractZip(zipPath, destDir) {
  ensureDirPath(destDir);

  if (typeof $zip !== "undefined") {
    if (typeof $zip.extract === "function") {
      $zip.extract(zipPath, destDir);
      return;
    }
    if (typeof $zip.unzip === "function") {
      $zip.unzip(zipPath, destDir);
      return;
    }
  }

  var root = new java.io.File(String(destDir)).getCanonicalPath() + java.io.File.separator;
  var input = new java.util.zip.ZipInputStream(
    new java.io.BufferedInputStream(new java.io.FileInputStream(String(zipPath)))
  );
  var buffer = java.lang.reflect.Array.newInstance(java.lang.Byte.TYPE, 8192);
  try {
    var entry;
    while ((entry = input.getNextEntry()) != null) {
      var outFile = new java.io.File(String(destDir), String(entry.getName()));
      var outPath = outFile.getCanonicalPath();
      if (outPath.indexOf(root) !== 0) {
        throw new Error("Unsafe zip entry: " + entry.getName());
      }
      if (entry.isDirectory()) {
        outFile.mkdirs();
      } else {
        ensureDirPath(parentDir(outPath));
        var output = new java.io.BufferedOutputStream(new java.io.FileOutputStream(outFile));
        try {
          var len;
          while ((len = input.read(buffer)) > 0) {
            output.write(buffer, 0, len);
          }
        } finally {
          output.close();
        }
      }
      input.closeEntry();
    }
  } finally {
    input.close();
  }
}

var updateChecker = {
  // 设备业务函数：处理 _getBaseDir 对应的抖音自动化动作、状态或安全边界。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 _getBaseDir 对应业务流程的处理结果。
  _getBaseDir: function () {
    try { return context.getFilesDir().getAbsolutePath(); } catch (e) {}
    try { return context.getExternalFilesDir(null).getAbsolutePath(); } catch (e2) {}
    return files.cwd();
  },

  // 设备业务函数：处理 _versionFile 对应的抖音自动化动作、状态或安全边界。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 _versionFile 对应业务流程的处理结果。
  _versionFile: function () {
    return this._getBaseDir() + "/update/local_version.txt";
  },

  // 设备业务函数：处理 getLocalVersion 对应的抖音自动化动作、状态或安全边界。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 getLocalVersion 对应业务流程的处理结果。
  getLocalVersion: function () {
    try {
      var vf = this._versionFile();
      if (files.exists(vf)) {
        return files.read(vf).trim();
      }
    } catch (e) {
      logger.warn(TAG, "Failed to read local version: " + e.message);
    }
    return "0.0.0";
  },

  // 设备业务函数：处理 saveLocalVersion 对应的抖音自动化动作、状态或安全边界。
  // 入参：version 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 saveLocalVersion 对应业务流程的处理结果。
  saveLocalVersion: function (version) {
    try {
      var vf = this._versionFile();
      ensureDirPath(parentDir(vf));
      files.write(vf, version);
    } catch (e) {
      logger.warn(TAG, "Failed to save local version: " + e.message);
    }
  },

  // 设备业务函数：处理 checkAndUpdate 对应的抖音自动化动作、状态或安全边界。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 checkAndUpdate 对应业务流程的处理结果。
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
      var baseDir = this._getBaseDir();
      var updateDir = baseDir + "/update";
      var zipPath = updateDir + "/device-script.zip";
      var tempDir = updateDir + "/temp";

      if (!files.exists(zipPath)) {
        logger.error(TAG, "Download reported success but zip not found: " + zipPath);
        return false;
      }

      ensureDirPath(tempDir);

      extractZip(zipPath, tempDir);

      // 验证关键文件存在
      var criticalFiles = ["main.js", "config.js"];
      for (var i = 0; i < criticalFiles.length; i++) {
        if (!files.exists(tempDir + "/" + criticalFiles[i])) {
          logger.error(TAG, "Update validation failed: missing " + criticalFiles[i]);
          files.removeDir(tempDir);
          files.remove(zipPath);
          return false;
        }
      }

      var projectDir = files.cwd();
      this._copyDir(tempDir, projectDir);

      this.saveLocalVersion(serverVersion);

      files.removeDir(tempDir);
      files.remove(zipPath);

      logger.info(TAG, "Update complete! New version: " + serverVersion);
      return true;
    } catch (e) {
      logger.error(TAG, "Update failed: " + e.message);
      try { files.removeDir(tempDir); } catch (ignore) {}
      return false;
    }
  },

  // 设备业务函数：处理 _copyDir 对应的抖音自动化动作、状态或安全边界。
  // 入参：src、dst 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 _copyDir 对应业务流程的处理结果。
  _copyDir: function (src, dst) {
    var items = files.listDir(src);
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var srcFile = src + "/" + item;
      var dstFile = dst + "/" + item;
      if (files.isDir(srcFile)) {
        ensureDirPath(dstFile);
        this._copyDir(srcFile, dstFile);
      } else {
        ensureDirPath(parentDir(dstFile));
        files.copy(srcFile, dstFile);
      }
    }
  },
};

module.exports = updateChecker;
