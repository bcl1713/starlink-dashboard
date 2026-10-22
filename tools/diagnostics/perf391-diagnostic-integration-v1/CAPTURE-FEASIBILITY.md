# Forge passive capture feasibility — read-only Stage 3A assessment

Assessed 2026-10-22 as `oracle-worker` (UID 1002). No packet socket was opened,
no packets or application HTTP requests were collected, and no privilege,
network, Nginx, Docker or service configuration was changed. This is a
conditional feasibility assessment, not Stage 3B implementation or runtime
qualification.

## Observed permissions and topology

Read-only host commands preserved the actor Docker configuration and active
`default` context. `docker info` reached the configured
`unix:///run/user/1002/docker.sock`: Docker 29.8.1, rootless, cgroup namespaces,
builtin seccomp. `docker ps` returned no running containers for this actor. The
sandbox cannot reach this socket; that failure is not daemon downtime. Host and
sandbox have different network/PID visibility.

`tcpdump --version` reports tcpdump 4.99.6 and libpcap 1.10.6, TPACKET_V3.
`getcap /usr/bin/tcpdump` returned no file capabilities. Host `capsh --print`
reports **empty effective and ambient capability sets** for this user.
CAP_NET_RAW/CAP_NET_ADMIN in the bounding set do not grant them to this process.
An ordinary libpcap packet socket therefore has no demonstrated authorization;
no capture attempt, sudo, setcap, group change or permission request was made.
No already authorized narrow capture helper is established by this assessment.

The host has other listeners, including addresses on `10.10.50.30`; none belongs
to this task and none was contacted. There is no task-owned frontend listener.
The exact future loopback port, interface, connection four-tuple, HTTP version,
cleartext hop and rootless forwarding visibility **cannot be confirmed without
the later separately authorized deployment/preflight**. Absence of a running
task stack makes the requested actual cleartext HTTP/1.1 capture point
unavailable today. Do not assume a rootless container's loopback is host `lo`.

## Static application evidence and encodings

Exact A/C frontend Nginx source is identical: `listen 80`, same-origin `/api/`
proxy to `http://starlink-location:8000`, gzip enabled for application/json,
minimum gzip length 1024, no TLS or HTTP/2 listener in that file. This supports
a possible cleartext browser-to-published-frontend hop; it does not establish
the actual Forge exposure path, HTTP protocol negotiated by a browser, outer
TLS, service worker/cache bypass or the network namespace where a tap would see
it. Keep Nginx gzip and the original browser/Axios transport unchanged.

A later bounded parser would need identity and gzip decoding after correct
HTTP/1.1 framing (Content-Length, chunked with extensions/trailers, or complete
connection-close). Python zlib is available for bounded incremental gzip;
CRC/EOF, truncation, conflicts and size limits still require implementation and
fixtures. This stage implements no parser or decoder. Brotli, other encodings,
TLS, HTTP/2 multiplexing, cache/service-worker served bodies, an invisible
forwarding hop and ambiguous framing remain unavailable. Do not treat a
compressed Content-Length as a decoded-size bound.

## Conditional later approach and limitations

Stage 3B must first establish an already approved narrow capture mechanism and
an exclusive synthetic loopback listener visible in the selected namespace. Use
the approved plan's exact-address/port BPF, 65535 snaplen, 4 MiB kernel buffer,
8 MiB queue, 64 MiB pcap ceiling, 32 connections/16 bodies, 2 MiB encoded and
decoded entity limits, 64 KiB working chunks/headers and 2 s body deadline. Stop
on loss, overflow, incomplete handshake/framing or unsupported encoding. Zero
observed drops must come from final capture statistics; missing statistics are
unknown. Budget the tap's CPU/storage impact separately in future calibration.
Never widen the filter, capture shared listeners or rotate away unfavorable
evidence.

Join Page Request object/diagnostic ID, captured HTTP request/paired response,
backend ASGI ID and actual parsed frontend object using content evidence. A
server-transmitted body is insufficient if the browser request failed. Packet
bytes do not reveal browser-native parse start or physical display scanout.

**Current result: capture is unavailable and not runtime-qualified.** Native
libraries exist, but effective capture permission and an actual task-specific
cleartext HTTP/1.1 topology are unverified/unavailable. Stage 3B needs its own
checkpoint. No fallback to Playwright/CDP whole-body APIs, request interception,
compression changes, Nginx modifications or unrestricted browser-body capture.
