// 笑脸报到 —— 前端交互逻辑
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  var currentSchool = "";
  var selGrade = $("sel-grade");
  var selClass = $("sel-class");
  var btnToggle = $("btn-toggle");
  var btnExport = $("btn-export");
  var btnCamera = $("btn-camera");
  var btnClear = $("btn-clear");
  var statusBadge = $("status-badge");
  var resultsList = $("results-list");
  var modal = $("camera-modal");
  var cameraUrl = $("camera-url");
  var cameraMsg = $("camera-msg");

  var active = false;
  var lastResultCount = 0;

  // ===== 时钟 =====
  function tick() {
    var d = new Date();
    var p = function (n) { return n < 10 ? "0" + n : n; };
    $("clock").textContent = p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }
  setInterval(tick, 1000);
  tick();

  // ===== 请求封装 =====
  function api(path, options) {
    return fetch(path, options).then(function (r) {
      return r.json().catch(function () { return {}; });
    });
  }

  // ===== 学校自动识别 + 年级/班级联动 =====
  function loadSchools() {
    api("/api/schools").then(function (list) {
      list = list || [];
      if (list.length) {
        currentSchool = list[0];
        $("school-name").textContent = currentSchool;
        loadGrades();
      } else {
        $("school-name").textContent = "未检测到底册";
      }
    });
  }
  function loadGrades() {
    selGrade.innerHTML = '<option value="">全部年级</option>';
    selClass.innerHTML = '<option value="">全部班级</option>';
    if (!currentSchool) return;
    api("/api/grades?school=" + encodeURIComponent(currentSchool)).then(function (list) {
      (list || []).forEach(function (g) {
        var o = document.createElement("option");
        o.value = g; o.textContent = g;
        selGrade.appendChild(o);
      });
    });
  }
  function loadClasses() {
    var grade = selGrade.value;
    selClass.innerHTML = '<option value="">全部班级</option>';
    if (!currentSchool || !grade) return;
    api("/api/classes?school=" + encodeURIComponent(currentSchool) +
        "&grade=" + encodeURIComponent(grade)).then(function (list) {
      (list || []).forEach(function (c) {
        var o = document.createElement("option");
        o.value = c; o.textContent = c;
        selClass.appendChild(o);
      });
    });
  }
  selGrade.addEventListener("change", loadClasses);

  // ===== 开始/停止 =====
  btnToggle.addEventListener("click", function () {
    if (active) {
      api("/api/stop", { method: "POST" }).then(function () {
        setActive(false);
      });
    } else {
      var school = currentSchool, grade = selGrade.value, cls = selClass.value;
      if (!school) {
        alert("未检测到底册，请先在 base_photos 目录放入照片后重启软件");
        return;
      }
      api("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ school: school, grade: grade, cls: cls })
      }).then(function () {
        setActive(true);
      });
    }
  });

  function setActive(a) {
    active = a;
    if (a) {
      btnToggle.textContent = "停止签到";
      btnToggle.classList.add("stop");
      statusBadge.textContent = "签到中";
      statusBadge.className = "badge badge-active";
    } else {
      btnToggle.textContent = "开始签到";
      btnToggle.classList.remove("stop");
      statusBadge.textContent = "未开始";
      statusBadge.className = "badge badge-idle";
    }
  }

  // ===== 结果轮询 =====
  function refreshResults() {
    api("/api/results").then(function (list) {
      list = list || [];
      renderStats(list);
      renderList(list);
    });
  }

  function renderStats(list) {
    var success = 0, repeat = 0, fail = 0;
    list.forEach(function (r) {
      if (r.result === "成功") success++;
      else if (r.result === "重复") repeat++;
      else if (r.result === "失败") fail++;
    });
    $("stat-total").textContent = list.length;
    $("stat-success").textContent = success;
    $("stat-repeat").textContent = repeat;
    $("stat-fail").textContent = fail;
  }

  function renderList(list) {
    if (!list.length) {
      resultsList.innerHTML = '<li class="empty">暂无签到记录</li>';
      return;
    }
    var html = "";
    for (var i = list.length - 1; i >= 0; i--) {
      var r = list[i];
      var cls = r.result === "成功" ? "success" : (r.result === "重复" ? "repeat" : "fail");
      var name = r.name || "（未识别）";
      html +=
        '<li class="result-item ' + cls + '">' +
          '<span class="r-dot"></span>' +
          '<span class="r-name">' + escapeHtml(name) + '</span>' +
          '<span class="r-meta">' +
            '<span class="r-time">' + escapeHtml(r.class_name || "") + " " + escapeHtml(r.time) + '</span><br>' +
            '<span class="r-sim">相似度 ' + r.similarity + '</span>' +
          '</span>' +
        '</li>';
    }
    resultsList.innerHTML = html;
    resultsList.scrollTop = 0;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  setInterval(refreshResults, 800);
  refreshResults();

  // ===== 导出 =====
  btnExport.addEventListener("click", function () {
    window.location.href = "/api/export";
  });

  // ===== 清空 =====
  btnClear.addEventListener("click", function () {
    if (!confirm("确定清空当前签到记录？")) return;
    api("/api/clear", { method: "POST" }).then(refreshResults);
  });

  // ===== 摄像头设置 =====
  btnCamera.addEventListener("click", function () {
    cameraMsg.textContent = "";
    api("/api/camera").then(function (d) {
      cameraUrl.value = d.url || "";
      modal.classList.remove("hidden");
    });
  });
  $("btn-camera-cancel").addEventListener("click", function () {
    modal.classList.add("hidden");
  });
  $("btn-camera-save").addEventListener("click", function () {
    cameraMsg.textContent = "正在连接...";
    cameraMsg.className = "camera-msg";
    api("/api/camera", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: cameraUrl.value })
    }).then(function (d) {
      if (d.ok) {
        cameraMsg.textContent = d.remote ? "已连接手机/网络流" : "已连接本地摄像头";
        cameraMsg.className = "camera-msg ok";
        setTimeout(function () { modal.classList.add("hidden"); }, 800);
      } else {
        cameraMsg.textContent = "连接失败：" + (d.error || "未知错误");
        cameraMsg.className = "camera-msg err";
      }
    });
  });

  loadSchools();
})();
