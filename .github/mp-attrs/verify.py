"""usage: <python with moviepy 1.0.3 or 2.2.1> verify.py > result.json
Each row of the page's table, run: the 1.x spelling in 1.x, the 2.x spelling in 2.x, on the same two-second 64x48 test clip
(a moving gradient with a 440 Hz tone). The result of a row is what can be compared across the two: duration, size, fps,
the frame at t=0.5 (sha1), the mask frame, the loudest audio sample. build_page.py compares the two files."""
import hashlib, json, os, sys, warnings
warnings.simplefilter("ignore")
REAL, sys.stdout = sys.stdout, open(os.devnull, "w")
import numpy as np
import moviepy
V2 = not os.path.exists(os.path.join(os.path.dirname(moviepy.__file__), "editor.py"))
if V2:
    from moviepy import VideoClip, AudioClip, ColorClip, CompositeVideoClip, concatenate_videoclips, clips_array, vfx, afx, convert_to_seconds, TextClip
else:
    from moviepy.editor import VideoClip, AudioClip, ColorClip, CompositeVideoClip, concatenate_videoclips, clips_array, vfx, afx, cvsecs, concatenate
    import moviepy.video.compositing.transitions as transfx
yy, xx = np.mgrid[0:48, 0:64]
def frame(t):
    k = int(round(t * 10))
    return np.dstack([(xx * 3 + k * 7) % 256, (yy * 5 + k * 3) % 256, (xx + yy + k) % 256]).astype("uint8")
def tone(t):
    return 0.8 * np.sin(440 * 2 * np.pi * t)
def clip():
    c = VideoClip(frame_function=frame, duration=2) if V2 else VideoClip(make_frame=frame, duration=2)
    return c.with_fps(10) if V2 else c.set_fps(10)
def aclip():
    return AudioClip(frame_function=tone, duration=2, fps=22050) if V2 else AudioClip(make_frame=tone, duration=2, fps=22050)
def sclip():   # stereo
    f = lambda t: np.array([tone(t), tone(t)]).T
    return AudioClip(frame_function=f, duration=2, fps=22050) if V2 else AudioClip(make_frame=f, duration=2, fps=22050)
def cA():
    return clip().with_audio(aclip()) if V2 else clip().set_audio(aclip())
def sha(a):
    return hashlib.sha1(np.ascontiguousarray(a).tobytes()).hexdigest()[:12]
def desc(c, t=0.5):
    d = {"duration": None if c.duration is None else round(float(c.duration), 4)}
    if hasattr(c, "get_frame") and hasattr(c, "size"):
        f = c.get_frame(t)
        d.update(size=[int(x) for x in c.size], frame=sha(f), mean=round(float(np.asarray(f, float).mean()), 2), fps=getattr(c, "fps", None))
        m = getattr(c, "mask", None)
        if m is not None:
            d["mask_mean"] = round(float(np.asarray(m.get_frame(t), float).mean()), 4)
        a = getattr(c, "audio", None)
        if a is not None:
            d["audio_max"] = round(float(np.abs(a.to_soundarray(fps=22050)).max()), 3)
        d["start"], d["end"] = c.start, c.end
    else:
        arr = np.asarray(c.to_soundarray(fps=22050))
        d["audio_max"] = round(float(np.abs(arr).max()), 3)
        d["audio_first"] = round(float(np.abs(arr[:2205]).max()), 3)
        d["audio_last"] = round(float(np.abs(arr[-2205:]).max()), 3)
    return d
