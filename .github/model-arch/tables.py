#!/usr/bin/env python3
"""Render the three data tables of en/model-arch-min-version from data.json (used by build_page.py)."""
import html, re

e = html.escape
STATUS = {"n": lambda v: "native", "p": lambda v: "removed (last %s)" % v[2], "g": lambda v: "gone (last %s)" % v[2],
          "t": lambda v: "Transformers backend (native to %s)" % v[2] if v[2] else "Transformers backend", "o": lambda v: "plugin"}
# h2g[class] = [arch, converter build or None, date]: None where the converter's registration predates b2700
# (those are refactoring dates, not support dates).


def gguf_cell(D, cls):
    if cls not in D["h2g"]:
        return ""
    arch, cb, _ = D["h2g"][cls]
    s = "<code>%s</code> b%s" % (e(arch), D["gg"][arch][0])
    if cb and int(cb) > int(D["gg"][arch][0]):
        s += ", converter b%s" % cb
    return s


def tft_rows(D):
    return "\n".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        e(k), v[0], D["dates"][v[0]], "removed after %s" % v[1] if v[1] else "") for k, v in sorted(D["tf"].items()))


def vlt_rows(D):
    return "\n".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        e(k), v[0] or "&mdash;", STATUS[v[1]](v), "<code>%s</code>" % e(D["a2m"][k]) if k in D["a2m"] else "", gguf_cell(D, k))
        for k, v in sorted(D["vl"].items()))


def fam_cells(D, mt, cls, vl_name=None):
    """Cells 3 and 5-9 of a family row (cells 1, 2 and 4 are the curated family, model_type and class).
    vl_name: the name vLLM registers when it is not the Transformers class name."""
    tf = D["tf"][mt]
    c3 = "%s (%s)" % (tf[0], D["dates"][tf[0]])
    v = D["vl"].get(vl_name or cls)
    if v is None:
        c5, c6 = "no native class", "see the Transformers backend note"
    else:
        c5 = "%s (%s)" % (v[0], D["dates"][v[0]])
        c6 = "native" if v[1] == "n" else {"t": "Transformers backend", "p": "removed", "g": "gone"}[v[1]] + " after %s" % v[2]
        if vl_name:
            c5 += " as <code>%s</code>" % e(vl_name)
    arch, cb, cd = D["h2g"][cls]
    g = D["gg"][arch]
    c7 = "<code>%s</code> b%s (%s)" % (e(arch), g[0], g[1])
    c8 = "b%s (%s)" % (cb, cd) if cb else "&mdash;"
    return c3, c5, c6, c7, c8, g[2] or "&mdash;"


def replace_tbody(page, table_id, rows):
    a = page.index('<table id="%s">' % table_id)
    b = page.index("<tbody>\n", a) + len("<tbody>\n")
    c = page.index("\n</tbody>", b)
    return page[:b] + rows + page[c:], page[b:c]
