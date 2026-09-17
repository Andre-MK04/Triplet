# App-inspired website concept

This is an isolated visual exploration, not a replacement for `apps/web`.
It translates Farelin's restored native design into rounded web cards, pill
controls, a floating navigation bar, softer surfaces and restrained feedback.
The actual website font families are shared through local font assets.

Serve the repository root (not this directory), for example:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
```

Then open http://127.0.0.1:8766/design/previews/farelin-native-web.html.
Screenshots in `screenshots` show dark/light desktop and mobile layouts.

Try the theme switch, Explore/Ask mode, mood chips, demo bookmark and trip
sheet. All fares, fit scores and watch content are fictional examples. Search
does not call AI/providers; bookmarks do not save to an account. Navigation
links point to concept sections, not production account pages.

The globe uses the existing native Natural Earth geometry in a local Canvas
projection. Drag/touch or arrow keys rotate it; rotation can be paused.
It is a lightweight design preview, not the native SceneKit globe or a promise
to replace the website's existing renderer. Reduced Motion stops auto-rotation
and interaction transitions. Responsive overflow checks passed at 360, 390,
768, 1024 and 1440px. No production deployment is part of this exploration.
