// Usage: node check_browser.js <base url>   (serve the site root, which has en/moviepy-removed-name-lookup/)
// Expected strings were written by hand from the probe results and the runs in 1.0.3 and 2.2.1, not from the page's script.
const { chromium } = require(process.env.PW || "playwright");
const BASE = process.argv[2], PATH = "/en/moviepy-removed-name-lookup/";
const cases = [
  ["subclip", "AttributeError: 'VideoFileClip' object has no attribute 'subclip'", ["clip.subclip", "Removed in MoviePy 2.0.0", "clip.subclipped(start, end)", "same result in 1.0.3 and 2.2.1", 'pip install "moviepy<2"'], []],
  ["editor", "ModuleNotFoundError: No module named 'moviepy.editor'", ["moviepy.editor", "Removed in MoviePy 2.0.0", "from moviepy import VideoFileClip"], []],
  ["resize", "AttributeError: 'VideoFileClip' object has no attribute 'resize'", ["clip.resized(0.5)", "vfx.Resize"], []],
  ["textpos", "AttributeError: 'TextClip' object has no attribute 'set_position'", ["clip.with_position(pos)"], []],
  ["audio", "AttributeError: 'AudioFileClip' object has no attribute 'volumex'", ["clip.with_volume_scaled(factor)", "afx.MultiplyVolume"], []],
  ["rotate", "AttributeError: 'ImageClip' object has no attribute 'rotate'", ["clip.rotated(angle, expand=True)"], []],
  ["fontsize", "TypeError: TextClip.__init__() got an unexpected keyword argument 'fontsize'", ["argument fontsize", "MoviePy 2 no longer takes it", "TextClip()", "font_size="], ["write_videofile"]],
  ["verbose", "TypeError: got an unexpected keyword argument 'verbose'", ["argument verbose", "VideoClip.write_videofile()", "logger=None"], []],
  ["font", "TypeError: multiple values for argument 'font'", ["the first parameter of TextClip is font", "font_size=40"], []],
  ["code", "clip = clip.fx(vfx.fadein, 1).volumex(0.5)", ["clip.fx", "vfx.FadeIn", "clip.with_volume_scaled(factor)"], []],
  ["code2", "final = concatenate_videoclips([a, b]).set_audio(music).set_duration(10)", ["clip.with_audio(audioclip)", "clip.with_duration(t)"], []],
  ["new-on-old", "AttributeError: 'VideoFileClip' object has no attribute 'subclipped'", ["New in MoviePy 2.x", "your install is 1.x", "clip.subclip"], ["Removed in"]],
  ["fxall", "ModuleNotFoundError: No module named 'moviepy.video.fx.all'", ["from moviepy import vfx", "vfx.Resize"], []],
  ["fxmod", "from moviepy.video.fx.resize import resize", ["moviepy.video.fx.resize", "vfx.Resize"], []],
  ["fxattr", "AttributeError: module 'moviepy.video.fx.all' has no attribute 'speedx'", ["vfx.speedx", "vfx.MultiplySpeed"], []],
  ["topimport", "ImportError: cannot import name 'VideoFileClip' from 'moviepy'", ["from moviepy import VideoFileClip", "from moviepy.editor import VideoFileClip"], []],
  ["spacing", "AttributeError: 'ImageDraw' object has no attribute '_multiline_spacing'", ["2.2.1", "pip install -U moviepy"], []],
  ["both", "AttributeError: 'VideoFileClip' object has no attribute 'write_videofile'", ["Both 1.0.3 and 2.2.1 have it"], ["Removed in"]],
  ["none", "AttributeError: 'VideoFileClip' object has no attribute 'foo_bar'", ["Nothing in it matched"], []],
  ["make_frame", "AttributeError: 'VideoClip' object has no attribute 'make_frame'", ["Removed in MoviePy 2.1.0", "clip.frame_function"], []],
];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome" });
  const errs = []; let fail = 0, n = 0;
  for (const w of [1200, 375]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on("pageerror", e => errs.push(String(e)));
    p.on("response", r => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errs.push(r.status() + " " + r.url()); });
    await p.goto(BASE + PATH, { waitUntil: "load" });
    await p.waitForFunction(() => window.MP_READY);
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
      if (!/Removed in MoviePy|no longer takes it/.test(await p.evaluate(() => document.getElementById("res").innerText))) { fail++; console.log("FAIL example", w); }
    }
    await p.close();
  }
  const p = await b.newPage();
  await p.goto(BASE + PATH + "?q=" + encodeURIComponent("clip.set_duration(5)"), { waitUntil: "load" });
  await p.waitForFunction(() => document.getElementById("res").getAttribute("data-done"));
  if (!(await p.evaluate(() => document.getElementById("res").innerText)).includes("with_duration")) { fail++; console.log("FAIL deep link"); }
  await b.close();
  if (errs.length) { fail++; console.log("page errors", errs.slice(0, 5)); }
  console.log(fail ? "FAILED " + fail : "ALL PASS (" + n + " lookups, 2 widths, example buttons, deep link)");
  process.exit(fail ? 1 : 0);
})();
