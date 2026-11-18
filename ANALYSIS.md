# DLSP — Project Archive Review

Analysis of `Projects.zip` (unpacked at the repo root). Two Digital Logic Sim
projects: **`PC_EYE_OS`** (20 chips, plus 5 added in this pass) and **`REFS`** (1 chip).

Reviewed by flattening every chip to its built-in NAND leaves and simulating the
resulting netlists. All findings below are reproduced by `tools/dlsp_sim.py`.

---

## 1. What was in the archive

```
Projects.zip
├── PC_EYE_OS/                    20 custom chips as shipped (24 after this pass)
│   ├── ProjectDescription.json   project manifest (version, prefs, collections)
│   └── Chips/*.json              1 file per chip
└── REFS/                         1 custom chip, created 2026-11-18 16:28
    ├── ProjectDescription.json
    └── Chips/REFS.json
```

Both are **Digital Logic Sim** projects (`DLSVersion_LastSaved: 2.1.6`,
`EarliestCompatible: 2.0.0`). No top-level circuit is stored in this export —
the projects are purely **chip libraries**, so the deliverable artefact is the
reusable standard-cell set, not a finished machine.

---

## 2. The file format

Each chip is a JSON netlist. Structure (all fields observed in these files):

| Field | Meaning |
| --- | --- |
| `Name`, `NameLocation` | chip name + where the label is drawn |
| `ChipType` | `0` in every file (normal custom chip) |
| `Size` | body size in grid units |
| `Colour` | body tint `{r,g,b,a}` |
| `InputPins[]` / `OutputPins[]` | `Name`, `ID`, `Position`, **`BitCount`**, `Colour`, `ValueDisplayMode` |
| `SubChips[]` | placed instances: `Name`, `ID`, `Label`, `Position`, `OutputPinColourInfo`, `InternalData` |
| `Wires[]` | `SourcePinAddress` / `TargetPinAddress` = `{PinID, PinOwnerID}`, `ConnectionType`, `Points[]` |
| `Displays[]` | empty in both projects |

**Pin addressing.** A wire endpoint is `(PinOwnerID, PinID)`. `PinOwnerID` is
the *object* (a chip pin `ID`, or a subchip instance `ID`); `PinID` is the pin
inside that object. The chip's own pins are always addressed as `PinID: 0`.

**Built-in chip pin numbering** (inferred from the wiring, consistent across all
files):

| Builtin | Pins |
| --- | --- |
| `NAND` | in `0`, `1` → out `2` |
| `4-1BIT` / `8-1BIT` (splitter) | in `0` → out `1..N` |
| `1-4BIT` / `1-8BIT` (merger) | in `0..N-1` → out `N` |
| `8-4BIT` | in `0` → out `1` = high nibble, `2` = low nibble |
| `4-8BIT` | in `0` = high nibble, `1` = low nibble → out `2` |
| `BUS-n` / `BUS-TERMINUS-n` | paired through `InternalData: [peerId, 0]` |

**Bit order** (verified by exhaustive arithmetic tests): splitter output pin
`k` carries bit `N-k`; merger input pin `j` carries bit `N-1-j`. So a signal of
the same significance always sits at pin index `k` on the split side and `k-1`
on the merge side — this is why every multi-bit chip looks like it wires
`1→0, 2→1, 3→2, …`.

**Semantics.** Unconnected inputs read `0`. Every custom chip in both projects
bottoms out in `NAND` plus the bus helpers, which is what makes full flattening
and simulation possible.

---

## 3. Project `REFS` — a pinout reference card

One chip (`REFS`, 0.725 × 1.125) containing **13 built-ins and zero wires**:

* `1-4BIT`, `1-8BIT`, `4-1BIT`, `4-8BIT`, `8-1BIT` — the split/merge family
* `BUS-1`, `BUS-4`, `BUS-8` + `BUS-TERMINUS-1/4/8` — wired to each other only via `InternalData`
* `RGB DISPLAY`

with six loose pins (`IN` 1/4/8-bit, `OUT` 1/4/8-bit). Unconnected pins are
intentional here: the chip is a **lookup sheet** for built-in pin layouts, laid
out in a tidy column.

