"""Coordinated limits for one bounded customer PDF preparation worker."""

RENDER_SECONDS = 120
RENDER_MILLISECONDS = RENDER_SECONDS * 1000
# The emergency supervisor leaves time for the renderer's owned-tree cleanup.
RENDER_WALL_SECONDS = RENDER_SECONDS + 10
# Captured input preparation runs before Node in the outer owned Python child.
SLIDE_WALL_SECONDS = RENDER_WALL_SECONDS + 50
