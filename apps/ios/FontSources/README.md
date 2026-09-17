# Farelin typography sources

The website and native app use Bricolage Grotesque (display), Hanken Grotesk
(body/controls), and JetBrains Mono (labels). These unmodified variable font
sources were obtained from the official Google Fonts repository on 2026-09-17:

- https://github.com/google/fonts/tree/main/ofl/bricolagegrotesque
- https://github.com/google/fonts/tree/main/ofl/hankengrotesk
- https://github.com/google/fonts/tree/main/ofl/jetbrainsmono

SIL Open Font License notices are included in `../Farelin/Resources/Fonts` and
bundled in the app. Sources live here for reproducibility and the local website
concept; they are not copied into the app bundle. Native weights are generated
static instances, not hand-drawn substitutes. Bricolage uses regular width and
optical size 32. Native rendering/optical sizing can differ slightly from web.

To regenerate in an isolated Python environment with `fonttools==4.60.0`, run:

```sh
python apps/ios/scripts/build_font_instances.py
/usr/bin/ruby apps/ios/scripts/sync_project.rb
```

Regular, Medium, SemiBold, Bold and ExtraBold instances for each family are
registered through UIAppFonts. `FarelinTypography` chooses explicit names and
semantic scaling. Generated files are checked in: runtime and CI do not need
fontTools or network font access. Keep license notices alongside any redistribution.
