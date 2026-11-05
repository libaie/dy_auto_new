var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "UPDATE";
var MANIFEST = "device-update.json";
var ENTRY_MARKER = "// dy-auto-release ";
var MAX_BYTES = 50 * 1024 * 1024;
var MAX_FILES = 1000;
var EXCLUDED = { test: true, tests: true, spike: true, node_modules: true, cache: true, logs: true, templates: true, update: true };

function own(value, key) { return Object.prototype.hasOwnProperty.call(value, key); }

function ensureDirPath(dir) {
  var file = new java.io.File(String(dir));
  if (!file.exists()) file.mkdirs();
  if (!file.exists() || !file.isDirectory()) throw new Error("Cannot create update directory: " + dir);
}

function parentDir(filename) {
  var value = String(filename);
  return value.substring(0, value.lastIndexOf("/"));
}

function safePath(name) {
  if (typeof name !== "string" || !name || name.length > 240) return false;
  var parts = name.split("/");
  for (var i = 0; i < parts.length; i++) {
    if (!/^[A-Za-z0-9_-][A-Za-z0-9_.-]*$/.test(parts[i]) || own(EXCLUDED, parts[i])) return false;
  }
  return true;
}

function inside(root, relative) {
  var prefix = String(new java.io.File(root).getCanonicalPath()) + java.io.File.separator;
  var result = String(new java.io.File(root, relative).getCanonicalPath());
  if (result.indexOf(prefix) !== 0) throw new Error("Unsafe update path: " + relative);
  return result;
}

function hashFile(filename) {
  var input = new java.io.FileInputStream(String(filename));
  var digest = java.security.MessageDigest.getInstance("SHA-256");
  var buffer = java.lang.reflect.Array.newInstance(java.lang.Byte.TYPE, 8192);
  try {
    var count;
    while ((count = input.read(buffer)) > 0) digest.update(buffer, 0, count);
  } finally { input.close(); }
  var bytes = digest.digest(), value = "";
  for (var i = 0; i < bytes.length; i++) {
    var hex = (bytes[i] & 255).toString(16);
    value += hex.length === 1 ? "0" + hex : hex;
  }
  return value;
}

function extractZip(zipPath, destDir) {
  // Check all entry names before writing. Java streams materialize only regular
  // files, never symlinks or plugin-specific path aliases.
  var archive = new java.util.zip.ZipFile(String(zipPath));
  var entries = [], seen = {}, total = 0;
  try {
    var iterator = archive.entries();
    while (iterator.hasMoreElements()) {
      var entry = iterator.nextElement();
      var raw = String(entry.getName());
      var name = entry.isDirectory() ? raw.substring(0, raw.length - 1) : raw;
      var size = Number(entry.getSize());
      if (!safePath(name) || own(seen, name)) throw new Error("Unsafe or duplicate ZIP path: " + raw);
      if (Number(entry.getMethod()) !== 0 && Number(entry.getMethod()) !== 8) throw new Error("Unsupported ZIP compression: " + raw);
      if (size < 0 || !isFinite(size)) throw new Error("Unknown ZIP entry size: " + raw);
      seen[name] = true;
      total += size;
      if (total > MAX_BYTES || entries.length >= MAX_FILES) throw new Error("Update package is too large");
      entries.push({ entry: entry, name: name, size: size });
    }
    ensureDirPath(destDir);
    var buffer = java.lang.reflect.Array.newInstance(java.lang.Byte.TYPE, 8192);
    for (var i = 0; i < entries.length; i++) {
      var item = entries[i], target = inside(destDir, item.name);
      if (item.entry.isDirectory()) { ensureDirPath(target); continue; }
      ensureDirPath(parentDir(target));
      var input = archive.getInputStream(item.entry), output = null;
      try {
        output = new java.io.FileOutputStream(target);
        var count, written = 0;
        while ((count = input.read(buffer)) > 0) {
          written += count;
          if (written > item.size) throw new Error("ZIP size mismatch: " + item.name);
          output.write(buffer, 0, count);
        }
        if (written !== item.size) throw new Error("Truncated ZIP entry: " + item.name);
      } finally {
        try { if (output) output.close(); } finally { input.close(); }
      }
    }
  } finally { archive.close(); }
}

