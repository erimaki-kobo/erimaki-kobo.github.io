"""usage: <python with one scikit-image> kwprobe.py > kw.json
Calls a few functions with the argument names older code uses (multichannel=, selem=, as_grey=, neighbors=, indices=, ...) on a
small test image, and records for each: ok, the warning scikit-image prints, or the error."""
import json, os, sys, warnings
REAL, sys.stdout = sys.stdout, open(os.devnull, "w")
import numpy as np
import skimage
rng = np.random.RandomState(0)
rgb = rng.rand(32, 32, 3)
gray = rng.rand(32, 32)
binary = gray > 0.5
lab = (gray * 4).astype(int)
def get(path):
    import importlib
    m, f = path.rsplit(".", 1)
    return getattr(importlib.import_module(m), f)
CALLS = {
 "filters.gaussian(multichannel=)": lambda: get("skimage.filters.gaussian")(rgb, sigma=1, multichannel=True),
 "metrics.structural_similarity(multichannel=)": lambda: get("skimage.metrics.structural_similarity")(rgb, rgb, multichannel=True, data_range=1.0),
 "feature.hog(multichannel=)": lambda: get("skimage.feature.hog")(rgb, multichannel=True),
 "transform.rescale(multichannel=)": lambda: get("skimage.transform.rescale")(rgb, 0.5, multichannel=True),
 "transform.pyramid_gaussian(multichannel=)": lambda: list(get("skimage.transform.pyramid_gaussian")(rgb, max_layer=1, multichannel=True)),
 "segmentation.slic(multichannel=)": lambda: get("skimage.segmentation.slic")(rgb, n_segments=4, multichannel=True),
 "restoration.denoise_tv_chambolle(multichannel=)": lambda: get("skimage.restoration.denoise_tv_chambolle")(rgb, multichannel=True),
 "util.random_noise + color.rgb2gray": lambda: get("skimage.color.rgb2gray")(rgb),
 "morphology.binary_erosion(selem=)": lambda: get("skimage.morphology.binary_erosion")(binary, selem=np.ones((3, 3), bool)),
 "morphology.dilation(selem=)": lambda: get("skimage.morphology.dilation")(gray, selem=np.ones((3, 3))),
 "filters.median(selem=)": lambda: get("skimage.filters.median")(gray, selem=np.ones((3, 3))),
 "measure.label(neighbors=)": lambda: get("skimage.measure.label")(lab, neighbors=8),
 "measure.label(input=)": lambda: get("skimage.measure.label")(input=lab),
 "feature.peak_local_max(indices=)": lambda: get("skimage.feature.peak_local_max")(gray, indices=True),
 "morphology.remove_small_objects(in_place=)": lambda: get("skimage.morphology.remove_small_objects")(binary.copy(), 2, in_place=True),
 "morphology.remove_small_objects(min_size=)": lambda: get("skimage.morphology.remove_small_objects")(binary.copy(), min_size=2),
 "segmentation.watershed(image, markers) by position": lambda: get("skimage.segmentation.watershed")(gray, lab),
 "restoration.richardson_lucy(iterations=)": lambda: get("skimage.restoration.richardson_lucy")(gray, np.ones((3, 3)) / 9, iterations=2),
 "segmentation.active_contour(max_iterations=)": lambda: get("skimage.segmentation.active_contour")(gray, np.array([[5., 5.], [5., 20.], [20., 20.], [20., 5.]]), max_iterations=2),
 "feature.greycomatrix()": lambda: get("skimage.feature.greycomatrix")((gray * 7).astype(np.uint8), [1], [0], levels=8),
 "feature.graycomatrix()": lambda: get("skimage.feature.graycomatrix")((gray * 7).astype(np.uint8), [1], [0], levels=8),
 "measure.compare_ssim()": lambda: get("skimage.measure.compare_ssim")(gray, gray),
 "color.rgb2grey()": lambda: get("skimage.color.rgb2grey")(rgb),
 "morphology.selem.disk()": lambda: get("skimage.morphology.selem.disk")(1),
 "draw.circle()": lambda: get("skimage.draw.circle")(5, 5, 2),
 "filters.gaussian(output=)": lambda: get("skimage.filters.gaussian")(gray, sigma=1, output=np.empty_like(gray)),
 "io.imread(as_grey=)": lambda: (get("skimage.io.imsave")("t.png", (rgb * 255).astype(np.uint8)), get("skimage.io.imread")("t.png", as_grey=True))[1],
}
NEW = {   # the spelling newer releases want
 "filters.gaussian(channel_axis=)": lambda: get("skimage.filters.gaussian")(rgb, sigma=1, channel_axis=-1),
 "metrics.structural_similarity(channel_axis=)": lambda: get("skimage.metrics.structural_similarity")(rgb, rgb, channel_axis=-1, data_range=1.0),
 "feature.hog(channel_axis=)": lambda: get("skimage.feature.hog")(rgb, channel_axis=-1),
 "transform.rescale(channel_axis=)": lambda: get("skimage.transform.rescale")(rgb, 0.5, channel_axis=-1),
 "transform.pyramid_gaussian(channel_axis=)": lambda: list(get("skimage.transform.pyramid_gaussian")(rgb, max_layer=1, channel_axis=-1)),
 "segmentation.slic(channel_axis=)": lambda: get("skimage.segmentation.slic")(rgb, n_segments=4, channel_axis=-1),
 "restoration.denoise_tv_chambolle(channel_axis=)": lambda: get("skimage.restoration.denoise_tv_chambolle")(rgb, channel_axis=-1),
 "morphology.binary_erosion(footprint=)": lambda: get("skimage.morphology.binary_erosion")(binary, footprint=np.ones((3, 3), bool)),
 "morphology.dilation(footprint=)": lambda: get("skimage.morphology.dilation")(gray, footprint=np.ones((3, 3))),
 "filters.median(footprint=)": lambda: get("skimage.filters.median")(gray, footprint=np.ones((3, 3))),
 "measure.label(connectivity=)": lambda: get("skimage.measure.label")(lab, connectivity=2),
 "measure.label(label_image=)": lambda: get("skimage.measure.label")(label_image=lab),
 "feature.peak_local_max() without indices": lambda: get("skimage.feature.peak_local_max")(gray),
 "morphology.remove_small_objects(out=)": lambda: get("skimage.morphology.remove_small_objects")(binary.copy(), 2, out=np.empty_like(binary)),
 "morphology.remove_small_objects(max_size=)": lambda: get("skimage.morphology.remove_small_objects")(binary.copy(), max_size=1),
 "restoration.richardson_lucy(num_iter=)": lambda: get("skimage.restoration.richardson_lucy")(gray, np.ones((3, 3)) / 9, num_iter=2),
 "segmentation.active_contour(max_num_iter=)": lambda: get("skimage.segmentation.active_contour")(gray, np.array([[5., 5.], [5., 20.], [20., 20.], [20., 5.]]), max_num_iter=2),
 "filters.gaussian(out=)": lambda: get("skimage.filters.gaussian")(gray, sigma=1, out=np.empty_like(gray)),
 "io.imread(as_gray=)": lambda: (get("skimage.io.imsave")("t.png", (rgb * 255).astype(np.uint8)), get("skimage.io.imread")("t.png", as_gray=True))[1],
 "metrics.structural_similarity()": lambda: get("skimage.metrics.structural_similarity")(gray, gray, data_range=1.0),
 "metrics.peak_signal_noise_ratio()": lambda: get("skimage.metrics.peak_signal_noise_ratio")(gray, gray * 0.9, data_range=1.0),
 "color.rgb2gray()": lambda: get("skimage.color.rgb2gray")(rgb),
 "draw.disk()": lambda: get("skimage.draw.disk")((5, 5), 2),
 "morphology.disk()": lambda: get("skimage.morphology.disk")(1),
 "registration.phase_cross_correlation()": lambda: get("skimage.registration.phase_cross_correlation")(gray, gray),
 "measure.marching_cubes()": lambda: get("skimage.measure.marching_cubes")(rng.rand(8, 8, 8), 0.5),
 "graph.rag_mean_color()": lambda: get("skimage.graph.rag_mean_color")(rgb, lab),
 "feature.graycoprops()": lambda: get("skimage.feature.graycoprops")(get("skimage.feature.graycomatrix")((gray * 7).astype(np.uint8), [1], [0], levels=8), "contrast"),
 "exposure.match_histograms()": lambda: get("skimage.exposure.match_histograms")(gray, gray),
 "segmentation.watershed()": lambda: get("skimage.segmentation.watershed")(gray, lab),
 "morphology.skeletonize() on 3-D": lambda: get("skimage.morphology.skeletonize")(rng.rand(6, 6, 6) > 0.5),
 "feature.plot_matched_features exists": lambda: get("skimage.feature.plot_matched_features"),
 "filters.filter_inverse exists": lambda: get("skimage.filters.filter_inverse"),
}
CALLS.update({"feature.greycoprops()": lambda: get("skimage.feature.greycoprops")(get("skimage.feature.greycomatrix")((gray * 7).astype(np.uint8), [1], [0], levels=8), "contrast"),
              "measure.compare_psnr()": lambda: get("skimage.measure.compare_psnr")(gray, gray * 0.9),
              "feature.register_translation()": lambda: get("skimage.feature.register_translation")(gray, gray),
              "measure.marching_cubes_lewiner()": lambda: get("skimage.measure.marching_cubes_lewiner")(rng.rand(8, 8, 8), 0.5),
              "morphology.watershed()": lambda: get("skimage.morphology.watershed")(gray, lab),
              "future.graph.rag_mean_color()": lambda: get("skimage.future.graph.rag_mean_color")(rgb, lab),
              "morphology.skeletonize_3d()": lambda: get("skimage.morphology.skeletonize_3d")(rng.rand(6, 6, 6) > 0.5),
              "util.pad()": lambda: get("skimage.util.pad")(gray, 1, mode="constant")})
