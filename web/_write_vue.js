var fs=require("fs");
var path="d:/devWorkspace/jsProjects/dy_auto/web/src/views/DMSequenceManagePage.vue";
var src=fs.readFileSync(path,"utf8");
console.log("read",src.length,"bytes");
