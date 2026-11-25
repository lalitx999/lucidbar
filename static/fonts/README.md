# Fonts

Self-hosted fonts referenced by `static/css/lucid.css`. No external font CDN is used.

| File | Font | Source | License |
|---|---|---|---|
| `Montserrat-Variable.woff2` | Montserrat, variable weight, Latin subset | `@fontsource-variable/montserrat` 5.3.0 (`montserrat-latin-wght-normal.woff2`) | SIL OFL 1.1, see `Montserrat-OFL.txt` |
| `Cinzel-Variable.woff2` | Cinzel, variable weight, Latin subset | `@fontsource-variable/cinzel` 5.3.0 (`cinzel-latin-wght-normal.woff2`) | SIL OFL 1.1, see `Cinzel-OFL.txt` |

The Latin subset covers English. Neither font has Thai glyphs, so Thai text
uses the system font; add a Thai font here when the Thai translation lands.

The service worker precaches these files automatically when they exist.
