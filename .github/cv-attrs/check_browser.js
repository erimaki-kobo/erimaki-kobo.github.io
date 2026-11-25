// Usage: node check_browser.js <base url>   (serve the site root, which has en/opencv-removed-name-lookup/)
// Expected strings were written by hand from the probe results and the runs in the installed releases, not from the page's script.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/opencv-removed-name-lookup/";
const cases = [
  ["cascade", "AttributeError: module 'cv2' has no attribute 'CascadeClassifier'", ["cv2.CascadeClassifier", "opencv-python removed it in 5.0.0.93 (last in 4.14.0.94)", "opencv-contrib-python 5.1.0.95 still has it", "pip install opencv-contrib-python", 'opencv-python<5.0.0.93', "haarcascade", "3.4.8.29 to 4.14.0.94"], []],
  ["caffe", "AttributeError: module 'cv2.dnn' has no attribute 'readNetFromCaffe'", ["cv2.dnn.readNetFromCaffe", "Removed in 5.0.0.93 (last in 4.14.0.94)", "Caffe importer has been removed", 'opencv-python<5.0.0.93'], ["Only in opencv-contrib-python"]],
  ["tf", "AttributeError: module 'cv2.dnn' has no attribute 'readNetFromTensorflow'", ["Removed in 5.1.0.95 (last in 5.0.0.93)", "TensorFlow importer has been removed"], []],
  ["xfeatures2d", "AttributeError: module 'cv2' has no attribute 'xfeatures2d'", ["Only in opencv-contrib-python", "every release read", "opencv-python never had it", "SIFT_create"], ["To keep it"]],
  ["aruco", "AttributeError: module 'cv2.aruco' has no attribute 'Dictionary_get'", ["Removed in 4.7.0.68 (last in 4.6.0.66)", "It was only ever in opencv-contrib-python", "getPredefinedDictionary", 'opencv-contrib-python<4.7.0.68', "3.4.8.29 to 4.6.0.66"], []],
  ["mosse", "AttributeError: module 'cv2' has no attribute 'TrackerMOSSE_create'", ["Removed in 4.5.1.48 (last in 4.4.0.46)", "cv2.legacy.TrackerMOSSE_create()"], []],
  ["boosting", "AttributeError: module 'cv2' has no attribute 'TrackerBoosting_create'", ["Removed in 4.5.1.48", "cv2.legacy has a name spelled the same in 5.1.0.95 (opencv-contrib-python)"], []],
  ["sift", "AttributeError: module 'cv2' has no attribute 'SIFT_create'", ["In both packages in 5.1.0.95", "opencv-python has it from 4.4.0.46", "opencv-contrib-python from 4.4.0.42", "Note:", "3.4.11.43 to 3.4.18.65"], ["Instead:"]],
  ["imshow", "AttributeError: module 'cv2' has no attribute 'imshow'", ["Every release read has it", "uninstall all of them and install one"], ["Removed in"]],
  ["member", "AttributeError: 'cv2.aruco.CharucoBoard' object has no attribute 'chessboardCorners'", ["cv2.aruco_CharucoBoard.chessboardCorners", "Removed in 4.7.0.68 (last in 4.6.0.66)", "getChessboardCorners()"], []],
  ["member-old", "AttributeError: 'cv2.aruco_Board' object has no attribute 'ids'", ["Removed in 4.7.0.68", "board.getIds()"], []],
  ["rigid", "AttributeError: module 'cv2' has no attribute 'estimateRigidTransform'", ["Removed in 4.x (not in 4.1.2.30", "last in 3.4.18.65", "estimateAffinePartial2D", "4.0.0 to 4.1.1 have no wheel"], ["To keep it"]],
  ["cv2cv2", "ImportError: Bindings generation error. Submodule name should always start with a parent module name. Parent name: cv2.cv2. Submodule name: cv2", ["import cv2.cv2", "Works up to 4.5.5.64 (and 3.4.17.63 in the 3.4 line)", "every release from 4.6.0.66 raises ImportError: Bindings generation error", "'cv2' is not a package"], []],
  ["code", "sift = cv2.xfeatures2d.SIFT_create()", ["cv2.xfeatures2d.SIFT_create", "Only in opencv-contrib-python"], []],
  ["partial", "AttributeError: partially initialized module 'cv2' has no attribute 'gapi_wip_gst_GStreamerPipeline' (most likely due to a circular import)", ["cv2.gapi_wip_gst_GStreamerPipeline", "opencv-python removed it in 5.0.0.93", "files of two OpenCV packages or versions are mixed"], []],
  ["old", "AttributeError: module 'cv2' has no attribute 'CV_LOAD_IMAGE_COLOR'", ["No release of opencv-python or opencv-contrib-python from 3.4.8.29 to 5.1.0.95 has this name", "OpenCV 2.4 names"], []],
  ["kaze", "AttributeError: module 'cv2' has no attribute 'KAZE_create'", ["Removed in 5.0.0.93 (last in 4.14.0.94)", "cv2.xfeatures2d.KAZE_create()"], []],
  ["cv2.cv2 attr", "AttributeError: module 'cv2.cv2' has no attribute 'TrackerKCF_create'", ["cv2.TrackerKCF_create", "Only in opencv-contrib-python"], []],
  ["logpolar", "AttributeError: module 'cv2' has no attribute 'logPolar'", ["Removed in 5.0.0.93", "cv2.warpPolar(src, dsize, center, maxRadius, cv2.WARP_POLAR_LOG)"], []],
  ["ml", "AttributeError: module 'cv2' has no attribute 'ml'", ["opencv-python removed it in 5.0.0.93 (last in 4.14.0.94)", "SVM_create"], []],
  ["doc", "AttributeError: module 'cv2.aruco' has no attribute 'estimatePoseBoard'", ["Removed in 5.0.0.93", "OpenCV's own text in 4.14.0", "Use Board::matchImagePoints and cv::solvePnP"], []],
  ["wrongmod", "AttributeError: module 'cv2.aruco' has no attribute 'SIFT_create'", ["Not at cv2.aruco in any release read", "cv2.SIFT_create"], []],
  ["dictvalue", "AttributeError: module 'cv2.dnn' has no attribute 'DictValue'", ["opencv-python has it from 4.6.0.66", "Note:", "cv2/typing"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.CV_READY);
    const st = await p.evaluate(() => ({ h1: document.querySelectorAll("h1").length, tables: document.querySelectorAll("table.flt").length,
      ld: JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)["@graph"].map(x => x["@type"]).join(","),
      over: document.documentElement.scrollWidth - document.documentElement.clientWidth }));
    if (st.h1 !== 1 || st.tables !== 1 || st.ld !== "TechArticle,WebApplication,Dataset,FAQPage,BreadcrumbList" || st.over > 0) { fail++; console.log("FAIL static", w, st); }
    for (const [name, q, want, not] of cases) {
      n++;
      const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
      await p.fill("#q", q); await p.click("#go");
      await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
      const t = (await p.evaluate(() => document.getElementById("res").innerText)).replace(/\s+/g, " ");
      const miss = want.filter(x => !t.includes(x)), extra = not.filter(x => t.includes(x));
      const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (miss.length || extra.length || over > 0) { fail++; console.log("FAIL", w, name, { miss, extra, over }, "|", t.slice(0, 600)); }
    }
    for (const ex of await p.$$("[data-ex]")) {
      const prev = await p.evaluate(() => document.getElementById("res").getAttribute("data-done"));
      await ex.click();
      await p.waitForFunction(x => document.getElementById("res").getAttribute("data-done") !== x, prev);
      if (!/Removed in|removed it in|Only in opencv-contrib-python|In both packages/.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("cv2.aruco.Dictionary_get"), { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("getPredefinedDictionary")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
