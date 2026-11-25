#!/usr/bin/env python3
"""Build en/moviepy-removed-name-lookup/ (index.html and moviepy_names.json).

Usage: python3 -I build_page.py probes/ notes.json pypi.json out_dir PUBLISHED MODIFIED
probes/: dir_<version>.json from probe.py (one per installed MoviePy release), verify_1.0.3.json and verify_2.2.1.json from
verify.py (each row of the tables run in both). notes.json: the 2.x spelling for each removed name, and which verify rows back it.
A replacement is marked "same result" only when the verify row gave the identical duration, size, frame, mask and audio numbers
in 1.0.3 and 2.2.1. ASCII only; the facts the prose names are asserted. style.css is shared with .github/llama-args."""
import collections, glob, html, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PD, NOTES, PYPI, OUT, PUB, MOD = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3])), Path(sys.argv[4]), sys.argv[5], sys.argv[6]
key = lambda v: tuple(int(x) for x in v.split("."))
e = html.escape
R = {os.path.basename(f)[4:-5]: json.load(open(f)) for f in glob.glob(os.path.join(PD, "dir_*.json"))}
VS = sorted(R, key=key)
OLD, NEW = "1.0.3", "2.2.1"
assert VS == ["1.0.0", "1.0.1", "1.0.2", "1.0.3", "2.0.0", "2.1.0", "2.1.1", "2.1.2", "2.2.0", "2.2.1"] and PYPI["info"]["version"] == NEW, (VS, PYPI["info"]["version"])
DATE = {v: min(f["upload_time"] for f in PYPI["releases"][v])[:10] for v in VS}
for v, d in R.items():
    assert d["dist"] == v and d["python"].startswith("3.11."), (v, d["dist"], d["python"])
    assert (d["editor"] == "ok") == (key(v) < (2,)), (v, d["editor"])
VA, VB = json.load(open(os.path.join(PD, "verify_%s.json" % OLD)))["rows"], json.load(open(os.path.join(PD, "verify_%s.json" % NEW)))["rows"]


def ver(label):   # same | differs | ran (2.x ran, 1.x raised) | fails
    a, b = VA.get(label), VB.get(label)
    if b is None or "error" in b:
        return "fails"
    if a is None or "error" in a:
        return "ran"
    return "same" if a == b else "differs"


def status(labels):
    if not labels:
        return "name"
    st = [ver(x) for x in labels]
    assert "fails" not in st, (labels, st)
    return "same" if all(s == "same" for s in st) else "differs" if "differs" in st else "ran"


ST_TEXT = {"same": "same result in 1.0.3 and 2.2.1", "ran": "ran in 2.2.1 (the 1.0.3 call raised here)", "differs": "ran in both; the result was not identical",
           "name": "the 2.x name is there; not run"}

# what each release has
MODS = {v: set(d["imports"]) for v, d in R.items()}                                   # module files
NAMES = {v: {m: set(x["names"]) for m, x in d["mods"].items()} for v, d in R.items()}  # names per importable module
def members(d, c):
    return set(d["classes"].get(c, ())) | set(d["inst"].get(c, ()))
CLS = {v: {c: members(d, c) for c in d["classes"]} for v, d in R.items()}
def pat(has):
    return "".join("o" if has(v) else "g" for v in VS)
MAIN = ["Clip", "VideoClip", "VideoFileClip", "ImageClip", "ColorClip", "TextClip", "CompositeVideoClip", "ImageSequenceClip", "AudioClip", "AudioFileClip", "CompositeAudioClip"]
for c in MAIN:
    assert c in CLS[OLD] and c in CLS[NEW], c

# 1. clip members that 1.0.3 has and 2.2.1 does not
GONE = collections.defaultdict(list)   # member -> classes
for c in MAIN:
    for n in sorted(CLS[OLD][c] - CLS[NEW][c]):
        GONE[n].append(c)
MEM = {}
for n, classes in GONE.items():
    p = pat(lambda v: any(n in CLS[v].get(c, ()) for c in classes))
    assert re.fullmatch(r"o{4,}g+", p), (n, p)   # there from 1.0.0, gone for good from some 2.x release
    rem = VS[p.index("g")]
    if n in NOTES["members"]:
        text, labels = NOTES["members"][n]
        MEM[n] = {"classes": classes, "fix": text, "st": status(labels), "rem": rem}
    elif NOTES["member_names"].get(n):
        new = NOTES["member_names"][n]
        assert all(new in CLS[NEW][c] for c in classes), (n, new)
        MEM[n] = {"classes": classes, "fix": "clip.%s" % new + ("()" if n != "memoize_frame" else ""), "st": "name", "rem": rem}
    elif n in NOTES["member_text"]:
        MEM[n] = {"classes": classes, "fix": NOTES["member_text"][n], "st": "", "rem": rem}
    else:
        MEM[n] = {"classes": classes, "fix": "", "st": "", "rem": rem}
for n in ("to_videofile", "to_gif", "to_images_sequence", "to_audiofile"):
    assert all(n.replace("to_", "write_") in CLS[OLD][c] and n.replace("to_", "write_") in CLS[NEW][c] for c in GONE[n]), n
