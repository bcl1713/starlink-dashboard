# Aviation weather Phase 2 presentation

The foundation merged in #294. Presentation adds conservative flight-level
ISA/log-pressure derivation, shared browser resource ownership, native globe
wind barbs and temperature, shared Configuration selection and passive UTC
context. Defaults stay off; issue #290 remains open for Phases 3–6.

Unit verification includes two-segment independent ISA values, real GRIB bracket
samples, conservative missing/terrain handling, immutable buffer sharing and
cancellation, maximum-range pennants, signed packing, projection conventions and
confirmed/failed Configuration saves. Task 3 passed 1,285 frontend tests, the
TypeScript/Vite production build and lint.

Production acceptance must bind a clean exact candidate SHA to three no-cache
images and the provisioned browser. It runs real worker acquisition/decoding,
publication, API/Nginx and native rendering. Only NOAA transport and labelled
replay time are fixtures. Captured 2026-10-06 00Z F006/F009 GRIB ranges and hashes
are pinned in `tools/acceptance/gfs-weather/presentation-source.json`; FL390 uses
the actual complete 150/200 hPa brackets. Independent source values compare to
admitted CPU arrays and native packed-shader U/V/T readback, including seam,
poles and terrain. Browser controls cover Configuration propagation between
independent contexts, horizon changes, combined radar/bulletin views and original
expiry despite failed polling. All pass controls, resource measurements and
empty cleanup inventory are required before PASS is written.

Evidence is software SwiftShader and historical source replay. Deployment GPU,
minimum-host performance and live NOAA availability remain separate deployment
validation. An unexecuted control or absent metric does not constitute acceptance.
The final exact-head artifact inventory, PR and measured results will be recorded
in the presentation handoff after the gate completes.