function decodeLiteral(raw) {
  return raw.replace(/\\(?:x([0-9a-fA-F]{2})|u([0-9a-fA-F]{4})|(\r?\n)|([^\r\n]))/g, function (_, hex, unicode, newline, char) {
    if (hex || unicode) return String.fromCharCode(parseInt(hex || unicode, 16));
    if (newline) return "";
    var escapes = { n: "\n", r: "\r", t: "\t", b: "\b", f: "\f", v: "\v", "0": "\0" };
    return own(escapes, char) ? escapes[char] : char;
  });
}

function staticRequires(source) {
  // Tokenize literal require calls; AutoJS XML layouts are not Node syntax.
  var tokens = [], i = 0, previous = "";
  var regexBefore = ["", "(", "[", "{", ",", ";", ":", "=", "!", "?", "&", "|", "+", "-", "*", "%", "^", "~", "return", "throw", "case"];
  while (i < source.length) {
    var char = source.charAt(i), start, end;
    if (/\s/.test(char)) { i++; continue; }
    if (source.substr(i, 2) === "//") {
      end = source.indexOf("\n", i + 2); i = end < 0 ? source.length : end + 1; continue;
    }
    if (source.substr(i, 2) === "/*") {
      end = source.indexOf("*/", i + 2); i = end < 0 ? source.length : end + 2; continue;
    }
    if (char === '"' || char === "'") {
      var quote = char; start = ++i;
      while (i < source.length && source.charAt(i) !== quote) i += source.charAt(i) === "\\" ? 2 : 1;
      tokens.push({ type: "string", value: decodeLiteral(source.substring(start, i)) });
      previous = "string"; i++; continue;
    }
    if (char === "/" && regexBefore.indexOf(previous) !== -1) {
      i++;
      var inClass = false;
      while (i < source.length) {
        char = source.charAt(i);
        if (char === "\\") { i += 2; continue; }
        if (char === "[") inClass = true;
        else if (char === "]") inClass = false;
        else if (char === "/" && !inClass) { i++; break; }
        i++;
      }
      while (i < source.length && /[A-Za-z]/.test(source.charAt(i))) i++;
      tokens.push({ type: "regex", value: "regex" }); previous = "regex"; continue;
    }
    if (/[A-Za-z_$]/.test(char)) {
      start = i++;
      while (i < source.length && /[A-Za-z0-9_$]/.test(source.charAt(i))) i++;
      previous = source.substring(start, i);
      tokens.push({ type: "name", value: previous }); continue;
    }
    tokens.push({ type: "punct", value: char }); previous = char; i++;
  }
  var result = [];
  for (i = 0; i + 3 < tokens.length; i++) {
    if (tokens[i].type === "name" && tokens[i].value === "require" && (i === 0 || tokens[i - 1].value !== ".") && tokens[i + 1].value === "(" && tokens[i + 2].type === "string" && tokens[i + 3].value === ")") result.push(tokens[i + 2].value);
  }
  return result;
}

function hasDependency(filename, dependency, available) {
  var parts = filename.split("/"); parts.pop();
  var requested = dependency.split("/");
  for (var i = 0; i < requested.length; i++) {
    var part = requested[i];
    if (!part || part === ".") continue;
    if (part === "..") { if (!parts.length) return false; parts.pop(); }
    else parts.push(part);
  }
  var target = parts.join("/");
  return own(available, target) || own(available, target + ".js") || own(available, target + ".json") || own(available, target + "/index.js");
}

function collectFiles(root, relative, result) {
  var dir = relative ? inside(root, relative) : root;
  var names = files.listDir(dir);
  if (!names) throw new Error("Cannot list update directory: " + dir);
  for (var i = 0; i < names.length; i++) {
    var name = relative ? relative + "/" + names[i] : String(names[i]);
    if (!safePath(name)) throw new Error("Unsafe extracted path: " + name);
    var filename = inside(root, name);
    if (files.isDir(filename)) collectFiles(root, name, result);
    else result[name] = filename;
  }
}

