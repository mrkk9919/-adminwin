// ===== My QR 动态二维码补丁 =====
// 替换硬编码的 yukheang-soeu-khqr.jpg 为根据用户真实账号动态生成的 QR 码
(function () {
  var QR_LIB_URL = "https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js";
  var PATCHED_FLAG = "myqr_patched";
  var observer = null;
  var qrLibLoaded = false;

  function loadQRLib(callback) {
    if (window.QRCode) { qrLibLoaded = true; callback(); return; }
    var s = document.createElement("script");
    s.src = QR_LIB_URL;
    s.onload = function () { qrLibLoaded = true; callback(); };
    s.onerror = function () {
      // fallback: use qrcode-generator from another CDN
      var s2 = document.createElement("script");
      s2.src = "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js";
      s2.onload = function () { qrLibLoaded = true; callback(); };
      s2.onerror = callback;
      document.head.appendChild(s2);
    };
    document.head.appendChild(s);
  }

  function extractPageData() {
    var data = { name: "", khr: "", usd: "", amount: "", currency: "USD" };
    // Merchant name - look for the h1 after "Merchant" label
    var merchantLabels = document.querySelectorAll("p");
    for (var i = 0; i < merchantLabels.length; i++) {
      if (merchantLabels[i].textContent.trim() === "Merchant") {
        var h1 = merchantLabels[i].parentNode.querySelector("h1");
        if (h1) data.name = h1.textContent.trim();
        break;
      }
    }
    // Account numbers - look for "Receiving KHR to" / "Receiving USD to"
    var allP = document.querySelectorAll("p");
    for (var j = 0; j < allP.length; j++) {
      var txt = allP[j].textContent.trim();
      if (txt === "Receiving KHR to") {
        var nextP = allP[j].parentNode.querySelectorAll("p")[1];
        if (nextP) data.khr = nextP.textContent.trim().replace(/\s+$/, "");
      }
      if (txt === "Receiving USD to") {
        var nextP2 = allP[j].parentNode.querySelectorAll("p")[1];
        if (nextP2) data.usd = nextP2.textContent.trim().replace(/\s+$/, "");
      }
    }
    // Amount & currency from the "Enter Amount" button
    var buttons = document.querySelectorAll("button");
    for (var k = 0; k < buttons.length; k++) {
      var btnText = buttons[k].textContent.trim();
      if (btnText.indexOf("· USD") > -1 || btnText.indexOf("· KHR") > -1) {
        var parts = btnText.split("·");
        if (parts.length === 2) {
          data.amount = parts[0].trim().replace(/[^0-9.,]/g, "");
          data.currency = parts[1].trim();
        }
      }
    }
    return data;
  }

  function generateQRValue(data) {
    var acct = data.currency === "KHR" ? data.khr : data.usd;
    if (!acct) acct = data.usd || data.khr || "";
    var payload = {
      bank: "WING",
      account: acct,
      name: data.name || "Wing Bank User",
      currency: data.currency || "USD",
      type: "bakong_qr",
      qr_type: "user"
    };
    if (data.amount) payload.amount = data.amount;
    return JSON.stringify(payload);
  }

  function patchQRImage() {
    // Find the hardcoded QR image
    var imgs = document.querySelectorAll("img[src*='yukheang-soeu-khqr']");
    if (imgs.length === 0) return false;

    var img = imgs[0];
    if (img.getAttribute(PATCHED_FLAG)) return true;

    var data = extractPageData();
    var qrValue = generateQRValue(data);

    // Create container for QR
    var container = img.parentNode;
    var qrDiv = document.createElement("div");
    qrDiv.id = "dynamic-qr-container";
    qrDiv.style.width = "100%";
    qrDiv.style.height = "100%";
    qrDiv.style.display = "flex";
    qrDiv.style.alignItems = "center";
    qrDiv.style.justifyContent = "center";

    // Hide original image but keep it for html2canvas capture
    img.style.display = "none";
    img.setAttribute(PATCHED_FLAG, "true");
    container.appendChild(qrDiv);

    // Generate QR
    if (window.QRCode) {
      try {
        new QRCode(qrDiv, {
          text: qrValue,
          width: 220,
          height: 220,
          colorDark: "#10191d",
          colorLight: "#ffffff",
          correctLevel: QRCode.CorrectLevel.M
        });
      } catch (e) {
        // fallback: canvas-based
        generateQRCanvas(qrDiv, qrValue);
      }
    } else {
      generateQRCanvas(qrDiv, qrValue);
    }

    // Also patch html2canvas capture: when user clicks Save/Screenshot,
    // temporarily show the dynamic QR and hide original
    patchCaptureButtons(qrDiv, img);

    console.log("[MyQR Patch] QR replaced with dynamic data:", data);
    return true;
  }

  function generateQRCanvas(container, text) {
    // Simple fallback using a data URL approach - show a message
    var canvas = document.createElement("canvas");
    canvas.width = 220;
    canvas.height = 220;
    var ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, 220, 220);
    ctx.fillStyle = "#10191d";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("QR Code", 110, 100);
    ctx.fillText("(loading library...)", 110, 120);
    container.appendChild(canvas);
  }

  function patchCaptureButtons(qrDiv, originalImg) {
    // When Save/Screenshot is clicked, ensure dynamic QR is visible for html2canvas
    var allButtons = document.querySelectorAll("button");
    for (var i = 0; i < allButtons.length; i++) {
      (function (btn) {
        var txt = btn.textContent.trim();
        if (txt === "Save" || txt === "Screenshot") {
          btn.addEventListener("click", function () {
            // html2canvas captures the cardRef div. Ensure QR is visible.
            setTimeout(function () {
              // The QR div is already in the DOM and visible
              // Original img is display:none, html2canvas will skip it
            }, 50);
          }, true);
        }
      })(allButtons[i]);
    }
  }

  function startObserver() {
    if (observer) return;
    observer = new MutationObserver(function (mutations) {
      // Check if we're on the My QR page
      var hash = (location.hash || "").toLowerCase();
      var path = (location.pathname || "").toLowerCase();
      var isMyQR = hash.indexOf("my-qr") > -1 || hash.indexOf("myqr") > -1 ||
                    path.indexOf("my-qr") > -1 || path.indexOf("myqr") > -1;
      if (isMyQR) {
        var found = document.querySelector("img[src*='yukheang-soeu-khqr']");
        if (found && !found.getAttribute(PATCHED_FLAG)) {
          if (qrLibLoaded) {
            patchQRImage();
          } else {
            loadQRLib(patchQRImage);
          }
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Initialize
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserver);
  } else {
    startObserver();
  }

  // Also try immediately
  setTimeout(function () {
    var found = document.querySelector("img[src*='yukheang-soeu-khqr']");
    if (found && !found.getAttribute(PATCHED_FLAG)) {
      loadQRLib(patchQRImage);
    }
  }, 1000);

  console.log("[MyQR Patch] Runtime patch initialized");
})();
