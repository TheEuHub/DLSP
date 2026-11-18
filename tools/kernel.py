"""PC_EYE_OS kernel: assembler + boot/monitor program.

The ROM is a built-in ROM 256x16 whose contents live in the chip-instance
runtime state, not in the chip JSON, so the program ships as `kernel.hex`
(plus this listing) and is typed/loaded through the in-app ROM editor.

Instruction word (16 bits):  [opcode:4][operand[11:8]:4][operand[7:0]:8]
"""
import sys

OPS = {
    "NOP":  0x0,
    "LDI":  0x1,   # A <- imm8
    "LDX":  0x2,   # X <- imm8
    "ADDX": 0x3,   # X <- X + imm8
    "CMPX": 0x4,   # Z <- (X == imm8)
    "SETC": 0x5,   # colour <- imm12  (R=11:8, G=7:4, B=3:0)
    "PIX":  0x6,   # screen[X] <- colour
    "JMP":  0x7,   # PC <- imm8
    "JZ":   0x8,   # if Z: PC <- imm8
    "ADD":  0x9,   # A <- A + imm8
    "AND":  0xA,   # A <- A & imm8
    "XOR":  0xB,   # A <- A ^ imm8
    "HLT":  0xF,
}


def assemble(src):
    """Two-pass assembler. Returns (words, listing)."""
    lines = []
    for raw in src.strip().splitlines():
        line = raw.split(";")[0].strip()
        if not line:
            continue
        # allow "label: instruction" on one line
        if ":" in line:
            lab, rest = line.split(":", 1)
            if " " not in lab.strip():
                lines.append(lab.strip() + ":")
                line = rest.strip()
                if not line:
                    continue
        lines.append(line)

    labels, pc = {}, 0
    for line in lines:
        if line.endswith(":"):
            labels[line[:-1].strip()] = pc
        else:
            pc += 1
    if pc > 256:
        raise ValueError(f"program is {pc} words, ROM holds 256")

    words, listing, pc = [], [], 0
    for line in lines:
        if line.endswith(":"):
            listing.append((pc, line, "", ""))
            continue
        parts = line.replace(",", " ").split()
        mnem = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else None
        if mnem not in OPS:
            raise ValueError(f"unknown opcode {mnem!r}")
        operand = 0
        if arg is not None:
            a = arg.lstrip("#")
            if a in labels:
                operand = labels[a]
            else:
                operand = int(a, 0)
        operand &= 0xFFF
        word = (OPS[mnem] << 12) | operand
        words.append(word)
        listing.append((pc, line, f"{word:04X}", mnem))
        pc += 1
    return words, listing


KERNEL = """
; ---------------------------------------------------------------
; PC_EYE_OS kernel  -  POST, framebuffer driver, desktop, idle
; 16x16 panel, 12-bit colour (R4 G4 B4), pixel = screen[X]
; ---------------------------------------------------------------
        SETC #0xFFF          ; POST: flood the panel white
        LDX  #0
post:   PIX                  ;   proves every pixel and the latch work
        ADDX #1
        CMPX #0
        JZ   desktop
        JMP  post

desktop: SETC #0x124         ; desktop background: dark blue
        LDX  #0
clear:  PIX                  ; paint the whole panel
        ADDX #1
        CMPX #0              ; X wrapped 255 -> 0 : all 256 pixels done
        JZ   frame
        JMP  clear

frame:  SETC #0xF80          ; amber window frame
        LDX  #0
top:    PIX                  ; top edge, 0..15
        ADDX #1
        CMPX #16
        JZ   bottom
        JMP  top
bottom: LDX  #240
bot:    PIX                  ; bottom edge, 240..255
        ADDX #1
        CMPX #0
        JZ   left
        JMP  bot
left:   LDX  #16
lft:    PIX                  ; left edge, step 16
        ADDX #16
        CMPX #0
        JZ   right
        JMP  lft
right:  LDX  #31
rgt:    PIX                  ; right edge, ends at 15 after the last step
        ADDX #16
        CMPX #15
        JZ   cursor
        JMP  rgt

; ---- idle: blink a 2x2 text cursor in the middle of the screen ----
cursor: SETC #0x0F0          ; green
        LDX  #136
        PIX
        LDX  #137
        PIX
        LDX  #152
        PIX
        LDX  #153
        PIX
        LDX  #0
dly1:   ADDX #1              ; busy-wait
        CMPX #200
        JZ   off
        JMP  dly1
off:    SETC #0x124          ; back to background
        LDX  #136
        PIX
        LDX  #137
        PIX
        LDX  #152
        PIX
        LDX  #153
        PIX
        LDX  #0
dly2:   ADDX #1
        CMPX #200
        JZ   cursor
        JMP  dly2
"""


def main():
    words, listing = assemble(KERNEL)
    here = __file__.rsplit("/", 1)[0]
    with open(f"{here}/kernel.hex", "w") as f:
        for i, w in enumerate(words):
            f.write(f"{i:02X} {w:04X}\n")
    print(f"{len(words)} words ({len(words)*2} bytes), ROM 256x16")
    for pc, src, hexw, mnem in listing:
        print(f"  {pc:3d} {hexw:>5}  {src}")
    return words, listing


if __name__ == "__main__":
    main()