f2 = lambda t: 255 - frame(t)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
# label: (1.x spelling, 2.x spelling)
ROWS = {
 "subclip": (lambda: clip().subclip(0.5, 1.5), lambda: clip().subclipped(0.5, 1.5)),
 "set_duration": (lambda: clip().set_duration(1), lambda: clip().with_duration(1)),
 "set_start": (lambda: clip().set_start(1), lambda: clip().with_start(1)),
 "set_end": (lambda: clip().set_end(1), lambda: clip().with_end(1)),
 "set_fps": (lambda: clip().set_fps(5), lambda: clip().with_fps(5)),
 "set_audio": (lambda: clip().set_audio(aclip()), lambda: clip().with_audio(aclip())),
 "set_opacity": (lambda: clip().set_opacity(0.5), lambda: clip().with_opacity(0.5)),
 "set_position": (lambda: CompositeVideoClip([clip().set_position((3, 4))], size=(80, 60)), lambda: CompositeVideoClip([clip().with_position((3, 4))], size=(80, 60))),
 "set_pos": (lambda: CompositeVideoClip([clip().set_pos((3, 4))], size=(80, 60)), lambda: CompositeVideoClip([clip().with_position((3, 4))], size=(80, 60))),
 "set_mask": (lambda: clip().set_mask(ColorClip((64, 48), color=0.25, ismask=True, duration=2)), lambda: clip().with_mask(ColorClip((64, 48), color=0.25, is_mask=True, duration=2))),
 "set_make_frame": (lambda: clip().set_make_frame(f2), lambda: clip().with_updated_frame_function(f2)),
 "resize": (lambda: clip().resize(0.5), lambda: clip().resized(0.5)),
 "resize(width=)": (lambda: clip().resize(width=32), lambda: clip().resized(width=32)),
 "crop": (lambda: clip().crop(x1=4, y1=4, x2=40, y2=30), lambda: clip().cropped(x1=4, y1=4, x2=40, y2=30)),
 "rotate": (lambda: clip().rotate(90), lambda: clip().rotated(90)),
 "rotate (expand)": (lambda: clip().rotate(90), lambda: clip().rotated(90, expand=True)),
 "rotate 180": (lambda: clip().rotate(180), lambda: clip().rotated(180)),
 "fl_image": (lambda: clip().fl_image(lambda im: 255 - im), lambda: clip().image_transform(lambda im: 255 - im)),
 "fl": (lambda: clip().fl(lambda gf, t: gf(t)[::-1]), lambda: clip().transform(lambda gf, t: gf(t)[::-1])),
 "fl_time": (lambda: clip().fl_time(lambda t: 2 * t).set_duration(1), lambda: clip().time_transform(lambda t: 2 * t).with_duration(1)),
 "fx": (lambda: clip().fx(vfx.mirror_x), lambda: clip().with_effects([vfx.MirrorX()])),
 "fadein": (lambda: clip().fadein(1), lambda: clip().with_effects([vfx.FadeIn(1)])),
 "fadeout": (lambda: clip().fadeout(1.8), lambda: clip().with_effects([vfx.FadeOut(1.8)])),
 "crossfadein": (lambda: clip().crossfadein(1), lambda: clip().with_effects([vfx.CrossFadeIn(1)])),
 "crossfadeout": (lambda: clip().crossfadeout(1.8), lambda: clip().with_effects([vfx.CrossFadeOut(1.8)])),
 "speedx": (lambda: clip().speedx(2), lambda: clip().with_speed_scaled(2)),
 "speedx (effect)": (lambda: clip().speedx(2), lambda: clip().with_effects([vfx.MultiplySpeed(2)])),
 "volumex": (lambda: cA().volumex(0.5), lambda: cA().with_volume_scaled(0.5)),
 "loop": (lambda: clip().loop(n=2), lambda: clip().with_effects([vfx.Loop(n=2)])),
 "margin": (lambda: clip().margin(4), lambda: clip().with_effects([vfx.Margin(4)])),
 "invert_colors": (lambda: clip().invert_colors(), lambda: clip().with_effects([vfx.InvertColors()])),
 "on_color": (lambda: clip().on_color(size=(80, 60), color=(0, 0, 255), pos=(8, 6)), lambda: clip().with_background_color(size=(80, 60), color=(0, 0, 255), pos=(8, 6))),
 "add_mask": (lambda: clip().add_mask(), lambda: clip().with_mask()),
 "cutout": (lambda: clip().cutout(0.5, 1.0), lambda: clip().with_section_cut_out(0.5, 1.0)),
 "subfx": (lambda: clip().subfx(vfx.mirror_x, 0.3, 1.0), lambda: clip().with_effects_on_subclip([vfx.MirrorX()], 0.3, 1.0)),
 "afx": (lambda: cA().afx(afx.volumex, 0.5), lambda: cA().with_effects([afx.MultiplyVolume(0.5)])),
 "audio_fadein": (lambda: sclip().audio_fadein(1), lambda: sclip().with_effects([afx.AudioFadeIn(1)])),
 "audio_fadeout": (lambda: sclip().audio_fadeout(1), lambda: sclip().with_effects([afx.AudioFadeOut(1)])),
 "audio_normalize": (lambda: aclip().audio_normalize(), lambda: aclip().with_effects([afx.AudioNormalize()])),
 "audio_loop": (lambda: sclip().audio_loop(nloops=2), lambda: sclip().with_effects([afx.AudioLoop(n_loops=2)])),
 "audio volumex": (lambda: aclip().volumex(0.5), lambda: aclip().with_volume_scaled(0.5)),
 "audio subclip": (lambda: aclip().subclip(0.5, 1), lambda: aclip().subclipped(0.5, 1)),
 "vfx.blackwhite": (lambda: clip().fx(vfx.blackwhite), lambda: clip().with_effects([vfx.BlackAndWhite()])),
 "vfx.colorx": (lambda: clip().fx(vfx.colorx, 0.5), lambda: clip().with_effects([vfx.MultiplyColor(0.5)])),
 "vfx.gamma_corr": (lambda: clip().fx(vfx.gamma_corr, 0.5), lambda: clip().with_effects([vfx.GammaCorrection(0.5)])),
 "vfx.lum_contrast": (lambda: clip().fx(vfx.lum_contrast, lum=10, contrast=0.2), lambda: clip().with_effects([vfx.LumContrast(lum=10, contrast=0.2)])),
 "vfx.mirror_y": (lambda: clip().fx(vfx.mirror_y), lambda: clip().with_effects([vfx.MirrorY()])),
 "vfx.time_mirror": (lambda: clip().fx(vfx.time_mirror), lambda: clip().with_effects([vfx.TimeMirror()])),
 "vfx.time_symmetrize": (lambda: clip().fx(vfx.time_symmetrize), lambda: clip().with_effects([vfx.TimeSymmetrize()])),
 "vfx.freeze": (lambda: clip().fx(vfx.freeze, t=0.5, freeze_duration=1), lambda: clip().with_effects([vfx.Freeze(t=0.5, freeze_duration=1)])),
 "vfx.even_size": (lambda: clip().crop(x2=63, y2=47).fx(vfx.even_size), lambda: clip().cropped(x2=63, y2=47).with_effects([vfx.EvenSize()])),
 "vfx.make_loopable": (lambda: clip().fx(vfx.make_loopable, 0.5), lambda: clip().with_effects([vfx.MakeLoopable(0.5)])),
 "vfx.mask_color": (lambda: clip().fx(vfx.mask_color, color=[0, 0, 0], thr=100), lambda: clip().with_effects([vfx.MaskColor(color=[0, 0, 0], threshold=100)])),
 "vfx.blink": (lambda: clip().fx(vfx.blink, 0.3, 0.3), lambda: clip().with_effects([vfx.Blink(0.3, 0.3)])),
 "vfx.resize": (lambda: clip().fx(vfx.resize, 0.5), lambda: clip().with_effects([vfx.Resize(0.5)])),
 "vfx.crop": (lambda: clip().fx(vfx.crop, x1=4, x2=40), lambda: clip().with_effects([vfx.Crop(x1=4, x2=40)])),
 "vfx.rotate": (lambda: clip().fx(vfx.rotate, 180), lambda: clip().with_effects([vfx.Rotate(180)])),
 "vfx.margin": (lambda: clip().fx(vfx.margin, 4), lambda: clip().with_effects([vfx.Margin(4)])),
 "vfx.loop": (lambda: clip().fx(vfx.loop, duration=5), lambda: clip().with_effects([vfx.Loop(duration=5)])),
 "vfx.speedx": (lambda: clip().fx(vfx.speedx, 0.5), lambda: clip().with_effects([vfx.MultiplySpeed(0.5)])),
 "vfx.fadein": (lambda: clip().fx(vfx.fadein, 1), lambda: clip().with_effects([vfx.FadeIn(1)])),
 "vfx.invert_colors": (lambda: clip().fx(vfx.invert_colors), lambda: clip().with_effects([vfx.InvertColors()])),
 "afx.audio_left_right": (lambda: afx.audio_left_right(AudioClip(make_frame=lambda t: np.array([tone(t), tone(t)]).T, duration=2, fps=22050), left=0.5, right=0.25),
                          lambda: AudioClip(frame_function=lambda t: np.array([tone(t), tone(t)]).T, duration=2, fps=22050).with_effects([afx.MultiplyStereoVolume(left=0.5, right=0.25)])),
 "transfx.slide_in": (lambda: CompositeVideoClip([clip().fx(transfx.slide_in, 1, "left")]), lambda: CompositeVideoClip([clip().with_effects([vfx.SlideIn(1, "left")])])),
 "transfx.crossfadein": (lambda: clip().fx(transfx.crossfadein, 1), lambda: clip().with_effects([vfx.CrossFadeIn(1)])),
 "concatenate_videoclips": (lambda: concatenate_videoclips([clip(), clip()]), lambda: concatenate_videoclips([clip(), clip()])),
 "concatenate": (lambda: concatenate([clip(), clip()]), lambda: concatenate_videoclips([clip(), clip()])),
 "clips_array": (lambda: clips_array([[clip(), clip()]]), lambda: clips_array([[clip(), clip()]])),
 "ColorClip(col=)": (lambda: ColorClip((64, 48), col=(255, 0, 0), duration=1), lambda: ColorClip((64, 48), color=(255, 0, 0), duration=1)),
 "ColorClip(ismask=)": (lambda: CompositeVideoClip([clip().set_mask(ColorClip((64, 48), color=0.5, ismask=True, duration=2))]), lambda: CompositeVideoClip([clip().with_mask(ColorClip((64, 48), color=0.5, is_mask=True, duration=2))])),
}
out = {}
for label, pair in ROWS.items():
    try:
        out[label] = desc(pair[1 if V2 else 0]())
    except Exception as e:
        out[label] = {"error": "%s: %s" % (type(e).__name__, str(e)[:200])}