REV = {}   # 2.x member -> the 1.x member it replaces (first name in the note)
for n, m in MEM.items():
    mm = re.match(r"clip\.(\w+)", m["fix"])
    if mm and all(mm.group(1) in CLS[NEW][c] and mm.group(1) not in CLS[OLD][c] for c in m["classes"]):
        REV.setdefault(mm.group(1), n)
assert REV["subclipped"] == "subclip" and REV["with_duration"] == "set_duration" and REV["resized"] == "resize" and REV["with_effects"] in ("fx", "fadein", "afx")
LATER = {n: m["rem"] for n, m in MEM.items() if m["rem"] != "2.0.0"}
print("removed after 2.0.0:", LATER, file=sys.stderr)
for n in NOTES["members"]:
    assert n in GONE, n
for n, new in (("set_duration", "with_duration"), ("subclip", "subclipped"), ("resize", "resized"), ("crop", "cropped"), ("rotate", "rotated"), ("volumex", "with_volume_scaled"),
               ("fx", "with_effects"), ("fl_image", "image_transform"), ("set_position", "with_position"), ("set_audio", "with_audio"), ("on_color", "with_background_color")):
    assert all(new in CLS[NEW][c] and new not in CLS[OLD][c] for c in GONE[n]), (n, new)
SETX = sorted(n for n in GONE if n.startswith("set_"))
assert [n for n in SETX if not all("with_" + n[4:] in CLS[NEW][c] for c in GONE[n])] == ["set_ismask", "set_make_frame", "set_pos"], SETX
assert R[OLD]["mparams"]["VideoClip"]["on_color"] == ["size", "color", "pos", "col_opacity"] and R[NEW]["mparams"]["VideoClip"]["with_background_color"] == ["size", "color", "pos", "opacity"]
for n in ("subclip", "set_duration", "set_position", "set_audio", "resize", "crop", "fl_image", "fx", "fadein", "speedx", "volumex", "set_opacity", "on_color", "margin", "loop"):
    assert MEM[n]["st"] == "same", (n, MEM[n])
assert ver("rotate") == "differs" and ver("rotate (expand)") == "same" and VA["rotate"]["size"] == [48, 64] and VB["rotate"]["size"] == [64, 48]
n_same = sum(1 for m in MEM.values() if m["st"] == "same")

# 2. modules
MOD_GONE = sorted(MODS[OLD] - MODS[NEW])
assert "moviepy.editor" in MOD_GONE and all(pat(lambda v: m in MODS[v]) == "oooogggggg" for m in MOD_GONE)
FXV, FXA = NOTES["vfx"], NOTES["afx"]
vfx_old = [n for n, k in zip(R[OLD]["mods"]["moviepy.video.fx.all"]["names"], R[OLD]["mods"]["moviepy.video.fx.all"]["kinds"]) if k == "f"]
afx_old = [n for n, k in zip(R[OLD]["mods"]["moviepy.audio.fx.all"]["names"], R[OLD]["mods"]["moviepy.audio.fx.all"]["kinds"]) if k == "f"]
assert sorted(vfx_old) == sorted(FXV) and sorted(afx_old) == sorted(FXA), (set(vfx_old) ^ set(FXV), set(afx_old) ^ set(FXA))
for n, (cls, lab) in list(FXV.items()) + list(FXA.items()):
    mod = "moviepy.video.fx" if n in FXV and cls in NAMES[NEW]["moviepy.video.fx"] else "moviepy.audio.fx"
    assert cls in NAMES[NEW][mod], (n, cls)
def fx_mod_fix(m):
    if m in NOTES["modules"]:
        return NOTES["modules"][m]
    mm = re.match(r"moviepy\.(video|audio)\.fx\.(\w+)$", m)
    if mm and mm.group(2) in (FXV if mm.group(1) == "video" else FXA):
        cls = (FXV if mm.group(1) == "video" else FXA)[mm.group(2)][0]
        return "from moviepy import %s: %s.%s (module moviepy.%s.fx.%s)" % ("vfx" if mm.group(1) == "video" else "afx", "vfx" if mm.group(1) == "video" else "afx", cls, mm.group(1), cls)
    return ""
MODFIX = {m: fx_mod_fix(m) for m in MOD_GONE}
for m in NOTES["modules"]:
    assert m in MOD_GONE, m
assert "MasksAnd" in NAMES[NEW]["moviepy.video.fx"] and "MasksOr" in NAMES[NEW]["moviepy.video.fx"]
assert "close_all_clips" in NAMES[NEW]["moviepy.tools"] and "concatenate_videoclips" in NAMES[NEW]["moviepy.video.compositing.CompositeVideoClip"]
assert "moviepy.video.io.display_in_notebook" in MODS[NEW] and "moviepy.video.io.ffplay_previewer" in MODS[NEW]

# 3. what `from moviepy.editor import *` gave, and where it is in 2.x
ED = sorted(NAMES[OLD]["moviepy.editor"])
TOP = NAMES[NEW]["moviepy"]
EDFIX = {}
for n in ED:
    if n in TOP:
        EDFIX[n] = ("from moviepy import %s" % n, "name")
    elif n in NOTES["editor"]:
        EDFIX[n] = (NOTES["editor"][n][0], status(NOTES["editor"][n][1]))
    else:
        EDFIX[n] = ("", "")
