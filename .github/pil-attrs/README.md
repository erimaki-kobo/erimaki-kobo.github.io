# en/pillow-removed-name-lookup: how the page is built

Same method as ../sk-attrs (build_page.py started from it). probe.py lists and getattr-s the PIL modules and the Image,
ImageDraw, FreeTypeFont and ImageFont classes in each installed Pillow; msg_probe.py also turns Pillow's
`deprecate("name", 10, "action")` calls into the sentence PIL/_deprecate.py prints. Pillow's modules have no __all__, so
build_page.py keeps class members and names with deprecation text (plus notes.json "keep"). ImageTk, ImageQt and
ImageGrab are skipped (environment-dependent imports).

```
curl -sS https://pypi.org/pypi/pillow/json -o pypi.json
for spec in 7.0.0:3.8 ... 10.4.0:3.8 11.0.0:3.9 ... 11.3.0:3.9 12.0.0:3.12 12.1.0:3.12 12.2.0:3.12 12.3.0:3.13 13.0.0:3.13; do   # every minor
  v=${spec%%:*}; p=${spec##*:}; uv venv -q --python $p v_$v; uv pip install -q --python v_$v/bin/python "pillow==$v"
  v_$v/bin/python -I probe.py dir > probes/dir_$v.json
done
# names.json = union of the dir lists; v_X/bin/python -I probe.py get names.json > probes/get_X.json
# want_X.json = names X has and the next release does not; v_X/bin/python -I msg_probe.py want_X.json > probes/msg_X.json
python3 -I build_page.py probes notes.json pypi.json <repo>/en/pillow-removed-name-lookup <published> <today>
node check_browser.js http://127.0.0.1:PORT
```