u8 = (gray * 255).astype(np.uint8)
vol = rng.rand(8, 8, 8)
pts = rng.rand(20, 2)
CALLS.update({
 "segmentation.slic(max_iter=)": lambda: get("skimage.segmentation.slic")(rgb, n_segments=4, max_iter=2),
 "filters.threshold_minimum(max_iter=)": lambda: get("skimage.filters.threshold_minimum")(np.concatenate([gray * 0.2, 0.8 + gray * 0.2]), max_iter=10000),
 "morphology.flood_fill(inplace=)": lambda: get("skimage.morphology.flood_fill")(lab.copy(), (0, 0), 9, inplace=True),
 "measure.regionprops(coordinates=)": lambda: get("skimage.measure.regionprops")(lab, coordinates="rc"),
 "filters.frangi(beta1=)": lambda: get("skimage.filters.frangi")(gray, beta1=0.5),
 "transform.warp_polar(multichannel=)": lambda: get("skimage.transform.warp_polar")(rgb, multichannel=True),
 "morphology.remove_small_holes(in_place=)": lambda: get("skimage.morphology.remove_small_holes")(binary.copy(), 2, in_place=True),
 "filters.rank.mean(selem=)": lambda: get("skimage.filters.rank.mean")(u8, selem=np.ones((3, 3), np.uint8)),
 "util.montage(multichannel=)": lambda: get("skimage.util.montage")(np.stack([rgb, rgb]), multichannel=True),
 "measure.ransac(random_state=)": lambda: get("skimage.measure.ransac")(pts, get("skimage.measure.LineModelND"), 2, 1, random_state=0),
 "feature.canny(mask=) control": lambda: get("skimage.feature.canny")(gray, mask=np.ones_like(binary)),
})


