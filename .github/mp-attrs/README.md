# en/moviepy-removed-name-lookup: how the page is built

MoviePy 1.0.0-1.0.3 and 2.0.0-2.2.1 (10 releases), each in its own uv venv on Python 3.11
(1.x: with "numpy<2" "pillow<10" "setuptools<70"; 1.x is sdist only and builds from source).
probe.py: after `import moviepy.editor` where it exists (that import attaches resize, fadein, ... to the clips in 1.x),
lists every module file, the names of each importable module, the members and parameters of every class, and the public
attributes of real objects (ColorClip, ImageClip, AudioClip, CompositeVideoClip, a VideoFileClip/AudioFileClip of a file
written with the bundled ffmpeg, TextClip where it can be built).
verify.py: every row of the tables, run: the 1.x spelling in 1.0.3 and the 2.x spelling in 2.2.1 on the same test clip;
build_page.py marks a row "same result" only when the two outputs are identical (duration, size, fps, frame sha1 at t=0.5,
mask frame, loudest audio sample). notes.json: the 2.x spelling of each removed name and the verify rows that back it.

```
curl -sS https://pypi.org/pypi/moviepy/json -o pypi.json      # probes/pypi.json keeps only the dates
uv venv -q --python 3.11 v_$V; uv pip install -q --python v_$V/bin/python "moviepy==$V" [numpy<2 pillow<10 setuptools<70]
mkdir w_$V; v_$V/bin/python -I probe.py w_$V > probes/dir_$V.json
(cd vw1 && ../v_1.0.3/bin/python -I verify.py > ../probes/verify_1.0.3.json)
(cd vw2 && ../v_2.2.1/bin/python -I verify.py > ../probes/verify_2.2.1.json)
python3 -I build_page.py probes notes.json probes/pypi.json <repo>/en/moviepy-removed-name-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
Not identical in the two versions: clip.rotate(90) vs clip.rotated(90) (2.x keeps the frame size unless expand=True),
vfx.time_mirror vs vfx.TimeMirror (the frame at t=0.5 differed). 1.0.3 raised in audio_loop, vfx.blink and
afx.audio_left_right on NumPy 1.26, so those rows ran in 2.2.1 only. 1.x TextClip needs ImageMagick (blocked by the
policy file here), so TextClip was built in 2.x only. The code sample at the top of the page was run in 2.2.1 as written
(shorter times, a real font path) and, without the TextClip lines, in 1.0.3.
The probe results are in probes.tar.xz (`tar xJf probes.tar.xz` gives probes/).
