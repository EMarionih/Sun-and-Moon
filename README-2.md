# Sun & Moon

A sun and a moon, drawn entirely out of text characters, crash into each other in a Python window.

The glowing orange sun and the blue moon drift together, collide into one blended blob (hot pink and white where they overlap, with sparks), then pull apart and repeat, all over a field of twinkling stars. There are no images and no graphics libraries: every pixel on screen is a keyboard character picked by how bright that spot should be.

<!-- Add a screen recording named demo.gif to the repo, then uncomment the next line: -->
<!-- ![Sun & Moon demo](demo.gif) -->

## Features

- Two spinning, textured spheres rendered as ASCII-style art
- Moon is lit from whichever side faces the sun, so it goes through phases as it moves
- Colors blend where the bodies overlap, with random sparks in the collision zone
- Sun has a fuzzy flickering corona; stars twinkle between `.`, `+`, and full cross shapes
- Pure Python standard library (tkinter only), no `pip install` needed
- Only redraws the characters that changed each frame, so it stays smooth

## Requirements

- Python 3.8 or newer
- tkinter (included with the standard Python installers for Windows and macOS; on Debian/Ubuntu run `sudo apt install python3-tk`)
- A monospaced font. It uses Consolas by default; change `FONT_FAMILY` at the top of the file if you don't have it (e.g. `"Menlo"` on macOS or `"DejaVu Sans Mono"` on Linux)

## Run it

```bash
python sunMoon.py
```

## Controls

| Key | Action |
| --- | --- |
| `Space` | Pause / resume |
| `Left` / `Right` | Slower / faster clash |
| `Up` / `Down` | Faster / slower spin |
| `Esc` | Quit |

## How it works

1. **Geometry:** each body is a sphere. For every cell of the character grid, the code works out whether it falls inside the circle and, if so, the surface direction (normal) at that point.
2. **Lighting:** the moon's brightness comes from a simple diffuse (Lambert) calculation against the direction of the sun. The sun glows on its own, brightest in the middle and darker toward the rim.
3. **Texture:** a cheap sine-wave texture on longitude/latitude gives the surfaces craters and granulation, and rotating it makes the bodies spin.
4. **Characters:** brightness picks a character from a ramp (`.,:;irsXA253hMHGS#9B&@`), with a little random jitter so it shimmers.
5. **Color:** brightness also picks a color from a gradient (red/orange/white for the sun, navy/blue/white for the moon). Where both bodies cover a cell, the colors are combined with a screen blend, which is why the overlap goes pink and white.
6. **Rendering:** the frame is built as two grids (characters and colors) and only the changed cells are pushed to a tkinter canvas.

The `Scene` class has no tkinter in it, so you can call `Scene(...).render(t)` from a test or another program and get the frame as plain lists.

## Customize

Everything worth tweaking is in the settings block at the top of `sunMoon.py`:

- `COLS`, `ROWS`, `FONT_SIZE`: window size
- `SUN_R_FRAC`, `MOON_R_FRAC`: how big each body is
- `CLASH_SPEED`, `SPARK_CHANCE`: how fast and how violent
- `RAMP`: the character set, from dark to bright
- `SUN_STOPS`, `MOON_STOPS`: the color gradients
- `NUM_STARS`: how busy the sky is

## Ideas to extend it

- Add a trail or shockwave ring when the bodies fully overlap
- Let the user drag the moon around with the mouse
- Export frames to a GIF
- Port it to a terminal using `curses` or ANSI colors

## License

Choose a license when you create the repo (MIT is a common pick for small projects like this).
