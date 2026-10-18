# Private training lifecycle proof

Candidate `92612aa206d1d546e1c8b515e55499a9108d0449`. Production images use committed source archives; their source hashes/image IDs/revisions were read after owned teardown and are identified as such.

The actual existing maintenance CLI created a backup, restored it offline with the fixture clock, produced a new API epoch and passed its integrity check. A post-backup write was removed by the explicit restore; the earlier sentinel and eight prerequisites remained. The real reset CLI retained the old private volumes, stopped its running disposable import destination, and started a fresh sibling root with a new store/namespace and only eight prerequisites. Restarting the old root recovered its nine exact record IDs and restored epoch. The separate destination had an actual saved Operator sentinel before parent reset removed its disposable runtime/data.

The prior caddcd17 run reached successful CLI restore but its harness JSON parser included Compose progress lines; an observed failing regression and last-line result parser corrected that harness issue. Both runs cleaned all owned containers/networks/disposable volumes. The old root and evidence remain on disk; no operational root, shared runtime or credentials were mounted or changed.

This proves reset/backup/restore/isolation and destination teardown, not archive ZIP/PDF contents or ordinary mission-import preservation. Those full T10 checks, failure curriculum, full parity/manual/quick reference and uncoached human sessions remain required.