assert [n for n in ED if n not in TOP] == ["concatenate", "cvsecs", "download_webfile", "ipython_display", "preview", "show", "transfx"]
assert EDFIX["cvsecs"][1] == "same" and EDFIX["concatenate"][1] == "same" and EDFIX["transfx"][1] == "same"
assert "convert_to_seconds" in TOP and "display_in_notebook" in TOP and "preview" in CLS[NEW]["VideoClip"] and "show" in CLS[NEW]["VideoClip"]

# 4. arguments 1.0.3 takes and 2.2.1 does not, for callables of the same name
def sigs(d):
    out = {}
    for c, ps in d["init"].items():
        if ps is not None and c in MAIN + ["SubtitlesClip"]:
            out[c + "()"] = ps
    for c in ("VideoClip", "AudioClip", "SubtitlesClip"):
        for m, ps in d["mparams"].get(c, {}).items():
            if ps is not None:
                out["%s.%s()" % (c, m)] = ps
    for f, ps in d["fparams"].get("moviepy.editor" if d["editor"] == "ok" else "moviepy", {}).items():
        if ps is not None:
            out[f + "()"] = ps
    return out
SA, SB = sigs(R[OLD]), sigs(R[NEW])
SV = {v: sigs(R[v]) for v in VS}
def par_removed(k, p):   # first 2.x release whose signature of k lacks p
    return next(v for v in VS[VS.index(OLD) + 1:] if k in SV[v] and p not in SV[v][k])
norm = lambda s: s.replace("_", "").lower()
PAR = {}
for k in sorted(SA):
    if k not in SB or (k.startswith("SubtitlesClip.") and k != "SubtitlesClip.in_subclip()") or k.split(".")[-1] in ("preview()", "show()"):
        continue
    for p in SA[k]:
        if p in SB[k]:
            continue
        new = [q for q in SB[k] if q not in SA[k] and norm(q) == norm(p)]
        fix = NOTES["params"].get("%s|%s" % (k, p)) or (new[0] + "=" if new else "")
        r = par_removed(k, p)
        PAR.setdefault(k, {})[p] = fix + (" (from %s)" % r if r != "2.0.0" and fix else " gone from %s" % r if r != "2.0.0" else "")
PAR_LATER = sorted({(k, p, par_removed(k, p)) for k in PAR for p in PAR[k] if par_removed(k, p) != "2.0.0"})
print("arguments that went after 2.0.0:", PAR_LATER, file=sys.stderr)
assert PAR["TextClip()"]["fontsize"].startswith("font_size=") and PAR["TextClip()"]["txt"].startswith("text=") and set(PAR["ColorClip()"]) == {"ismask", "col"}
assert set(PAR["VideoClip()"]) == {"make_frame", "ismask"} and PAR["VideoClip()"]["make_frame"].startswith("frame_function=") and "verbose" in PAR["VideoClip.write_videofile()"] and "rewrite_audio" in PAR["VideoClip.write_videofile()"]
assert PAR["VideoClip.write_images_sequence()"]["nameformat"].startswith("name_format=") and PAR["VideoClip.save_frame()"]["withmask"].startswith("with_mask=")
assert R[OLD]["mparams"]["SubtitlesClip"]["in_subclip"] == ["t_start", "t_end"] and R[NEW]["mparams"]["SubtitlesClip"]["in_subclip"] == ["start_time", "end_time"]
assert R[NEW]["init"]["TextClip"][:4] == ["font", "text", "filename", "font_size"] and R[OLD]["init"]["TextClip"][0] == "txt"
E_FONTSIZE, E_TXT, E_VERBOSE, E_POS = (VB[k]["error"] for k in ("TextClip(fontsize=) (2.x)", "TextClip(txt=) (2.x)", "write_videofile(verbose=) (2.x)", "TextClip positional (2.x)"))
assert E_FONTSIZE == "TypeError: got an unexpected keyword argument 'fontsize'" and E_VERBOSE == "TypeError: got an unexpected keyword argument 'verbose'"
assert E_POS == "TypeError: multiple values for argument 'font'" and "value" in VB["TextClip (2.x)"] and VB["write_videofile (2.x)"]["value"] is True
# two more measured facts
assert [R[v]["version_attr"] for v in VS] == ["1.0.0", "1.0.1", "1.0.2", "1.0.3", "2.0.0", "2.1.0", "2.1.1", "2.1.1", "2.1.2", "2.1.2"]
T220 = R["2.2.0"]["inst_errors"].get("TextClip", "")
assert "'ImageDraw' object has no attribute '_multiline_spacing'" in T220 and "TextClip" in R["2.2.1"]["inst"] and "TextClip" in R["2.1.2"]["inst"]
PIL220, PIL212 = R["2.2.0"]["deps"]["pillow"], R["2.1.2"]["deps"]["pillow"]
assert R["2.2.1"]["deps"]["pillow"] == PIL220