function validatePackage(root) {
  var available = {};
  collectFiles(root, "", available);
  if (!own(available, MANIFEST)) throw new Error("Missing " + MANIFEST + "; rebuild with tools/pack_device.py");
  var manifest = JSON.parse(files.read(available[MANIFEST]));
  if (!manifest || manifest.format !== 1 || manifest.entry !== "main.js" || !manifest.files || typeof manifest.files !== "object" || Array.isArray(manifest.files)) throw new Error("Invalid update manifest");
  var records = manifest.files, name, count = 0, total = 0;
  for (name in available) {
    if (!own(available, name) || name === MANIFEST) continue;
    if (!own(records, name)) throw new Error("Unlisted update file: " + name);
  }
  for (name in records) {
    if (!own(records, name)) continue;
    var record = records[name];
    if (!safePath(name) || name === MANIFEST || !own(available, name)) throw new Error("Missing or unsafe update file: " + name);
    if (!record || typeof record.size !== "number" || !isFinite(record.size) || record.size < 0 || Math.floor(record.size) !== record.size || !/^[0-9a-f]{64}$/.test(record.sha256 || "")) throw new Error("Invalid file metadata: " + name);
    total += record.size; count++;
    if (total > MAX_BYTES || count >= MAX_FILES) throw new Error("Update manifest is too large");
    if (Number(new java.io.File(available[name]).length()) !== record.size || hashFile(available[name]) !== record.sha256) throw new Error("Update checksum mismatch: " + name);
  }
  var required = ["main.js", "config.js", "project.json"];
  for (var i = 0; i < required.length; i++) if (!own(records, required[i])) throw new Error("Missing root file: " + required[i]);
  if (JSON.parse(files.read(available["project.json"])).main !== "main.js") throw new Error("Project entry must be main.js");
  for (name in records) {
    if (!own(records, name) || !/\.js$/.test(name)) continue;
    var dependencies = staticRequires(String(files.read(available[name])));
    for (var j = 0; j < dependencies.length; j++) {
      var dependency = dependencies[j];
      if (dependency.charAt(0) === "/" || dependency.indexOf("\\") !== -1 || (dependency.charAt(0) === "." && !hasDependency(name, dependency, records))) throw new Error("Missing or outside local require in " + name + ": " + dependency);
    }
  }
  return manifest;
}

function atomicRename(from, to) {
  // Never remove the old target first. A same-filesystem Android rename either
  // replaces the entry atomically or leaves the previous entry usable.
  if (!new java.io.File(String(from)).renameTo(new java.io.File(String(to)))) throw new Error("Cannot atomically activate: " + to);
}

function writeChecked(filename, value) {
  files.write(filename, value);
  if (!files.exists(filename) || String(files.read(filename)) !== value) throw new Error("Update write failed: " + filename);
}

