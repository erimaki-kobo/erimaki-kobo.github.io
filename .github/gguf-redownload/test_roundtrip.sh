#!/usr/bin/env bash
# patch a.gguf into b.gguf's metadata with the commands the page prints; test_parser.mjs then checks a3.gguf
set -e
printf '%s' '{{ x }} fixed' > t.jinja
gguf-new-metadata --force a.gguf a3.gguf --chat-template-file t.jinja
gguf-set-metadata --force a3.gguf tokenizer.ggml.add_bos_token ''
