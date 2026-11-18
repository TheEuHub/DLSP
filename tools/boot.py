#!/usr/bin/env python3
"""Boot the PC_EYE_OS ROM in the simulator and capture the screen.

    python3 tools/boot.py [--frames] [--out tools/os_screenshot.png]

The panel is 16x16 with 12-bit colour; each pixel is
    value = (B << 8) | (G << 4) | R          (BGR packing, see framebuffer())

Everything here is a normal DLS simulation: CLK is toggled, POWER is raised, the
CPU fetches from `ROM 256x16` and drives `RGB DISPLAY` through `WRITE`.
"""
import argparse, json, os, struct, sys, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dlsp_sim as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEX = os.path.join(ROOT, "tools", "kernel.hex")
SIDE = 16


def rgb(v):
    """Framebuffer word -> (r, g, b), each 0..15."""
    return v & 15, (v >> 4) & 15, (v >> 8) & 15


def png(path, pixels, side=SIDE, scale=32, gap=2):
    """Write an RGB PNG, each panel pixel blown up with a thin grid gap."""
    bg = (16, 16, 20)
    w = h = side * scale + (side + 1) * gap
    rows = []
    img = [[bg] * w for _ in range(h)]
    for py in range(side):
        for px in range(side):
            r, g, b = rgb(pixels[py * side + px])
            col = (r * 17, g * 17, b * 17)
            x0 = gap + px * (scale + gap)
            y0 = gap + py * (scale + gap)
            for y in range(y0, y0 + scale):
                row = img[y]
                for x in range(x0, x0 + scale):
                    row[x] = col
    for row in img:
        rows.append(b"\x00" + b"".join(struct.pack("BBB", *c) for c in row))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(b"".join(rows), 9)))
        f.write(chunk(b"IEND", b""))
    return path


def render(pixels, side=SIDE, chars=None):
    """ASCII view: '#' amber frame, 'O' cursor, '.' desktop, ' ' black, '?' other."""
    glyphs = {
        (15, 8, 0): "#",   # amber frame
        (0, 15, 0): "O",   # green cursor
        (1, 2, 4): ".",    # desktop
        (15, 15, 15): "+",  # POST white
        (0, 0, 0): " ",
    }
    out = []
    for y in range(side):
        out.append("".join(glyphs.get(rgb(pixels[y * side + x]), "?") for x in range(side)))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "tools", "os_screenshot.png"))
    ap.add_argument("--boot", type=int, default=3400, help="instructions until the desktop is up")
    ap.add_argument("--blink", type=int, default=900, help="instructions per cursor phase")
    args = ap.parse_args()

    p = S.Project(os.path.join(ROOT, "PC_EYE_OS"))
    p.load_rom(HEX)
    sim = p.sim("PC_EYE 8")

    def run(n):
        for _ in range(n):
            sim.step({"CLK": 0, "POWER": 1})
            sim.step({"CLK": 1, "POWER": 1})

    run(args.boot)
    on = sim.framebuffer()
    print("== desktop, cursor on ==")
    print(render(on))

    run(args.blink)
    off = sim.framebuffer()
    print("\n== cursor phase toggled ==")
    print(render(off))
    print("\nblink working:", on != off)

    out = png(args.out, on)
    print("settled:", sim.settled, "| screenshot:", os.path.relpath(out, ROOT))
    with open(os.path.join(ROOT, "tools", "framebuffer.json"), "w") as f:
        json.dump(on, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