def dig(x):
    import hashlib
    if isinstance(x, np.ndarray):
        return "%s %s %s" % (x.shape, x.dtype, hashlib.sha1(np.ascontiguousarray(x).tobytes()).hexdigest()[:12])
    if isinstance(x, (tuple, list)):
        return [dig(y) for y in x]
    if hasattr(x, "edges") and hasattr(x, "nodes"):
        return dig(np.array(sorted((min(a, b), max(a, b), round(float(d.get("weight", 0)), 9)) for a, b, d in x.edges(data=True))))
    if isinstance(x, (float, np.floating)):
        return repr(float(x))
    return repr(x)


g2 = np.clip(gray * 0.9 + 0.05, 0, 1)
psf = np.ones((3, 3)) / 9
EQ = {   # old spelling, new spelling: same input, results compared by digest
 "gaussian multichannel=True | channel_axis=-1": (lambda: get("skimage.filters.gaussian")(rgb, sigma=1, multichannel=True), lambda: get("skimage.filters.gaussian")(rgb, sigma=1, channel_axis=-1)),
 "gaussian multichannel=False | channel_axis=None": (lambda: get("skimage.filters.gaussian")(rgb, sigma=1, multichannel=False), lambda: get("skimage.filters.gaussian")(rgb, sigma=1, channel_axis=None)),
 "rescale multichannel=True | channel_axis=-1": (lambda: get("skimage.transform.rescale")(rgb, 0.5, multichannel=True), lambda: get("skimage.transform.rescale")(rgb, 0.5, channel_axis=-1)),
 "structural_similarity multichannel=True | channel_axis=-1": (lambda: get("skimage.metrics.structural_similarity")(rgb, rgb[::-1], multichannel=True, data_range=1.0), lambda: get("skimage.metrics.structural_similarity")(rgb, rgb[::-1], channel_axis=-1, data_range=1.0)),
 "binary_erosion selem= | footprint=": (lambda: get("skimage.morphology.binary_erosion")(binary, selem=np.ones((3, 3), bool)), lambda: get("skimage.morphology.binary_erosion")(binary, footprint=np.ones((3, 3), bool))),
 "dilation selem= | footprint=": (lambda: get("skimage.morphology.dilation")(gray, selem=np.ones((3, 3))), lambda: get("skimage.morphology.dilation")(gray, footprint=np.ones((3, 3)))),
 "rank.mean selem= | footprint=": (lambda: get("skimage.filters.rank.mean")(u8, selem=np.ones((3, 3), np.uint8)), lambda: get("skimage.filters.rank.mean")(u8, footprint=np.ones((3, 3), np.uint8))),
 "draw.circle(5, 5, 2) | draw.disk((5, 5), 2)": (lambda: get("skimage.draw.circle")(5, 5, 2), lambda: get("skimage.draw.disk")((5, 5), 2)),
 "label neighbors=8 | connectivity=2": (lambda: get("skimage.measure.label")(lab, neighbors=8), lambda: get("skimage.measure.label")(lab, connectivity=2)),
 "label neighbors=4 | connectivity=1": (lambda: get("skimage.measure.label")(lab, neighbors=4), lambda: get("skimage.measure.label")(lab, connectivity=1)),
 "richardson_lucy iterations=2 | num_iter=2": (lambda: get("skimage.restoration.richardson_lucy")(gray, psf, iterations=2), lambda: get("skimage.restoration.richardson_lucy")(gray, psf, num_iter=2)),
 "measure.compare_ssim | metrics.structural_similarity": (lambda: get("skimage.measure.compare_ssim")(gray, g2), lambda: get("skimage.metrics.structural_similarity")(gray, g2)),
 "measure.compare_psnr | metrics.peak_signal_noise_ratio": (lambda: get("skimage.measure.compare_psnr")(gray, g2), lambda: get("skimage.metrics.peak_signal_noise_ratio")(gray, g2)),
 "measure.compare_mse | metrics.mean_squared_error": (lambda: get("skimage.measure.compare_mse")(gray, g2), lambda: get("skimage.metrics.mean_squared_error")(gray, g2)),
 "measure.compare_nrmse | metrics.normalized_root_mse": (lambda: get("skimage.measure.compare_nrmse")(gray, g2), lambda: get("skimage.metrics.normalized_root_mse")(gray, g2)),
 "color.rgb2grey | color.rgb2gray": (lambda: get("skimage.color.rgb2grey")(rgb), lambda: get("skimage.color.rgb2gray")(rgb)),
 "color.grey2rgb | color.gray2rgb": (lambda: get("skimage.color.grey2rgb")(gray), lambda: get("skimage.color.gray2rgb")(gray)),
 "feature.greycomatrix | feature.graycomatrix": (lambda: get("skimage.feature.greycomatrix")(u8 // 32, [1], [0], levels=8), lambda: get("skimage.feature.graycomatrix")(u8 // 32, [1], [0], levels=8)),
 "feature.greycoprops | feature.graycoprops": (lambda: get("skimage.feature.greycoprops")(get("skimage.feature.greycomatrix")(u8 // 32, [1], [0], levels=8), "contrast"), lambda: get("skimage.feature.graycoprops")(get("skimage.feature.graycomatrix")(u8 // 32, [1], [0], levels=8), "contrast")),
 "morphology.watershed | segmentation.watershed": (lambda: get("skimage.morphology.watershed")(gray, lab), lambda: get("skimage.segmentation.watershed")(gray, lab)),
 "util.pad | numpy.pad": (lambda: get("skimage.util.pad")(gray, 1, mode="constant"), lambda: np.pad(gray, 1, mode="constant")),
 "feature.register_translation | registration.phase_cross_correlation": (lambda: get("skimage.feature.register_translation")(gray, np.roll(gray, 3, axis=0)), lambda: get("skimage.registration.phase_cross_correlation")(gray, np.roll(gray, 3, axis=0))),
 "measure.marching_cubes_lewiner | measure.marching_cubes": (lambda: get("skimage.measure.marching_cubes_lewiner")(vol, 0.5), lambda: get("skimage.measure.marching_cubes")(vol, 0.5)),
 "morphology.skeletonize_3d | morphology.skeletonize": (lambda: get("skimage.morphology.skeletonize_3d")(vol > 0.5), lambda: get("skimage.morphology.skeletonize")(vol > 0.5)),
 "transform.match_histograms | exposure.match_histograms": (lambda: get("skimage.transform.match_histograms")(gray, g2), lambda: get("skimage.exposure.match_histograms")(gray, g2)),
 "future.graph.rag_mean_color | graph.rag_mean_color": (lambda: get("skimage.future.graph.rag_mean_color")(rgb, lab), lambda: get("skimage.graph.rag_mean_color")(rgb, lab)),
 "morphology.selem.disk(2) | morphology.disk(2)": (lambda: get("skimage.morphology.selem.disk")(2), lambda: get("skimage.morphology.disk")(2)),
 "feature.structure_tensor_eigvals | feature.structure_tensor_eigenvalues": (lambda: get("skimage.feature.structure_tensor_eigvals")(*get("skimage.feature.structure_tensor")(gray, sigma=1)), lambda: get("skimage.feature.structure_tensor_eigenvalues")(get("skimage.feature.structure_tensor")(gray, sigma=1))),
 "gaussian output= | out=": (lambda: get("skimage.filters.gaussian")(gray, sigma=1, output=np.empty_like(gray)), lambda: get("skimage.filters.gaussian")(gray, sigma=1, out=np.empty_like(gray))),
 "external.tifffile.imread | tifffile.imread": (lambda: (get("skimage.io.imsave")("e.tif", u8), get("skimage.external.tifffile.imread")("e.tif"))[1], lambda: (get("skimage.io.imsave")("e.tif", u8), __import__("tifffile").imread("e.tif"))[1]),
}
eq = {}
for label, (fo, fn) in EQ.items():
    r = {}
    for side, f in (("old", fo), ("new", fn)):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                r[side] = dig(f())
            except Exception as e:
                r[side] = "ERR %s: %s" % (type(e).__name__, " ".join(str(e).split())[:160])
    eq[label] = r
out = {}
for label, f in list(CALLS.items()) + list(NEW.items()):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            f()
            msgs = [" ".join(str(x.message).split()) for x in w if issubclass(x.category, (FutureWarning, DeprecationWarning, UserWarning)) and "skimage" in (x.filename or "") or "deprecat" in str(x.message).lower()]
            out[label] = {"ok": True, "warn": msgs[0][:400] if msgs else ""}
        except Exception as e:
            out[label] = {"ok": False, "error": "%s: %s" % (type(e).__name__, " ".join(str(e).split())[:300])}
import importlib.util
json.dump({"skimage": skimage.__version__, "calls": out, "old": sorted(CALLS), "new": sorted(NEW), "eq": eq,
           "deps": {m: importlib.util.find_spec(m) is not None for m in ("tifffile", "matplotlib", "imageio", "pooch", "networkx", "lazy_loader")}}, REAL, indent=0)
