/**
 * 贝塞尔曲线计算 — 用于生成拟人滑动轨迹
 */

function factorial(n) {
  var result = 1;
  for (var i = 2; i <= n; i++) result *= i;
  return result;
}

// 设备业务函数：处理 bernstein 对应的抖音自动化动作、状态或安全边界。
function bernstein(t, i, n) {
  return (
    (factorial(n) / (factorial(i) * factorial(n - i))) *
    Math.pow(t, i) *
    Math.pow(1 - t, n - i)
  );
}

/**
 * 计算贝塞尔曲线上的点
 * @param {Array} controlPoints - 控制点数组 [{x, y}, ...]
 * @param {number} t - 参数 (0-1)
 * @returns {{x: number, y: number}}
 */
function bezierPoint(controlPoints, t) {
  var n = controlPoints.length - 1;
  var x = 0, y = 0;
  for (var i = 0; i <= n; i++) {
    var b = bernstein(t, i, n);
    x += controlPoints[i].x * b;
    y += controlPoints[i].y * b;
  }
  return { x: Math.round(x), y: Math.round(y) };
}

/**
 * 生成拟人滑动轨迹
 * @param {number} startX - 起点 X
 * @param {number} startY - 起点 Y
 * @param {number} endX - 终点 X
 * @param {number} endY - 终点 Y
 * @param {number} steps - 轨迹点数 (默认 10-20 之间的随机值)
 * @returns {Array} 轨迹点数组 [{x, y, duration}, ...]
 */
function generateSwipePath(startX, startY, endX, endY, steps) {
  steps = steps || (Math.floor(Math.random() * 11) + 10); // 10-20

  // 生成 2 个随机中间控制点，模拟手指不走直线
  var midX1 = startX + (endX - startX) * 0.3 + (Math.random() - 0.5) * 50;
  var midY1 = startY + (endY - startY) * 0.3 + (Math.random() - 0.5) * 50;
  var midX2 = startX + (endX - startX) * 0.7 + (Math.random() - 0.5) * 50;
  var midY2 = startY + (endY - startY) * 0.7 + (Math.random() - 0.5) * 50;

  var controlPoints = [
    { x: startX, y: startY },
    { x: midX1, y: midY1 },
    { x: midX2, y: midY2 },
    { x: endX, y: endY },
  ];

  var path = [];
  for (var i = 0; i <= steps; i++) {
    var t = i / steps;
    var point = bezierPoint(controlPoints, t);
    // 变速：中间快两头慢
    var duration = Math.round(10 + 20 * Math.sin(t * Math.PI));
    path.push({ x: point.x, y: point.y, duration: duration });
  }
  return path;
}

module.exports = {
  generateSwipePath: generateSwipePath,
  bezierPoint: bezierPoint,
};
