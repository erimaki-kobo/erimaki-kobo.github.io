"""Labels the replay self-test cannot reach (no parser output produces them): call in reasoning, schema mismatch,
finish_reason, stream header. usage: python3 -I test_toolcheck.py <path to toolcheck.py>"""
import importlib.util, sys
spec = importlib.util.spec_from_file_location("toolcheck", sys.argv[1]); tc = importlib.util.module_from_spec(spec); spec.loader.exec_module(tc)
C = lambda n, a: {"id": "x", "type": "function", "function": {"name": n, "arguments": a}}
cases = [
    ({"content": "", "reasoning": "hm <tool_call>\n<function=get_weather>", "tool_calls": []}, "stop", False, [], "call_in_reasoning"),
    ({"content": "", "reasoning_content": "<tool_call>{\"name\": \"get_weather\"}", "tool_calls": []}, "stop", False, [], "call_in_reasoning"),
    ({"content": None, "tool_calls": []}, "stop", False, [], "empty"),
    ({"content": "It is sunny.", "tool_calls": []}, "stop", False, [], "no_call"),
    ({"content": "[get_weather(city='Tokyo')]", "tool_calls": []}, "stop", False, [], "markup_in_content"),
    ({"content": None, "tool_calls": [C("get_weather", '{"days": 3}')]}, "tool_calls", False, [], "schema_mismatch"),
    ({"content": None, "tool_calls": [C("get_weather", '{"city": "Tokyo", "days": "3"}')]}, "tool_calls", False, [], "schema_mismatch"),
    ({"content": None, "tool_calls": [C("get_weather", '{"city": "Tokyo"')]}, "tool_calls", False, [], "bad_json"),
    ({"content": None, "tool_calls": [C("get_weather", '{"city": "Tokyo"}')]}, "stop", False, [], "finish_reason"),
    ({"content": None, "tool_calls": [C("get_weather", '{"city": "Tokyo"}')]}, "tool_calls", True, [], "finish_reason"),
    ({"content": None, "tool_calls": [C("get_weather", '{"city": "Tokyo"}')]}, "length", True, [], "ok"),
    ({"content": None, "tool_calls": [C("get_weather", '{"city": "Tokyo"}')]}, "tool_calls", False, ["call 0: first chunk has id=None name='get_weather'"], "stream_header"),
    ({"content": None, "tool_calls": [C("get_weather", '{"city": "Tokyo", "days": 3}')]}, "tool_calls", False, [], "ok"),
]
bad = 0
for msg, fin, cut, probs, want in cases:
    got = tc.verdict(msg, fin, cut, probs)[0]
    if got != want:
        bad += 1; print("FAIL", want, got, msg)
m, f, p = tc.merge_stream([{"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "get_weather", "arguments": "{\"ci"}}]}}]},
                           {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "ty\": \"Tokyo\"}"}}]}, "finish_reason": "tool_calls"}]}])
if not p or m["tool_calls"][0]["function"]["arguments"] != '{"city": "Tokyo"}':
    bad += 1; print("FAIL merge", m, p)
print("FAILED %d" % bad if bad else "ALL PASS (%d labels, stream merge)" % len(cases))
sys.exit(1 if bad else 0)