# the data the lookup reads
DATA = {"vs": [[v, DATE[v]] for v in VS], "old": OLD, "new": NEW,
        "mem": {n: [m["classes"], m["fix"], m["st"], m["rem"]] for n, m in sorted(MEM.items())},
        "rev": REV, "cls": {c: sorted(CLS[NEW][c]) for c in MAIN}, "cls_old": {c: sorted(CLS[OLD][c]) for c in MAIN},
        "mod": {m: MODFIX[m] for m in MOD_GONE}, "mods_new": sorted(MODS[NEW]),
        "ed": {n: list(EDFIX[n]) for n in ED}, "top": sorted(TOP),
        "vfx": {n: [c, ver(l) if l else "name"] for n, (c, l) in sorted(FXV.items())}, "afx": {n: [c, ver(l) if l else "name"] for n, (c, l) in sorted(FXA.items())},
        "par": PAR, "st": ST_TEXT,
        "names": {m: sorted(NAMES[NEW][m]) for m in ("moviepy", "moviepy.video.fx", "moviepy.audio.fx", "moviepy.tools", "moviepy.video.tools.subtitles", "moviepy.video.io.ffmpeg_tools") if m in NAMES[NEW]}}
for n, x in list(DATA["vfx"].items()) + list(DATA["afx"].items()):
    assert x[1] != "fails", (n, x)
data_json = json.dumps(DATA, separators=(",", ":"))
assert "</" not in data_json

URL = "https://erimaki-kobo.github.io/en/moviepy-removed-name-lookup/"
TITLE = "'VideoFileClip' object has no attribute 'subclip' (MoviePy 2): every rename"
H1 = ("AttributeError: 'VideoFileClip' object has no attribute 'subclip' (or 'set_duration', 'resize', 'fx', 'volumex'), No module named 'moviepy.editor': "
      "every name MoviePy 2 changed and what to write instead")
DESC = ("MoviePy 2 removed moviepy.editor and renamed clip methods: subclip is subclipped, set_duration is with_duration, resize is resized. "
        "%d renames run in 1.x and 2.x, same result." % n_same)
assert len(TITLE) <= 76 and 140 <= len(DESC) <= 180, (len(TITLE), len(DESC))
stspan = lambda st: ' <span class="note">(%s)</span>' % e(ST_TEXT[st]) if st else ""
ORDER = ["subclip", "set_duration", "set_start", "set_end", "set_position", "set_pos", "set_audio", "set_fps", "set_opacity", "set_mask", "resize", "crop", "rotate", "fx", "fl_image", "fl", "fl_time",
         "fadein", "fadeout", "crossfadein", "crossfadeout", "speedx", "volumex", "loop", "margin", "on_color", "invert_colors", "audio_fadein", "audio_fadeout", "audio_normalize", "audio_loop", "afx", "subfx",
         "cutout", "add_mask", "set_ismask", "set_make_frame", "set_memoize", "ismask", "make_frame", "ipython_display", "to_videofile", "to_gif", "to_images_sequence", "to_audiofile"]
assert all(n in MEM for n in ORDER)
mem_rows = []
for n in ORDER + sorted(set(MEM) - set(ORDER)):
    m = MEM[n]
    cl = "every clip" if len(m["classes"]) >= 8 else "video clips" if "VideoClip" in m["classes"] and "AudioClip" not in m["classes"] else "audio clips" if "VideoClip" not in m["classes"] and "AudioClip" in m["classes"] else ", ".join(m["classes"])
    mem_rows.append("<tr><td><code>clip.%s</code><br><span class=\"note\">%s</span></td><td>%s%s</td></tr>" % (e(n), e(cl), e(m["fix"]) or "no 2.x name found", stspan(m["st"])))
mem_html = "\n".join(mem_rows)
ed_rows = "\n".join("<tr><td><code>%s</code></td><td>%s%s</td></tr>" % (e(n), e(EDFIX[n][0]) or "not in 2.x", stspan(EDFIX[n][1] if EDFIX[n][1] != "name" else "")) for n in ED)
mod_rows = "\n".join("<tr><td><code>%s</code></td><td>%s</td></tr>" % (e(m), e(MODFIX[m]) or "gone; no 2.x module of that name") for m in MOD_GONE if not re.match(r"moviepy\.(video|audio)\.fx\.[a-z_]+$", m) or m.endswith(".all"))
fx_rows = "\n".join("<tr><td><code>%s.%s</code></td><td><code>%s.%s</code>%s</td></tr>" % (pre, e(n), pre, e(c), stspan(ver(l) if l else "name"))
                    for pre, table in (("vfx", FXV), ("afx", FXA)) for n, (c, l) in sorted(table.items()))
par_rows = []
for k in ["TextClip()", "ColorClip()", "VideoClip()", "AudioClip()", "ImageClip()", "CompositeVideoClip()", "ImageSequenceClip()", "VideoFileClip()", "concatenate_videoclips()", "clips_array()",
          "VideoClip.write_videofile()", "VideoClip.write_gif()", "VideoClip.write_images_sequence()", "VideoClip.save_frame()", "AudioClip.write_audiofile()", "SubtitlesClip.in_subclip()"]:
    if k in PAR:
        par_rows.append("<tr><td><code>%s</code></td><td>%s</td></tr>" % (e(k.replace("VideoClip.", "clip.").replace("AudioClip.", "audioclip.")),
                        "; ".join("<code>%s</code> %s" % (e(p), (e(f) if f.startswith("gone") or f.startswith("drop") else "&rarr; " + e(f)) if f.strip() else "gone") for p, f in PAR[k].items())))
