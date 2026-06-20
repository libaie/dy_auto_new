const assert = require("assert");

const storageData = {};
global.storages = {
  create: function () {
    return {
      get: function (key, fallback) {
        return Object.prototype.hasOwnProperty.call(storageData, key) ? storageData[key] : fallback;
      },
      put: function (key, value) {
        storageData[key] = value;
      },
      remove: function (key) {
        delete storageData[key];
      },
    };
  },
};

let requestedUrl = "";
global.http = {
  postJson: function (url) {
    requestedUrl = url;
    return {
      statusCode: 200,
      body: JSON.stringify({ pairing_token: "pair-token", status: "pending" }),
    };
  },
};

const pairing = require("../core/pairing");

pairing.request("192.168.166.17", "dev-test", "Mi 10", "12", "1.0.0");

assert.strictEqual(
  requestedUrl,
  "http://192.168.166.17:8001/api/device/pair-request",
  "pairing should default to the dy_auto backend port 8001 when only an IP is entered",
);
