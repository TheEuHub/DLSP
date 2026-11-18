# Programming the ROM by hand

`CPU 8` holds its program in a single `ROM 256×16`. **That program is not stored
in the chip file**, and this is a limitation of the DLS format, not a choice:

* `ROM 256×16` keeps its contents in `InternalState` (an address → word array on
  the chip *instance*). The Rewired reimplementation reads it exactly that way:
  `Rom_256x16.Evaluate` returns `chip.InternalState[address]` on `OUT B` / `OUT A`.
* `ChipDescription` — the serialised form of a chip — has `InputPins`,
  `OutputPins`, `SubChips[]`, `Wires[]`, `Displays[]`, but **no field for that
  internal state**. `SubChips[]` has an `InternalData` slot that carries bus
  wiring (`[peerId, 0]`), not memory contents.
* So a saved project ships a `ROM 256×16` with an **empty** program. Loading the
  project and running it gives a CPU that fetches `0x0000` (`NOP`) forever.

The boot image therefore lives next to the chips, as text:
`tools/kernel.hex` (address → 16-bit word, `;` comments allowed), generated from
the source in `tools/kernel.py`.

## Loading it

**Simulator** — one line, because `tools/dlsp_sim.py` models the ROM array:

```python
import sys; sys.path.insert(0, 'tools')
import dlsp_sim as S
p = S.Project('PC_EYE_OS')
p.load_rom('tools/kernel.hex')      # fills every ROM instance in the project
sim = p.sim('PC_EYE 8')
for _ in range(3400):
    sim.step({'CLK': 0, 'POWER': 1})
    sim.step({'CLK': 1, 'POWER': 1})
print(sim.framebuffer()[:16])
```

or just `python3 tools/boot.py`.

**In DLS by hand** — the ROM has no in-game editor, so the words have to be
poked in. Two workable routes:

1. *One ROM per byte, hard-wired:* build the image as 256 `CONST`-style gate
   networks — 67 words is about 2 100 gates, which is within reach of
   `tools/build_os.py` but throws away the point of having a ROM.
2. *Patch the save file:* DLS writes `InternalState` into the `.dlsp` project
   save (not into the `.chip`), so a project opened from a save that already
   contains a programmed ROM keeps the program. The hex file is written to be
   easy to splice: one line per address, `0007 8007`, matching the
   little-endian word order DLS uses (`OUT B` = high byte, `OUT A` = low byte).

Either way the assembler is the source of truth: edit `tools/kernel.py`, run it,
copy the new `kernel.hex`.

## The image

67 words, `[opcode:4][unused:4][operand:8]`:

```
addr word  mnemonic
00   5FFF  SETC #0xFFF      POST: flood the panel white
01   2000  LDX  #0
02   6000  PIX
03   3001  ADDX #1
04   4000  CMPX #0
05   8007  JZ   desktop
06   7002  JMP  post
...
08   5124  SETC #0x124      desktop fill, then the amber frame
...
40   40C8  CMPX #200        cursor blink delay
41   8027  JZ   cursor
42   703F  JMP  dly2
```

`python3 tools/kernel.py` prints the full listing with the assembled words and
writes `tools/kernel.hex`.

## Why this is not a defect in the CPU

`PC_EYE 8` is correct: give it a programmed ROM and it boots (see
`tools/boot.py` and `ANALYSIS.md` §6.6). The missing piece is only the
*transport* for ROM contents. If DLS ever adds `InternalData` for ROM instances,
the hex file can be converted to it directly — one array of 256 `uint16`.