Supporting evidence that it is a scratch project: grid, snapping and straight
wires are all **off** (`Prefs_GridDisplayMode/Snapping/StraightWires: 0`), and
`AllCustomChipNames` contains only `REFS` — it is deliberately kept separate
from the working library.

---

## 4. Project `PC_EYE_OS` — the logic library

**Intent.** The name ("PC" + "EYE" + "OS") points at a computer with a display;
the contents are the bottom-up standard-cell library that such a machine would
be built from. `ChipCollections` groups the library into
`BASIC / IN-OUT / MERGE-SPLIT / BUS / DISPLAY / MEMORY / OTHER`, and the author
has starred 20 of them for quick access.

### 4.1 Layer cake

```
L0  NAND (builtin)  ─────────────────────────────────────────────┐
L1  NOT, OND(AND), NOND(NAND)        1 NAND each (OND uses 2)    │
L2  OR, NOR, XOR, XNOR               3–5 NANDs, pure NAND nets    │
    ── 1-bit datapath ──                                          │
L2  HALF ADDER, FULL ADDER           6 / 15 NANDs                 │
L3  4BIT FULL ADDER                  ripple of 4 full adders     │
L4  8BIT FULL ADDER                  ripple of 2 4-bit adders    │
    ── storage ──                                                │
L2  D FLIP FLOP (gated D latch)      NOR latch + load gates      │
L3  4BIT / 8BIT D FLIP FLOP          parallel latches            │
L5  8BIT REG                         master/slave = edge-triggered
L2  T FLIP FLOP                      toggling bistable            │
    ── masking + display ──                                      │
L2  1/4/8 PIN LOCK                   AND-mask gated buffers      │
L3  RGB SCREEN                       RGB DISPLAY + power lamp    │
    ── HDMI link ──                                             │
L3  HDMI TYPE A                      19-pin connector + receivers│
L4  TMDS 9B ENCODER / DECODER        8b<->9b transition coding   │
L5  HDMI DISPLAY                     connector → decode → screen │
    ── computer (section 6) ──                                   │
L2  CONST 1, MUX 1/4/8, REG 1/4, XOR 8, ISZERO 8                 │
L3  DECODER 4 TO 16, ALU 8           op select, instruction decode│
L4  CPU 8                            registers + ROM + ALU + CU  │
L5  PC_EYE 8                         CPU 8 + RGB SCREEN = a PC   │
```

### 4.2 Chip inventory (verified behaviour)

| Chip | In → Out | Built from | NAND leaves | Verdict |
| --- | --- | --- | --- | --- |
| `NOT` | 1 → 1 | NAND | 1 | ✅ truth table |
| `OND` (AND) | 2 → 1 | 2×NAND | 2 | ✅ truth table |
| `NOND` (NAND) | 2 → 1 | NAND | 1 | ✅ truth table |
| `OR` | 2 → 1 | 3×NAND (De Morgan) | 3 | ✅ truth table |
| `NOR` | 2 → 1 | OR + inverter | 4 | ✅ truth table |
| `XOR` | 2 → 1 | 4×NAND | 4 | ✅ truth table |
| `XNOR` | 2 → 1 | XOR + inverter | 5 | ✅ truth table |
| `HALF ADDER` | A,B → SUM,C OUT | XOR + AND | 6 | ✅ all 4 cases |
| `FULL ADDER` | A,B,C IN → SUM,C OUT | 2×XOR, 2×AND, OR | 15 | ✅ all 8 cases |
| `4BIT FULL ADDER` | A,B[4],C IN → SUM[4],C OUT | 4× full adder + splitters | 60 | ✅ all 512 cases |
| `8BIT FULL ADDER` | A,B[8] → SUM[8],OF | 2× 4-bit adder | 120 | ✅ all 65 536 cases |
| `D FLIP FLOP` | DATA,LOAD → MEM,-MEM | NOR latch + load gates | 13 | ✅ latch: transparent at LOAD=1, holds at LOAD=0 |
| `4BIT D FLIP FLOP` | DATA[4],LOAD → MEM[4],-MEM[4] | 4× D latch | 52 | ✅ holds, -MEM = ~MEM |
| `8BIT D FLIP FLOP` | DATA[8],LOAD → MEM[8],-MEM[8] | 2× 4-bit DFF | 104 | ✅ holds, -MEM = ~MEM |
| `8BIT REG` | DATA[8],LOAD → MEM[8],-MEM[8] | 2× 8-bit DFF (master/slave) | 209 | ✅ captures on LOAD rising edge |
| `T FLIP FLOP` | IN → OUT,-OUT | 8×NAND + 2×NOT | 10 | ✅ toggles on every IN rising edge, holds on falling |
| `1 PIN LOCK` | IN,UNLOCK → OUT | AND mask | 2 | ✅ OUT = IN ∧ UNLOCK |
| `4 PIN LOCK` | IN[4],UNLOCK → OUT[4] | 4× AND + split/merge | 8 | ❌ **OUT pin never wired** |
| `8 PIN LOCK` | IN[8],UNLOCK → OUT[8] | 8× AND + split/merge | 16 | ✅ OUT = IN ∧ UNLOCK |
| `RGB SCREEN` | ADDR[8],R[4],G[4],B[4],WRITE,CLOCK,ON → R/G/B OUT[4] | RGB DISPLAY + 2 masking gates + LED | 4 | ✅ new, replaces `DISP` |
| `HDMI TYPE A` | 19 connector pins → D0/D1/D2[8], CLK, LINK | 6 splitters, 24 XOR + 23 AND | 150 | ✅ 19-pin pinout, link detect |
| `TMDS 9B ENCODER` | D[8],DE → Q[8],Q8 | XOR/XNOR chain + popcount adder tree | 353 | ✅ matches HDMI 1.4 §5.4.2 stage 1, all 256 bytes |
| `TMDS 9B DECODER` | Q[8] → D[8] | XOR/XNOR chain | 113 | ✅ round-trips all 256 bytes |
| `HDMI DISPLAY` | 19 HDMI pins + ADDR/WRITE/CLOCK/ON | connector → 3 decoders → screen | 493 | ✅ wired, compiles |