assert len(par_rows) >= 14
par_html = "\n".join(par_rows)
D20 = DATE["2.0.0"]
FAQ = [
    ("How do I fix \"'VideoFileClip' object has no attribute 'subclip'\"?",
     "MoviePy 2.0.0 (%s) renamed it: write clip.subclipped(start, end). The other methods changed the same way: set_duration, set_start, set_position and the "
     "rest are with_duration, with_start, with_position; resize, crop and rotate are resized, cropped and rotated. Run on a test clip, subclip(0.5, 1.5) in 1.0.3 "
     "and subclipped(0.5, 1.5) in 2.2.1 gave the same frames. To keep the old names: pip install \"moviepy<2\"." % D20),
    ("How do I fix \"No module named 'moviepy.editor'\"?",
     "MoviePy 2.0.0 removed moviepy.editor. Write from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips (or from moviepy import *). "
     "Code written for 1.x then needs the renamed methods too, or pip install \"moviepy==1.0.3\"."),
    ("How do I fix \"'VideoFileClip' object has no attribute 'resize'\" (or 'fx', 'fadein', 'volumex')?",
     "In 1.x these were effect functions attached to the clip. In 2.x: clip.resized(0.5), clip.cropped(...), clip.rotated(angle, expand=True), "
     "clip.with_volume_scaled(0.5), clip.with_speed_scaled(2); and for every effect, clip.with_effects([vfx.FadeIn(1), vfx.MirrorX()]) with the effect classes "
     "from moviepy import vfx, afx. clip.fx(vfx.mirror_x) becomes clip.with_effects([vfx.MirrorX()])."),
    ("How do I fix \"TextClip got an unexpected keyword argument 'fontsize'\" or \"multiple values for argument 'font'\"?",
     "In 2.x the first parameter of TextClip is font, a path to a font file, and the others were renamed: TextClip(text=\"hi\", font=\"/path/DejaVuSans.ttf\", "
     "font_size=20, color=\"white\") ran in 2.2.1. txt is text and fontsize is font_size. TextClip(\"hi\", font=...) raises \"multiple values "
     "for argument 'font'\" because \"hi\" lands on font."),
    ("How do I fix \"write_videofile() got an unexpected keyword argument 'verbose'\"?",
     "2.x dropped verbose (and rewrite_audio) from write_videofile, and verbose from write_audiofile and write_gif. Remove the argument; logger=None silences the progress bar."),
    ("How do I fix \"'ImageDraw' object has no attribute '_multiline_spacing'\" in TextClip?",
     "That is MoviePy 2.2.0 with Pillow %s: building a TextClip raised it here. 2.2.1, installed with the same Pillow, builds the same clip. pip install -U moviepy." % PIL220),
    ("Why does moviepy.__version__ show the wrong version?",
     "The attribute was not updated in three releases: 2.1.2 reports 2.1.1, and 2.2.0 and 2.2.1 report 2.1.2. Use pip show moviepy, or importlib.metadata.version(\"moviepy\")."),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["MoviePy", "AttributeError"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "MoviePy 1.x to 2.x name lookup", "url": URL + "#lookup",
     "description": "Paste a MoviePy error (no attribute, No module named, unexpected keyword argument) and get the MoviePy 2 spelling.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "MoviePy names removed in 2.0 and their 2.x spelling", "url": URL + "moviepy_names.json", "dateModified": MOD,
     "description": "Clip members, modules, effect functions and arguments that MoviePy 1.0.3 has and 2.2.1 does not, read from %d installed releases, with the 2.x spelling and whether it gave the same result." % len(VS),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "moviepy_names.json"}]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += ("\n.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\ntd code,p code,li code,h1,h2,h3{overflow-wrap:anywhere}"
        "main p,main li,td{overflow-wrap:break-word}\npre{overflow-x:auto;font-size:.85rem;line-height:1.45;padding:10px 12px;border:1px solid var(--line,#ddd);border-radius:8px}\n")
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("AttributeError: 'VideoFileClip' object has no attribute 'subclip'", "subclip"),
      ("ModuleNotFoundError: No module named 'moviepy.editor'", "moviepy.editor"),
      ("AttributeError: 'VideoFileClip' object has no attribute 'resize'", "resize"),
      ("AttributeError: 'TextClip' object has no attribute 'set_position'", "set_position"),
      ("TypeError: TextClip.__init__() got an unexpected keyword argument 'fontsize'", "fontsize"),
      ("clip = clip.fx(vfx.fadein, 1).volumex(0.5)", "old code")]