try:
    out["cvsecs"] = {"value": (convert_to_seconds if V2 else cvsecs)("00:01:30.5")}
except Exception as e:
    out["cvsecs"] = {"error": "%s: %s" % (type(e).__name__, e)}
for label, f in {"ismask attr": lambda: getattr(clip(), "is_mask" if V2 else "ismask"),
                 "make_frame attr": lambda: sha((getattr(clip(), "frame_function" if V2 else "make_frame"))(0.5)),
                 "set_ismask": lambda: getattr(clip().with_is_mask(True) if V2 else clip().set_ismask(True), "is_mask" if V2 else "ismask"),
                 "set_memoize": lambda: (clip().with_memoize(True) if V2 else clip().set_memoize(True)).memoize}.items():
    try:
        out[label] = {"value": f()}
    except Exception as e:
        out[label] = {"error": "%s: %s" % (type(e).__name__, e)}
if V2:
    for label, f in {"TextClip (2.x)": lambda: desc(TextClip(text="hi", font=FONT, font_size=20, color="white", duration=1)),
                     "write_videofile (2.x)": lambda: (clip().write_videofile("v.mp4", fps=10, logger=None), os.path.getsize("v.mp4") > 0)[1],
                     "write_videofile(verbose=) (2.x)": lambda: clip().write_videofile("v.mp4", fps=10, verbose=False, logger=None),
                     "TextClip(fontsize=) (2.x)": lambda: TextClip(text="hi", font=FONT, fontsize=20),
                     "TextClip(txt=) (2.x)": lambda: TextClip(txt="hi", font=FONT),
                     "TextClip positional (2.x)": lambda: desc(TextClip("hi", font=FONT, font_size=20).with_duration(1))}.items():
        try:
            out[label] = {"value": f()}
        except Exception as e:
            out[label] = {"error": "%s: %s" % (type(e).__name__, str(e)[:200])}
def plain(o):
    if isinstance(o, dict):
        return {k: plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [plain(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    return o
json.dump({"moviepy": moviepy.__version__, "v2": V2, "rows": plain(out)}, REAL, indent=0, sort_keys=True)