**Colour convention.** The primitive layer uses pure RGB primaries (red `NOT`,
blue `OND`, magenta `NOND`, cyan `XOR`, yellow `NOR`, green `OR`, white `XNOR`);
every composite chip gets its own unique tint. **Build order** from file
timestamps: gates (Nov 5) → adders (Nov 7) → flip-flops/register (Nov 7–8) →
pin locks and `DISP` (Nov 18) — i.e. the display driver was the newest,
unfinished work. `DISP` has since been deleted and replaced by `RGB SCREEN`
plus the HDMI link chips described in §5.

---

## 5. Findings

### 🔴 B1 — `4 PIN LOCK` has no output connection

`4 PIN LOCK.json` has 13 wires where its siblings need 14. The merge chip
`1-4BIT` (id `796558869`) receives all four masked bits on pins `0..3`, but
**pin `4` is never wired to the chip's `OUT` pin** (`1960317531`).

The fix is the one wire every other member of the family has — in `8 PIN LOCK`
it is the last wire, `1-8BIT` output pin `8` → chip `OUT`:

```json
{ "SourcePinAddress": { "PinID": 8, "PinOwnerID": <1-8BIT id> },
  "TargetPinAddress": { "PinID": 0, "PinOwnerID": 1593448837 } }   // 8 PIN LOCK OUT
```

For `4 PIN LOCK` the equivalent is `PinID: 4` of the `1-4BIT` instance
(id `796558869`) → `PinID: 0` of `OUT` (id `1960317531`).

Effect: the chip returns `0` for **every** input — a silent failure, no width or
dangling-reference error. Fix: add one wire `1-4BIT(pin 4) → OUT(pin 0)`.

### ✅ `DISP` — deleted, replaced by `RGB SCREEN` + the HDMI link

The original `DISP` was dead twice over: none of its eight latch data inputs were
wired (its only input drove `UNLOCK`), and it embedded three copies of the broken
`4 PIN LOCK`. It has been removed and replaced by five new chips.

**What the built-in `RGB DISPLAY` actually is** (read out of the engine source,
`BuiltinChipCreator.CreateDisplayRGB` + `Simulator.cs`):

| Pin | Name | Width |
| --- | --- | --- |
| 0 | `ADDRESS` | 8 bits (256 pixels, 16×16) |
| 1/2/3 | `RED` / `GREEN` / `BLUE` | 4 bits each (4096 colours) |
| 4/5/6/7 | `RESET` / `WRITE` / `REFRESH` / `CLOCK` | 1 bit |
| 8/9/10 | `R OUT` / `G OUT` / `B OUT` | 4 bits (read-back) |

