# Optional Geographic Boundaries

On **Configuration → Overview → Geographic boundaries**, use **Country borders**
and **State/province borders** independently. Both are off by default. Saved
settings apply to all Overview displays and reach an already-open display on its
next five-second settings refresh, including fullscreen, without a reload or
active mission. A failed save leaves the last confirmed preference in place.

Country borders show international land boundaries and coastlines, including
major islands, with the same stroke and switch. State/province borders show
worldwide subdivisions where the bundled Natural Earth dataset supplies them.
Thin contrasting strokes remain below the aircraft, route and satellite
presentation. Dashed lines identify source-classified disputed or uncertain
borders. The legend identifies loaded layers; loading or unavailable messages
apply only to the optional layer. Disable both switches to restore the usual
globe presentation.

Boundary data ships with the frontend and does not require external network
access at runtime. It is generalized reference data, with incomplete coverage
and no guarantee of current political boundaries. See
[dataset provenance, license and disputed-boundary treatment](../../frontend/mission-planner/public/boundaries/ATTRIBUTION.md).

To repeat isolated production Docker/Nginx/browser verification, commit the
candidate and run `tools/acceptance/overview-boundaries/run.sh`. It uses the
configured Docker daemon, task-owned volumes, and loopback ports 15282/18282,
then removes its containers, volumes and temporary source archive. Evidence
stays in `.superpowers/sdd/overview-boundaries/<candidate SHA>/`. Browser
controls cover default off, cross-window saves, independent toggles, cache
reuse, GPU cleanup, desktop/fullscreen/mobile views and explicitly intercepted
missing or malformed optional assets. This focused runner is separate from the
generic acceptance platform's final authority.
