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
      // 优先用 app 私有目录（与 downloadScript 一致）
      var baseDir = null;
      try { baseDir = context.getExternalFilesDir(null).getAbsolutePath(); } catch (e) {}
      if (!baseDir) { baseDir = files.cwd(); }
      var updateDir = baseDir + "/update";
      var zipPath = updateDir + "/device-script.zip";
      var tempDir = updateDir + "/temp";

      if (!files.exists(zipPath)) {
        logger.error(TAG, "Download reported success but zip not found: " + zipPath);
        return false;
      }

      files.ensureDir(tempDir);

      $zip.extract(zipPath, tempDir);

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