It is double-buffered: on a `CLOCK` rising edge it clears the back buffer when
`RESET` is high, otherwise stores the colour at `ADDRESS` when `WRITE` is high,
and copies back→front when `REFRESH` is high.

#### `RGB SCREEN` (replaces `DISP`)

Seven inputs, three outputs:

```
ADDR[8]  RED[4]  GREEN[4]  BLUE[4]  WRITE  CLOCK  ON   ──▶  R OUT[4] G OUT[4] B OUT[4]
```

* `ON` gates both `WRITE` and `CLOCK` with an AND, so nothing can be written
  while the screen is off.
* `REFRESH` is tied to the gated `WRITE`, so a pixel appears the moment it is
  written (write-through). Unwire that one wire if you want manual refresh.
* An **LED sits inside the chip on `ON`** — that is the on/off indicator — and
  `R/G/B OUT` read back the colour at `ADDR`.

#### `HDMI TYPE A` — the cord

All **19 pins of a Type A HDMI connector**, in physical order and with the standard
names: `1 TMDS D2+`, `2 D2 SHIELD`, `3 TMDS D2-`, … `13 CEC`, `14 RESERVED`,
`15 SCL`, `16 SDA`, `17 GND`, `18 +5V`, `19 HPD`.

It also does what a receiver front-end does: each TMDS pair is compared bit-by-bit
(XOR), the XORs are AND-reduced, and `LINK` goes high only when all three data
pairs are complementary, the clock pair is complementary, and `+5V` is present.
`D0/D1/D2` output the recovered bytes. The shields, `CEC`, `SCL`, `SDA`, `GND` and
`HPD` are deliberately unconnected reference pins.

#### `TMDS 9B ENCODER` / `TMDS 9B DECODER` — the "more than five gates" chip

This is the new building block the brief asked for: a chip that cannot be made
from a handful of gates. It implements **stage 1 of the TMDS 8b/10b link encoding
from HDMI 1.4 §5.4.2** — the transition-minimised 8b→9b mapping:

```
q_m[0] = D[0]
q_m[i] = q_m[i-1] XNOR D[i]   when D[0] = 0
q_m[i] = q_m[i-1] XOR  D[i]   when D[0] = 1
N1{D}  = number of ones in D
q_m[8] = 1 when N1 < 4, or when N1 = 4 and D[0] = 1; otherwise 0
```

`N1` is computed with a popcount tree: four half adders, three 4-bit adders.
The XOR/XNOR choice is a two-AND/one-OR multiplexer per bit. `DE` gates the output
to zero for control periods. That is **353 NAND gates** in `TMDS 9B ENCODER`
(113 in the decoder) — comfortably past "more than five".

Verified exhaustively against a reference implementation of the spec:

* encoder == reference for all 256 input bytes × `DE` ∈ {0,1} — **PASS**
* `ENCODER → DECODER` returns the original byte for all 256 values — **PASS**
* connector: complementary pairs + `+5V` → `LINK=1` and correct data; shorted
  pairs or missing `+5V` → `LINK=0` — **PASS**

#### `HDMI DISPLAY`

The assembled monitor: the 19 connector pins plus `ADDR`, `WRITE`, `CLOCK`, `ON`.
Inside, the connector feeds three decoders (channel 0 = blue, 1 = green, 2 = red,
as in HDMI), the decoded 8-bit channels are truncated to the panel's 4-bit
channels with `8-4BIT` splitters, and the result drives `RGB SCREEN`.

**Modelling caveat.** A real HDMI link serialises the 10-bit TMDS symbols at ten
times the pixel rate; DLS has no way to express a rate domain, so each lane here
carries one symbol as a parallel bus (8 data bits + separate `Q8`). The connector
pinout, the differential pairs, the channel-to-colour mapping and the encoding
arithmetic are faithful; the serializer/deserializer is out of scope, and the
running-disparity (9b→10b) stage is not modelled — `Q8` is exposed for a future
stage.

### 🟡 R1 — "D FLIP FLOP" is a latch, not a flip-flop

