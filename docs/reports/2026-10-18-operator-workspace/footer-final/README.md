# Persistent editor actions

The fresh review identified a minor mismatch with the approved fixed action
footer. Save and Discard now sit outside the scrolling editor body. Each Save
button uses the original form's native ID and submit handler, preserving HTML
validation, disabled state and the existing frozen-command owner. Original-shell
forms retain their own submit buttons. Capability and historical issue
correction keep their specific action labels.

A component assertion failed against the old layout, then passed after the fix;
304 Operator component assertions passed. Canonical frontend passed 2,057 tests
and production build at `9b07dbb48c6036c3c3c217dc46f88583eb682fdd`. The reviewer
inspected the small correction and found no further defect.

Production acceptance passes all six workspace cases at exact clean runtime
`de4994f7c62cd3c56f0716c9cf79c61bdb3f79ee` across normal/busy missions and
desktop, portrait and landscape. Save stays within the viewport before/after
body scrolling and at emulated 844 by 250 keyboard height. Real invalid/valid
submission, conference/customer, issue correction, capability, transport, paged
relationships, response-loss exact retry and offline retained input remain
covered.

The first run at `9b07dbb4` passed five cases but sampled footer geometry before
Chromium applied the resized dynamic viewport height: old bottom 377 versus
requested height 250. The corrected test waits for actual dialog height to equal
the requested viewport before retaining the identical strict footer bound. The
second run passes without a product workaround or relaxed geometry. Initial log
and failed evidence root remain retained; no failed result is counted as
accepted.

Both runs removed containers, networks, private volumes, images, workers,
extracted sources and listeners. Independent host checks found zero surviving
owned groups; ports are recorded in host-cleanup files. Physical keyboard and
screen-reader acceptance remain pending.
