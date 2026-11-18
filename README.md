# DLSP

Digital Logic Sim project archive.

| Path | What it is |
| --- | --- |
| `PC_EYE_OS/` | Main library: 24 custom chips — NAND-based gates → adders → latches → 8-bit register → RGB screen → HDMI link. DLS 2.1.6. |
| `REFS/` | Scratch reference project: one chip showing the pinout of every built-in splitter, merger, bus and the RGB display. |
| `ANALYSIS.md` | Full review: format documentation, per-chip verification, and the defects found. |
| `tools/dlsp_sim.py` | Reader/simulator for the chip format — flattens any chip to NAND leaves and evaluates it. |
| `tools/build_hdmi.py` | Generator for the five HDMI/RGB-screen chips (they are machine-built, not hand-drawn). |

## Display chain

`DISP` was deleted. Its replacement is a five-chip HDMI/RGB display path:

```
  TMDS 9B ENCODER ──┐
                    │  19-pin cable
  HDMI TYPE A ──────┴──▶ HDMI DISPLAY ──▶ TMDS 9B DECODER ×3 ──▶ RGB SCREEN
                          (19 HDMI pins)                        (16×16, 4096 colours)
```

* **`RGB SCREEN`** — the screen. `ADDR[8]`, `RED[4]`, `GREEN[4]`, `BLUE[4]`,
  `WRITE`, `CLOCK`, `ON` in; `R OUT[4]`, `G OUT[4]`, `B OUT[4]` out. The LED inside
  it is the **on/off indicator** — `ON` also gates writes and the clock.
* **`HDMI TYPE A`** — all 19 Type A connector pins in physical order
  (`1 TMDS D2+` … `19 HPD`) plus differential receivers and a `LINK` detect.
* **`TMDS 9B ENCODER`** — transition-minimised 8b→9b TMDS coding (HDMI 1.4 §5.4.2,
  stage 1) with a popcount adder tree: 353 NAND gates. `TMDS 9B DECODER` inverts it.
* **`HDMI DISPLAY`** — connector → decoders (channel 0 = blue, 1 = green,
  2 = red) → screen.

## Quick start

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, 'tools')
import dlsp_sim as S
p = S.Project('PC_EYE_OS')
print(p.run('8BIT FULL ADDER', {'IN A': 200, 'IN B': 100}))   # {'SUM': 44, 'OF': 1}
e = p.run('TMDS 9B ENCODER', {'D': 0x9C, 'DE': 1})            # {'Q': ..., 'Q8': ...}
print(p.run('TMDS 9B DECODER', {'Q': e['Q']}))                # {'D': 156}
PY
```

## Open issue

`4 PIN LOCK` is missing the wire from its `1-4BIT` merge output to the chip's
`OUT` pin, so the chip always returns 0. Nothing else in the library uses it any
more, but it is still broken. See `ANALYSIS.md` §5, finding B1.