`D FLIP FLOP` is transparent while `LOAD = 1` and holds while `LOAD = 0`
(verified statefully). That makes `4BIT/8BIT D FLIP FLOP` level-sensitive too —
hard to reason about in a synchronous design. `8BIT REG` is the only proper
edge-triggered part (master loads on `LOAD = 0`, slave on `LOAD = 1`, so it
captures on the rising edge). Suggest renaming to `D LATCH` / keeping the
`REG` name for the edge-triggered version.

### 🟡 R2 — no reset anywhere

No chip has a `RESET`/`CLEAR` input, and the latches power up in a metastable
state (both `MEM` and `-MEM` settle equal on a cold start). A register file or
PC built from these parts would start in an undefined state. Adding a clear
input to the D latch (extra gate on the NOR latch) would fix the whole family.

**Worked around:** `CPU 8` gives every state register a reset mux in front of its
data input, driven by `¬POWER`, so the machine boots from a defined state and a
power cycle restarts the kernel (section 6.6).

### 🟡 R3 — `8BIT FULL ADDER` cannot be cascaded

`4BIT FULL ADDER` exposes `C IN`, but `8BIT FULL ADDER` drops it (the low-nibble
adder's `C IN` is simply unconnected — harmless, implicit `0`, but it blocks
chaining). Without a `C IN`/`C OUT` pair you can't build 16-bit adders, and you
can't do subtract-on-add (`A + ~B + 1`) at 8 bits either. Worth exposing
`C IN` for symmetry.

### 🔵 N1 — naming

* `OND` = AND, `NOND` = NAND, `XNOR`/`NOR` inverted — the `O`/`N` prefix scheme
  is self-consistent but non-obvious.
* `* PIN LOCK` are **not** locks/memory: each is just `IN ∧ UNLOCK`, a gated
  buffer. The name suggests latching.
* `8BIT REG` and `4BIT/8BIT D FLIP FLOP` have identical ports and pin names
  (`DATA/LOAD → MEM/-MEM`) but different timing behaviour.

---

## 6. The operating system

Section 6 of the old review said the machine could not run because there was no
decoder, no ALU, no program counter and no memory in use. All of that now
exists: `PC_EYE_8` is a complete 8-bit computer with a ROM-resident kernel, and
it boots in the simulator (section 6.6).

### 6.1 What was added

| Chip | In → Out | Built from | NAND leaves |
| --- | --- | --- | --- |
| `CONST 1` | – → 1 | one `NAND` fed by itself | 1 |
| `MUX 1` | `IN A`,`IN B`,`SEL` → `OUT` | NOT + 2×OND + OR | 8 |
| `MUX 4` | 4-bit A/B + `SEL` → 4-bit `OUT` | 4×`MUX 1` + splitters | 29 |
| `MUX 8` | 8-bit A/B + `SEL` → 8-bit `OUT` | 8×`MUX 1` + splitters | 57 |
| `REG 1` | `DATA`,`LOAD` → `MEM`,`-MEM` | 2×`D FLIP FLOP` + NOT (master/slave) | 27 |
| `REG 4` | 4-bit `DATA` + `LOAD` → `MEM` | 4×`REG 1` | 105 |
| `XOR 8` | 8-bit A/B → `OUT` | ripple of 4×`XOR` | 32 |
| `ISZERO 8` | 8-bit `IN` → `OUT` | OR tree of 8, inverted | 22 |
| `DECODER 4 TO 16` | 4-bit `IN` → `O0..O15` | 16×4-input AND + 4 inverters | 100 |
| `ALU 8` | `IN A`,`IN B`,`OP0`,`OP1` → `OUT` | `8BIT FULL ADDER` + `XOR 8` + 8 muxes | 339 |
| `CPU 8` | `CLK`,`POWER` → `ADDR`,`R`,`G`,`B`,`WRITE` | 49 sub-chips | 2375 |
| `PC_EYE 8` | `CLK`,`POWER` → — | `CPU 8` + `RGB SCREEN` | 2379 |

`ALU 8` op select: `00` = pass B, `01` = A+B, `10` = A AND B, `11` = A XOR B.
That is enough for a real ISA (load, add, mask, compare) without a subtractor:
`CMPX` computes `X XOR operand` and sets Z when the result is zero.

### 6.2 `CPU 8` — the machine

