"""Assemble index.html: head (meta, JSON-LD built from the FAQ in body.html) + the site's
page style (copied from an existing /en/ page) + body.html.
usage: python3 build_page.py <site checkout> body.html out.html
"""
import html, json, re, sys

site, body_path, out = sys.argv[1:4]
URL = "https://erimaki-kobo.github.io/en/context-overflow-error-status-check/"
TITLE = "Context Length Exceeded: Status Codes by LLM Engine"
DESC = ("What vLLM, SGLang, llama.cpp, Ollama, TGI and Dynamo return when a prompt is too long, "
        "which ones answer 200 or 500, and how openai-python and LiteLLM react.")
HEADLINE = ("Context length exceeded: what vLLM, SGLang, llama.cpp, Ollama, TGI and Dynamo return, "
            "and what openai-python and LiteLLM do with it")

ref = open(site + "/en/spec-decode-lossless-check/index.html", encoding="utf-8").read()
style = re.search(r"<style>.*?</style>", ref, re.S).group(0)
style = style.replace("</style>", ".tw table{min-width:760px}\ntd.ok{box-shadow:inset 3px 0 var(--ok)}td.bad{box-shadow:inset 3px 0 var(--bad)}td.warn{box-shadow:inset 3px 0 var(--warn)}\n</style>")
body = open(body_path, encoding="utf-8").read()


def text(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


faq = [{"@type": "Question", "name": text(q), "acceptedAnswer": {"@type": "Answer", "text": text(a)}}
       for q, a in re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", body, re.S)]
assert len(faq) == 5, len(faq)
org = {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": HEADLINE, "description": DESC, "url": URL,
     "datePublished": "2026-11-25", "dateModified": "2026-11-25", "inLanguage": "en", "author": org,
     "publisher": org, "mainEntityOfPage": URL},
    {"@type": "SoftwareSourceCode", "@id": URL + "#code", "name": "overflow_check.py",
     "description": "Sends over-long requests to an OpenAI-compatible server and reports the HTTP status, error "
                    "type and message, silent truncation, errors inside a 200 stream, and whether openai-python "
                    "retries and LiteLLM classifies the error as ContextWindowExceededError.",
     "programmingLanguage": "Python", "codeRepository": URL, "url": URL + "overflow_check.py", "version": "1.0.0",
     "license": "https://opensource.org/licenses/MIT", "isAccessibleForFree": True, "publisher": org},
    {"@type": "FAQPage", "@id": URL + "#faq", "mainEntity": faq},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers",
         "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": "Context length exceeded: status codes by engine", "item": URL}]}]}

head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}</title>
<meta name="description" content="{html.escape(DESC)}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="article">
<meta property="og:title" content="{TITLE}">
<meta property="og:description" content="{html.escape(DESC)}">
<meta property="og:url" content="{URL}">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
{style}
</head>
"""
open(out, "w", encoding="utf-8").write(head + body)
print("wrote", out, len((head + body).encode()), "bytes; title", len(TITLE), "chars; description", len(DESC))
