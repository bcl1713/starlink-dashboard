# Idle profiles and retained-work backout

Original runtime: `1a3e77d3b4017ad1f7cb33d1b1ef20b9378e0244`. Candidate runtime and identical browser harness: `2837ddc0b174cb32e3e6e797c75117ba733f9a04`. Both ran sequentially on the same machine with production images, a busy synthetic mission, visible foreground pages and two real sixty-second samples each. Raw 10ms CPU profiles, CDP metrics, actual React commits, connected canvas frame counters and HTTP counts are retained.

| Page | Original thread CPU s | Candidate thread CPU s | Original commits | Candidate commits | Original frames | Candidate frames |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Operator | 0.196876 | 0.187616 | 8 | 8 | n/a | n/a |
| Overview | 6.298934 | 6.267939 | 2249 | 2195 | 1384 | 1390 |

No measured CPU increase exceeded the investigation threshold of ten percent. CDP TaskDuration includes renderer work and is not equivalent to thread CPU: Operator was 0.134842 to 0.112937 seconds; Overview 43.962956 to 43.952381. These single controlled samples do not establish physical-device or GPU performance. Operator polled health/events four times each, with no idle records, closed presets or per-row requests. Overview counts match exactly, including four shared health requests and no Operator event polling; other existing Overview polling is retained in raw reports.

Backout passed on desktop, portrait and landscape. A real native note committed before its response was dropped. Another note remained parked. Reloading the original shell retained both, exposed the explicit recovery link, and left the store and revision high-water mark unchanged. Following that link recovered the uncertain command with identical body, key, epoch and original receipt, exactly one immutable revision, and no duplicate. The separately parked note and its text remained recoverable. This is a whole-shell routing backout without database rewrite, not a destructive downgrade test. Restore/source-change quarantine has separate private-RC coverage.

Both runners removed their containers, networks, private volumes, images, source extraction, workers and listeners. Independent host checks found zero surviving owned groups and ports 47891/57409 free. Actual human mission, physical keyboard, screen reader and contrast checks remain pending; these automated results do not grant human acceptance or cutover authorization.