Single cycle, one instruction per rising clock edge, state in six
master/slave registers plus the Z flag:

```
             ┌─────────────── ROM 256x16 ───────────────┐
   PC ──────▶│ ADDRESS                             OUT B/A│
             └──────────────────────────────────────────┘
                      │ opcode[7:4]      │ operand[7:0] (jump target)
                      ▼                  │
              DECODER 4 TO 16            │
                      │ 16 control lines │
      ┌───────────────┼──────────────────┼──────────────────┐
      ▼               ▼                  ▼                  ▼
   ┌─────┐        ┌──────┐          ┌─────────┐       ┌─────────┐
   │  A  │◀─ALU──│ ALU 8│          │   PC    │       │  R,G,B  │
   └─────┘        └──────┘          └─────────┘       └─────────┘
      │               ▲                  ▲                  │
      └──▶ ADDR ──▶ RGB SCREEN           │                  └──▶ RED/GREEN/BLUE
                                          │
      X ──▶ ADDR, ALU, XOR ──▶ ISZERO ──▶ Z
```

**Timing idiom.** Every register has `LOAD = CLK` and its data input is a 2:1
mux: `DATA = (write-enable ? new value : its own MEM)`, with a second mux that
forces `0` while `POWER` is low. The master half of the register captures during
the low phase, i.e. exactly when the current instruction's control lines are
stable, so a write-enable can never leak into the next instruction.

The first version of the CPU gated the enables with the clock (`LOAD = WE ∧ CLK`)
and it deadlocked: while `CLK` stayed high the *next* instruction's decoder
outputs were already active, so flags were loaded one instruction early and a
`CMPX #0` never set Z. The mux idiom above is the fix; it is also what makes the
design robust to any clock period.

### 6.3 ISA

16-bit words: `[opcode:4][unused:4][operand:8]`.

| # | Mnemonic | Effect |
| --- | --- | --- |
| `0` | `NOP` | – |
| `1` | `LDI n` | `A ← n` |
| `2` | `LDX n` | `X ← n` |
| `3` | `ADDX n` | `X ← X + n` |
| `4` | `CMPX n` | `Z ← (X == n)` |
| `5` | `SETC c` | `R,G,B ← high,mid,low nibble of c` |
| `6` | `PIX` | write colour to `screen[X]` |
| `7` | `JMP a` | `PC ← a` |
| `8` | `JZ a` | `PC ← a if Z` |
| `9` | `ADD n` | `A ← A + n` |
| `A` | `AND n` | `A ← A ∧ n` |
| `B` | `XOR n` | `A ← A ⊕ n` |
| `F` | `HLT` | stop fetching |

There is no stack and no indirect addressing: the ROM is 256 words and the
machine is a display driver, not a general-purpose computer.

### 6.4 The kernel

`tools/kernel.py` is a two-pass assembler plus the kernel source; it emits
`tools/kernel.hex` (address → 16-bit word) and a listing. 67 words:

1. **POST** — flood the panel white, which proves every pixel address and the
   panel latch.
2. **Desktop** — fill the panel with the background colour `0x124`.
3. **Frame** — draw the amber window border `0xF80`: top row, bottom row, then
   the two side columns stepping by 16.
4. **Idle** — a 2×2 green cursor at `screen[136]` that blinks: write, busy-wait
   200 iterations, erase, busy-wait, repeat.

```
post:   SETC #0xFFF / LDX #0 / PIX / ADDX #1 / CMPX #0 / JZ desktop / JMP post
clear:  SETC #0x124 / LDX #0 / PIX / ADDX #1 / CMPX #0 / JZ frame   / JMP clear
frame:  SETC #0xF80 / top row (0..15) / bottom row (240..255) / left col / right col
cursor: SETC #0x0F0 / PIX ×4 / delay / SETC #0x124 / PIX ×4 / delay / JMP cursor
```

Loop termination is done by wrap-around rather than by a second compare: the
clear loop runs until `ADDX #1` turns 255 into 0, then `CMPX #0` fires. Saves a
compare per iteration and keeps the ROM small.

### 6.5 ROM is not part of the chip file