var updateChecker = {
  _getBaseDir: function () {
    try { return String(context.getFilesDir().getAbsolutePath()); } catch (e) {}
    try { return String(context.getExternalFilesDir(null).getAbsolutePath()); } catch (e2) {}
    return files.cwd();
  },

  _projectDir: function () {
    var root = typeof global !== "undefined" && global.__dyAutoProjectRoot ? String(global.__dyAutoProjectRoot) : files.cwd();
    return String(new java.io.File(root).getCanonicalPath());
  },

  _versionFile: function () { return this._getBaseDir() + "/update/local_version.txt"; },

  getLocalVersion: function () {
    try {
      var entry = String(files.read(this._projectDir() + "/main.js")).split("\n")[0];
      if (entry.indexOf(ENTRY_MARKER) === 0) {
        var active = JSON.parse(entry.substring(ENTRY_MARKER.length));
        if (typeof active.version === "string" && /^\.dy_auto_releases\/[A-Za-z0-9_-]+\/main\.js$/.test(active.entry)) return active.version;
      }
    } catch (e) {}
    try { if (files.exists(this._versionFile())) return String(files.read(this._versionFile())).trim(); } catch (e2) {}
    return "0.0.0";
  },

  saveLocalVersion: function (version) {
    // Keep the legacy sidecar for existing tooling. The atomically switched
    // entry is authoritative, so a sidecar failure cannot split code/version.
    var target = this._versionFile(), temporary = target + ".pending";
    try {
      ensureDirPath(parentDir(target));
      writeChecked(temporary, String(version));
      atomicRename(temporary, target);
      return true;
    } catch (e) { logger.warn(TAG, "Failed to save legacy version: " + e.message); return false; }
    finally { try { if (files.exists(temporary)) files.remove(temporary); } catch (ignore) {} }
  },

  checkAndUpdate: function () {
    if (this._checking) return false;
    this._checking = true;
    var tempDir = null, stageDir = null, releaseDir = null, entryTemp = null, backupTemp = null, activated = false;
    try {
      var localVersion = this.getLocalVersion(), serverVersion = apiClient.getScriptVersion();
      if (typeof serverVersion !== "string" || !/^[A-Za-z0-9_.-]{1,80}$/.test(serverVersion)) return false;
      if (localVersion === serverVersion) return false;
      if (!apiClient.downloadScript()) return false;
      var zipPath = this._getBaseDir() + "/update/device-script.zip";
      if (!files.exists(zipPath)) throw new Error("Downloaded ZIP is missing");
      var id = Date.now().toString(36) + "-" + Math.random().toString(36).substring(2, 10);
      tempDir = this._getBaseDir() + "/update/unpack-" + id;
      extractZip(zipPath, tempDir);
      validatePackage(tempDir);

      var projectDir = this._projectDir(), releaseRoot = projectDir + "/.dy_auto_releases";
      ensureDirPath(releaseRoot);
      stageDir = releaseRoot + "/" + id + "-staging";
      releaseDir = releaseRoot + "/" + id;
      if (files.exists(stageDir) || files.exists(releaseDir)) throw new Error("Update staging directory already exists");
      ensureDirPath(stageDir);
      this._copyDir(tempDir, stageDir);
      validatePackage(stageDir);
      atomicRename(stageDir, releaseDir);
      stageDir = null;

      var entryPath = projectDir + "/main.js";
      var relativeEntry = ".dy_auto_releases/" + id + "/main.js";
      var bootstrap = ENTRY_MARKER + JSON.stringify({ version: serverVersion, entry: relativeEntry }) + "\n" +
        "global.__dyAutoProjectRoot = " + JSON.stringify(projectDir) + ";\n" +
        "require(" + JSON.stringify("./" + relativeEntry) + ");\n";
      // A same-directory backup preserves the old entry's relative requires.
      // Both old root modules and previous release directories remain untouched.
      backupTemp = projectDir + "/.dy_auto_previous_main.pending-" + id;
      writeChecked(backupTemp, String(files.read(entryPath)));
      atomicRename(backupTemp, projectDir + "/.dy_auto_previous_main.js");
      backupTemp = null;
      entryTemp = projectDir + "/.dy_auto_main.pending-" + id;
      writeChecked(entryTemp, bootstrap);
      atomicRename(entryTemp, entryPath);
      activated = true;
      entryTemp = null;
      this.saveLocalVersion(serverVersion);
      logger.info(TAG, "Update complete! New version: " + serverVersion + "; restart to use it");
      return true;
    } catch (e) {
      logger.error(TAG, "Update failed; previous runnable entry retained: " + e.message);
      return activated;
    } finally {
      try { if (tempDir && files.exists(tempDir)) files.removeDir(tempDir); } catch (ignore1) {}
      try { if (stageDir && files.exists(stageDir)) files.removeDir(stageDir); } catch (ignore2) {}
      try { if (!activated && releaseDir && files.exists(releaseDir)) files.removeDir(releaseDir); } catch (ignore3) {}
      try { if (entryTemp && files.exists(entryTemp)) files.remove(entryTemp); } catch (ignore4) {}
      try { if (backupTemp && files.exists(backupTemp)) files.remove(backupTemp); } catch (ignore5) {}
      this._checking = false;
    }
  },

  _copyDir: function (src, dst) {
    var items = files.listDir(src);
    if (!items) throw new Error("Cannot list update source: " + src);
    for (var i = 0; i < items.length; i++) {
      var srcFile = src + "/" + items[i], dstFile = dst + "/" + items[i];
      if (files.isDir(srcFile)) {
        ensureDirPath(dstFile);
        this._copyDir(srcFile, dstFile);
      } else {
        ensureDirPath(parentDir(dstFile));
        if (files.copy(srcFile, dstFile) === false || !files.exists(dstFile)) throw new Error("Update copy failed: " + items[i]);
      }
    }
  },
};

module.exports = updateChecker;