ex_html = "".join('<button type="button" data-ex="%s">%s</button>' % (e(q), e(lb)) for q, lb in EX)
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), q = document.getElementById("q"), res = document.getElementById("res");
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function st(s) { return s && D.st[s] ? ' <span class="note">(' + esc(D.st[s]) + ")</span>" : ""; }
  var PIN = '<p>To keep the 1.x names instead: <code>pip install "moviepy&lt;2"</code> (that is 1.0.3).</p>';
  function member(n, cls) {
    var m = D.mem[n];
    if (m) return "<h3><code>clip." + esc(n) + "</code></h3><p><strong>Removed in MoviePy " + esc(m[3]) + "</strong>" + (m[3] === "2.0.0" ? " (1.0.3 is the last release with it)" : "") + ".</p><p><strong>Write:</strong> " + (m[1] ? esc(m[1]) + st(m[2]) : "no 2.x name found.") + "</p>";
    var has = Object.keys(D.cls).filter(function (c) { return D.cls[c].indexOf(n) >= 0; }), had = Object.keys(D.cls_old).filter(function (c) { return D.cls_old[c].indexOf(n) >= 0; });
    if (has.length && !had.length) return "<h3><code>clip." + esc(n) + "</code></h3><p><strong>New in MoviePy 2.x</strong> (" + esc(has.slice(0, 4).join(", ")) + "): 1.0.3 does not have it, so your install is 1.x. <code>pip install -U moviepy</code>" + (D.rev[n] ? ", or use the 1.x name <code>clip." + esc(D.rev[n]) + "</code>" : "") + ".</p>";
    if (has.length) return "<h3><code>clip." + esc(n) + "</code></h3><p>Both 1.0.3 and 2.2.1 have it on " + esc(has.slice(0, 5).join(", ")) + (cls && has.indexOf(cls) < 0 ? ", but not on " + esc(cls) : "") + ".</p>";
    return "";
  }
  function fxname(pre, n) {
    var t = D[pre][n];
    return t ? "<h3><code>" + pre + "." + esc(n) + "</code></h3><p><strong>Removed in MoviePy 2.0.0.</strong> The effect is a class now: <code>clip.with_effects([" + pre + "." + esc(t[0]) + "(...)])</code>" + st(t[1]) + "</p>" : "";
  }
  function show() {
    var t = q.value, h = "", seen = {}, m, re;
    function add(k, s) { if (s && !seen[k]) { seen[k] = 1; h += s; } }
    re = /'(\w+)' object has no attribute '(\w+)'/g;
    while ((m = re.exec(t))) add("m" + m[2], member(m[2], m[1]));
    re = /No module named '(moviepy[\w.]*)'|(?:from|import)\s+(moviepy\.[\w.]+)/g;
    while ((m = re.exec(t))) {
      var mod = m[1] || m[2];
      if (mod in D.mod) add("M" + mod, "<h3><code>" + esc(mod) + "</code></h3><p><strong>Removed in MoviePy 2.0.0.</strong> " + (D.mod[mod] ? "<strong>Write:</strong> " + esc(D.mod[mod]) : "No 2.x module of that name.") + "</p>");
      else if (D.mods_new.indexOf(mod) >= 0 && m[1]) add("M" + mod, "<h3><code>" + esc(mod) + "</code></h3><p>MoviePy 2.2.1 has this module; 1.0.3 " + (/\.fx\.[A-Z]/.test(mod) ? "does not (the effect classes are new in 2.0.0): <code>pip install -U moviepy</code>." : "may not.") + "</p>");
    }
    re = /cannot import name '(\w+)' from '(moviepy[\w.]*)'|module '(moviepy[\w.]*)' has no attribute '(\w+)'/g;
    while ((m = re.exec(t))) {
      var n = m[1] || m[4], mo = m[2] || m[3];
      if (/fx/.test(mo) && (D.vfx[n] || D.afx[n])) add("f" + n, fxname(D.vfx[n] && !/audio/.test(mo) ? "vfx" : "afx", n));
      else if (D.ed[n] && mo !== "moviepy") add("e" + n, "<h3><code>" + esc(n) + "</code></h3><p>" + (D.ed[n][0] ? "<strong>Write:</strong> " + esc(D.ed[n][0]) + st(D.ed[n][1] === "name" ? "" : D.ed[n][1]) : "Not in MoviePy 2.x.") + "</p>");
      else if (D.top.indexOf(n) >= 0) add("e" + n, "<h3><code>" + esc(n) + "</code></h3><p>MoviePy 2.2.1 has it at the top: <code>from moviepy import " + esc(n) + "</code>. If that fails, the install is 1.x (there: <code>from moviepy.editor import " + esc(n) + "</code>).</p>");
      else if (D.vfx[n] || D.afx[n]) add("f" + n, fxname(D.vfx[n] ? "vfx" : "afx", n));
    }
    re = /(?:(\w+)(?:\.__init__)?\(\) )?got an unexpected keyword argument '(\w+)'/g;
    while ((m = re.exec(t))) {
      var p = m[2], hits = Object.keys(D.par).filter(function (k) { return p in D.par[k] && (!m[1] || k.indexOf(m[1]) >= 0); });
      if (!hits.length) hits = Object.keys(D.par).filter(function (k) { return p in D.par[k]; });
      if (hits.length) add("p" + p, "<h3>argument <code>" + esc(p) + "</code></h3><p><strong>MoviePy 2 no longer takes it</strong> in " + hits.slice(0, 6).map(function (k) { return "<code>" + esc(k) + "</code>" + (D.par[k][p] ? " (write " + esc(D.par[k][p]) + ")" : " (gone)"); }).join(", ") + ".</p>");
    }
    if (/multiple values for argument 'font'/.test(t)) add("font", "<h3>TextClip: multiple values for argument 'font'</h3><p>In MoviePy 2 the first parameter of TextClip is <code>font</code> (a path to a font file), not the text. <strong>Write:</strong> TextClip(text=\"...\", font=\"/path/font.ttf\", font_size=40, color=\"white\").</p>");
    if (/_multiline_spacing/.test(t)) add("ms", "<h3>'ImageDraw' object has no attribute '_multiline_spacing'</h3><p>MoviePy 2.2.0 with a new Pillow; 2.2.1 builds the same TextClip. <code>pip install -U moviepy</code></p>");
    if (!h || /\.\w+\(/.test(t)) {
      re = /\.(\w+)\s*\(|\b(vfx|afx)\.(\w+)/g;
      while ((m = re.exec(t))) {
        if (m[1] && D.mem[m[1]]) add("m" + m[1], member(m[1]));
        else if (m[2] && D[m[2]][m[3]]) add("f" + m[3], fxname(m[2], m[3]));
      }
      re = /\b(\w+)\s*=/g;
      while ((m = re.exec(t))) { var ks = Object.keys(D.par).filter(function (k) { return m[1] in D.par[k] && t.indexOf(k.replace(/\(\)$/, "").split(".").pop() + "(") >= 0; });
        if (ks.length) add("p" + m[1], "<h3>argument <code>" + esc(m[1]) + "</code></h3><p><strong>MoviePy 2 no longer takes it</strong> in <code>" + esc(ks[0]) + "</code>" + (D.par[ks[0]][m[1]] ? ": write " + esc(D.par[ks[0]][m[1]]) : " (gone)") + ".</p>"); }
    }
    res.innerHTML = h ? h + PIN : "<p>Paste the error line or the old code, for example 'VideoFileClip' object has no attribute 'subclip'. Nothing in it matched a name MoviePy 2 changed.</p>";
    res.setAttribute("data-done", String(Date.now()));
  }
  document.getElementById("go").addEventListener("click", show);
  [].forEach.call(document.querySelectorAll("[data-ex]"), function (b) { b.addEventListener("click", function () { q.value = b.getAttribute("data-ex"); show(); }); });
  var u = new URLSearchParams(location.search); if (u.get("q")) { q.value = u.get("q"); show(); }
  window.MP_READY = true;
})();
"""
assert "</script" not in JS
n_mem_fix = sum(1 for m in MEM.values() if m["fix"])
page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(TITLE, quote=False)}</title>
<meta name="description" content="{e(DESC)}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(TITLE)}">
<meta property="og:description" content="{e(DESC)}">
<meta property="og:url" content="{URL}">
<style>
{css}</style>
<script type="application/ld+json">{LD}</script>
</head>
<body>
<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>{e(H1, quote=False)}</h1>
<p class="lede"><strong>MoviePy 2.0.0 ({D20}) removed <code>moviepy.editor</code> and renamed the clip methods. Write <code>from moviepy import VideoFileClip</code>; <code>subclip</code> is <code>subclipped</code>, the <code>set_x</code> methods are <code>with_x</code> (<code>with_duration</code>, <code>with_position</code>, <code>with_audio</code>), <code>resize</code> / <code>crop</code> / <code>rotate</code> are <code>resized</code> / <code>cropped</code> / <code>rotated</code>, <code>volumex</code> is <code>with_volume_scaled</code>, and <code>clip.fx(vfx.fadein, 1)</code> is <code>clip.with_effects([vfx.FadeIn(1)])</code>.</strong> Or keep the old names with <code>pip install "moviepy&lt;2"</code>. Many tutorials still show 1.x code: paste the error or the code below.</p>
<p class="meta">Published {PUB} &middot; MoviePy {VS[0]} to {VS[-1]} installed ({len(VS)} releases) &middot; {n_same} of the {len(MEM)} removed clip members gave the same result under their 2.x name &middot; <a href="#how">how</a></p>
<pre><code># MoviePy 1.x
from moviepy.editor import *
clip = VideoFileClip("in.mp4").subclip(5, 10)
clip = clip.resize(0.5).set_fps(24)
clip = clip.fx(vfx.fadein, 1).volumex(0.8)
txt = TextClip("Hi", fontsize=40, color="white")
txt = txt.set_position("center").set_duration(5)
CompositeVideoClip([clip, txt]).write_videofile("out.mp4")</code></pre>
<pre><code># MoviePy 2.x
from moviepy import *
clip = VideoFileClip("in.mp4").subclipped(5, 10)
clip = clip.resized(0.5).with_fps(24)
clip = clip.with_effects([vfx.FadeIn(1)]).with_volume_scaled(0.8)
txt = TextClip(text="Hi", font="DejaVuSans.ttf", font_size=40, color="white")
txt = txt.with_position("center").with_duration(5)
CompositeVideoClip([clip, txt]).write_videofile("out.mp4")</code></pre>

<div class="card" id="lookup">
<label for="q">The error line, or the old code</label>
<textarea id="q" spellcheck="false" placeholder="AttributeError: 'VideoFileClip' object has no attribute 'subclip'"></textarea>
<div class="row"><button type="button" id="go">Look up</button></div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on the data in this page (<a href="moviepy_names.json">moviepy_names.json</a>); nothing you paste is sent anywhere.</p>
</div>

<h2 id="methods">Which clip methods did MoviePy 2 rename?</h2>
<p><strong>{len(MEM)} clip members are in 1.0.3 and not in 2.2.1; {len(MEM) - len(LATER)} of them went in 2.0.0{"".join(" (%s in %s)" % (k, v) for k, v in sorted(LATER.items()))}.</strong> "Same result" means the 1.x call in 1.0.3 and the 2.x call in 2.2.1 were run on the same test clip and gave identical duration, size, frame, mask and audio numbers.</p>
<div class="tw"><table class="flt">
<thead><tr><th>MoviePy 1.x</th><th>MoviePy 2.x</th></tr></thead>
<tbody>
{mem_html}
</tbody></table></div>

<h2 id="imports">What replaces <code>from moviepy.editor import ...</code>?</h2>
<p><strong><code>moviepy.editor</code> is gone in every 2.x release; its names are at the top of the package.</strong> What <code>from moviepy.editor import *</code> gave in 1.0.3, and where each is in 2.2.1:</p>
<div class="tw"><table>
<thead><tr><th>In moviepy.editor (1.0.3)</th><th>MoviePy 2.x</th></tr></thead>
<tbody>
{ed_rows}
</tbody></table></div>
<p>Modules that 1.0.3 has and 2.2.1 does not ({len(MOD_GONE)}; the {sum(1 for m in MOD_GONE if re.match(r"moviepy\.(video|audio)\.fx\.[a-z_]+$", m) and not m.endswith(".all"))} one-function effect modules such as <code>moviepy.video.fx.resize</code> are in the next table):</p>
<div class="tw"><table>
<thead><tr><th>Module (1.x)</th><th>MoviePy 2.x</th></tr></thead>
<tbody>
{mod_rows}
</tbody></table></div>

<h2 id="effects">Which effect class replaces each <code>vfx</code> / <code>afx</code> function?</h2>
<p><strong>Effects are classes in 2.x, applied with <code>clip.with_effects([...])</code>.</strong> The module moved with the name: <code>moviepy.video.fx.resize</code> is <code>moviepy.video.fx.Resize</code>.</p>
<div class="tw"><table>
<thead><tr><th>1.x function</th><th>2.x class</th></tr></thead>
<tbody>
{fx_rows}
</tbody></table></div>

<h2 id="arguments">Which arguments did MoviePy 2 rename or drop?</h2>
<p><strong>Read from the signatures of 1.0.3 and 2.2.1.</strong> In 2.2.1, <code>TextClip(fontsize=20)</code> raises "{e(E_FONTSIZE)}" and <code>write_videofile(verbose=False)</code> raises "{e(E_VERBOSE)}".</p>
<div class="tw"><table>
<thead><tr><th>Call</th><th>1.x argument &rarr; 2.x</th></tr></thead>
<tbody>
{par_html}
</tbody></table></div>

<h2 id="how">How was this measured?</h2>
<p><strong>MoviePy {", ".join(VS)} were each installed from PyPI in their own environment (Python {R[NEW]["python"]}), and a probe listed every module file, the names of each importable module, and the members and parameters of every class, after <code>import moviepy.editor</code> where it exists</strong> (that import is what attaches <code>resize</code>, <code>fadein</code> and the other effect methods to the clips in 1.x). Members set in <code>__init__</code> were read from real objects: a ColorClip, ImageClip, AudioClip, CompositeVideoClip, and a VideoFileClip and AudioFileClip of a one-second file written with the bundled ffmpeg.</p>
<p>Each rename was then run: the 1.x spelling in 1.0.3 and the 2.x spelling in 2.2.1 on the same two-second 64x48 clip (a moving gradient with a 440 Hz tone), comparing duration, size, fps, the frame at t=0.5, the mask frame and the loudest audio sample. Rows that did not come out identical say so. 1.x TextClip needs ImageMagick and could not be built here, so TextClip was run in 2.x only. 2.0.0.dev1 and dev2 (2020) were not installed.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>The MoviePy releases on <a href="https://pypi.org/project/moviepy/#history">PyPI</a>, installed and run; the release dates are PyPI's.</li>
<li>MoviePy's own <a href="https://zulko.github.io/moviepy/getting_started/updating_to_v2.html">guide to updating from v1 to v2</a>.</li>
</ul>
<p>The same data as JSON: <a href="moviepy_names.json">moviepy_names.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/opencv-removed-name-lookup/">"module 'cv2' has no attribute 'CascadeClassifier'"</a> &middot; <a href="/en/pillow-removed-name-lookup/">"module 'PIL.Image' has no attribute 'ANTIALIAS'"</a> &middot; <a href="/en/numpy-removed-attribute-lookup/">"module 'numpy' has no attribute 'float_'"</a>.</p>
</main>
<script type="application/json" id="data">{data_json}</script>
<script>
{JS}</script>
</body>
</html>
"""
page.encode("ascii")
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "index.html").write_text(page, encoding="ascii")
(OUT / "moviepy_names.json").write_text(json.dumps(DATA, indent=0), encoding="ascii")
print("index.html %d bytes | removed members %d (with a 2.x spelling %d, same result %d) | modules gone %d | effects %d | calls with dropped arguments %d"
      % (len(page), len(MEM), n_mem_fix, n_same, len(MOD_GONE), len(FXV) + len(FXA), len(PAR)), file=sys.stderr)