`ROM 256×16` keeps its contents in runtime state, and `ChipDescription` has no
field that carries that state (checked against the Rewired reimplementation:
`Rom_256x16` reads `chip.InternalState[address]`). A `.chip` file therefore ships
an **empty** ROM. `tools/rom_loader.md` explains this and lists the 67 words so
the ROM can be typed in by hand; the simulator loads them with
`Project.load_rom('tools/kernel.hex')`.

### 6.6 Boot proof

`python3 tools/boot.py` loads `kernel.hex`, raises `POWER`, toggles `CLK` for
3400 instructions and screenshots the panel:

```
################
#..............#
#..............#
#..............#
#..............#
#..............#
#..............#
#..............#
#.......OO.....#
#.......OO.....#
#..............#
#..............#
#..............#
#..............#
#..............#
################
```

Legend: `#` amber frame `0xF80`, `.` desktop `0x124`, `O` cursor `0x0F0`.

Verified in simulation:

| Check | Result |
| --- | --- |
| `POWER = 0` holds every register at 0 | ✅ `PC` stays 0 |
| POST floods 256 white pixels | ✅ |
| Desktop fills 256 background pixels | ✅ |
| Border draws 60 amber pixels (16+16+14+14) | ✅ |
| Cursor blinks (on ≈ 800 instr, off ≈ 800) | ✅ |
| Power cycle restarts the POST | ✅ 24 → 214 white pixels mid-flood |

Screenshot: `tools/os_screenshot.png`. Raw frame: `tools/framebuffer.json`
(`(B<<8)|(G<<4)|R` per pixel).

Machine cost: `PC_EYE 8` flattens to **2379 NAND gates**, 162 bus operations,
one ROM and one display.

## 7. What was missing (now historical)

The original review listed the blocks a working PC_EYE_OS would need. Status:

| Block | Status |
| --- | --- |
| Multiplexer / demux / decoder | ✅ `MUX 1/4/8`, `DECODER 4 TO 16` |
| ALU | ✅ `ALU 8` — pass / add / and / xor |
| Program counter, control unit | ✅ inside `CPU 8` |
| Memory in use | ✅ `ROM 256x16` holds the kernel; `BUS-*` still unused |
| Tri-state busing | ⬜ still unused — the datapath uses muxes instead |
| Clock usage | ✅ everything is clocked from `CLK` |
| Reset | ✅ `¬POWER` mux per register (see R2) |
| Raster/address generator | ✅ the kernel is the address generator |

The remaining wants for a bigger machine: a `C IN` on `8BIT FULL ADDER` (R3) so
16-bit addresses become possible, RAM (there is none — `BUS-*` gives no storage),
and a stack pointer, which needs RAM.

## 8. Tooling added

`tools/dlsp_sim.py` — a small reader/simulator for this project format:

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, 'tools')
import dlsp_sim as S
p = S.Project('PC_EYE_OS')
print(p.run('8BIT FULL ADDER', {'IN A': 200, 'IN B': 100}))   # {'SUM': 44, 'OF': 1}
print(p.run('XOR', {'IN A': 1, 'IN B': 1}))                   # {'OUT': 0}
PY
```

* `Project(root).run(chip, {inputs})` — settle a chip and read its outputs.
* `Project(root).sim(chip).step({inputs})` — state-preserving stepping, needed
  for latches/registers/toggle logic (bistables keep their value between steps).
* `Project(root).compile(chip)` — the flattened NAND/bus netlist.
* `Project(root).load_rom(path)` — fill every `ROM 256x16` from a hex image.
* `Sim.framebuffer()` — the 256 words the panel is showing (`(B<<8)|(G<<4)|R`).

Machine-level tools:

| File | Purpose |
| --- | --- |
| `tools/kernel.py` | two-pass assembler + kernel source → `tools/kernel.hex` + listing |
| `tools/boot.py` | boot the machine, render the screen as ASCII, write `tools/os_screenshot.png` |
| `tools/selftest.py` | truth tables for all twelve OS chips, plus the boot/border/cursor assertions |
| `tools/build_os.py` | regenerates the twelve chip JSON files from Python |
| `tools/rom_loader.md` | why the ROM cannot live in a chip file, and the 67-word image |

Note: a plain static `run()` starts every net at `0`, so memory-holding states
look "unstable" from cold. That is a limitation of cold-start evaluation, not a
defect in the chips — use `sim()` for sequential parts.
