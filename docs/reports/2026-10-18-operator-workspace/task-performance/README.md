# Original and candidate task comparison

Original runtime: 1a3e77d3b4017ad1f7cb33d1b1ef20b9378e0244 from a separate clean
checkout. Candidate and identical browser harness:
679a5c1f24088e4d185338a7e88ad6415e661598. Image/source/harness identities and
actual request timings are retained. Runs were sequential on the same machine
after display cleanup.

Both passed 48 measurements: eight matching outcomes across normal/busy missions
and three sizes. Ordinary tasks had a five-second budget; response-loss recovery
had ten seconds. Writes required actual acknowledgments. Recovery lost the
response after actual commit, then verified the original request/receipt and one
immutable revision. Ready inline baseline forms were reused without unnecessary
reset clicks.

| Task                                     | Baseline median ms | Candidate median ms | Change ms | Baseline clicks | Candidate clicks |
| ---------------------------------------- | -----------------: | ------------------: | --------: | --------------: | ---------------: |
| Create planned call                      |                192 |                 412 |      +219 |               1 |                2 |
| Reschedule same call                     |                230 |                 521 |      +291 |               3 |                5 |
| Inspect original and replacement history |                109 |                 315 |      +206 |               2 |                2 |
| Log mission note                         |                181 |                 505 |      +325 |               1 |                2 |
| Log issue                                |                147 |                 448 |      +301 |               1 |                3 |
| Resolve issue                            |                158 |                  94 |       -64 |               1 |                1 |
| Change shared display history window     |                167 |                 592 |      +425 |               2 |              2–3 |
| Recover response loss with exact retry   |                336 |                 541 |      +206 |               3 |                4 |

The candidate is not a generic speed improvement: contextual editors, navigation
and parking add activations to some sequential tasks. The existing 200ms dialog
transition also contributes to open/close waits; this is a
source/trace-supported explanation, not human timing. Display closure records
Escape separately. Full edits/selectors/keypresses and request timings remain in
raw reports. Human discovery, mis-selections and typing time are unmeasured.

Nine candidate native accessibility-tree audits of
Overview/Missions/Configuration checked 175 controls with no unnamed interactive
controls. Operator awareness/editor naming and keyboard focus were separately
accepted. Physical keyboard, screen-reader and contrast usability are not
certified.

Both runners removed containers, networks, volumes, images, source extractions,
workers and listeners. Independent host checks found no surviving owned groups;
ports 47253/59253 are free. Raw browser traces remain at the recorded evidence
roots. Idle CPU/render/polling profiles and retained-draft backout are separate
final checks.
