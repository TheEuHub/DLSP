"""Generate the HDMI / RGB-screen chips for the PC_EYE_OS project.

DLS pin addressing (confirmed against the engine source):
  * a wire endpoint is (PinOwnerID, PinID);
  * for a pin of the chip being defined, PinOwnerID = the pin's ID and PinID = 0;
  * for a pin of a placed subchip, PinOwnerID = the subchip instance ID and
    PinID = that subchip's pin ID.

Built-in pin numbering (BuiltinChipCreator.cs / Simulator.cs):
  NAND              IN B=0, IN A=1, OUT=2
  4-1BIT split      in 0            -> out 1..4    (out k = bit 4-k)
  8-1BIT split      in 0            -> out 1..8    (out k = bit 8-k)
  1-4BIT merge      in 0..3         -> out 4       (in j  = bit 3-j)
  1-8BIT merge      in 0..7         -> out 8       (in j  = bit 7-j)
  8-4BIT split      in 0            -> out 1 = high nibble, 2 = low nibble
  4-8BIT merge      in 0 = high, 1 = low -> out 2
  RGB DISPLAY       ADDRESS=0(8b) RED=1(4b) GREEN=2(4b) BLUE=3(4b)
                    RESET=4 WRITE=5 REFRESH=6 CLOCK=7
                    R OUT=8(4b) G OUT=9(4b) B OUT=10(4b)
  LED               IN=0
"""
import json, os, math

HERE = os.path.dirname(os.path.abspath(__file__))
CHIPS_DIR = os.path.join(HERE, "..", "PC_EYE_OS", "Chips")

# output pin ids of built-ins (for OutputPinColourInfo)
BUILTIN_OUT_PINS = {
    "8-1BIT": [1, 2, 3, 4, 5, 6, 7, 8],
    "4-1BIT": [1, 2, 3, 4],
    "1-4BIT": [4],
    "1-8BIT": [8],
    "8-4BIT": [1, 2],
    "4-8BIT": [2],
    "RGB DISPLAY": [8, 9, 10],
    "LED": [],
    "NAND": [2],
}


class Chip:
    def __init__(self, name, colour):
        self.name = name
        self.colour = colour
        self.inputs, self.outputs, self.subs, self.wires = [], [], [], []
        self._seq = 0
        self._used = set()

    # ---- ids ----
    def _newid(self):
        self._seq += 1
        # deterministic, unique, in the same numeric range the editor uses
        v = (self._seq * 2654435761) % 2147483647
        while v in self._used:
            v = (v + 1) % 2147483647
        self._used.add(v)
        return v

    # ---- pins of this chip: address is (pinID, 0) ----
    def inp(self, name, bits=1):
        pid = self._newid()
        self.inputs.append({"Name": name, "ID": pid, "Position": {"x": -6.0, "y": 0.0},
                            "BitCount": bits, "Colour": 0, "ValueDisplayMode": 0})
        return (pid, 0)

    def out(self, name, bits=1):
        pid = self._newid()
        self.outputs.append({"Name": name, "ID": pid, "Position": {"x": 1.0, "y": 0.0},
                             "BitCount": bits, "Colour": 0, "ValueDisplayMode": 0})
        return (pid, 0)

    # ---- subchips: address is (instanceID, pinID) ----
    def sub(self, name):
        sid = self._newid()
        self.subs.append({"Name": name, "ID": sid, "Label": "",
                          "Position": {"x": 0.0, "y": 0.0},
                          "OutputPinColourInfo": [], "InternalData": None})
        return sid

    def pin(self, sid, pinmap, pinname):
        return (sid, pinmap[pinname])

    # ---- wiring ----
    def wire(self, src, dst):
        self.wires.append({
            "SourcePinAddress": {"PinID": int(src[1]), "PinOwnerID": int(src[0])},
            "TargetPinAddress": {"PinID": int(dst[1]), "PinOwnerID": int(dst[0])},
            "ConnectionType": 0, "ConnectedWireIndex": -1,
            "ConnectedWireSegmentIndex": -1,
            "Points": [{"x": 0.0, "y": 0.0}, {"x": 0.0, "y": 0.0}],
        })

    # ---- composite helpers (all talk in (owner,pin) handles) ----
    def split(self, bus, n):
        """bus -> [bit0 .. bit{n-1}]"""
        s = self.sub(f"{n}-1BIT")
        self.wire(bus, (s, 0))
        return [(s, n - i) for i in range(n)]

    def merge(self, n, bits):
        """[bit0 .. bit{n-1}] -> bus"""
        m = self.sub(f"1-{n}BIT")
        for i, b in enumerate(bits):
            self.wire(b, (m, n - 1 - i))
        return (m, n)

    def gate(self, kind, reg, a, b):
        g = self.sub(kind)
        self.wire(a, self.pin(g, reg[kind], "IN A"))
        self.wire(b, self.pin(g, reg[kind], "IN B"))
        return self.pin(g, reg[kind], "OUT")

    def inv(self, reg, a):
        g = self.sub("NOT")
        self.wire(a, self.pin(g, reg["NOT"], "IN"))
        return self.pin(g, reg["NOT"], "OUT")

    # ---- emit ----
    def to_json(self, reg):
        n = len(self.subs)
        cols = min(4, max(1, math.ceil(math.sqrt(max(n, 1)))))
        rows = max(1, math.ceil(n / cols))
        for i, p in enumerate(self.inputs):
            p["Position"] = {"x": -6.0, "y": -0.5 * i}
        for i, p in enumerate(self.outputs):
            p["Position"] = {"x": round(-4.0 + 1.7 * cols + 1.2, 3), "y": -0.5 * i}
        for i, s in enumerate(self.subs):
            c, r = divmod(i, rows)
            s["Position"] = {"x": round(-4.0 + 1.7 * c, 3), "y": round(-0.8 * r, 3)}
            ids = BUILTIN_OUT_PINS.get(s["Name"])
            if ids is None:
                ids = [p["ID"] for p in json.load(open(
                    os.path.join(CHIPS_DIR, s["Name"] + ".json")))["OutputPins"]]
            s["OutputPinColourInfo"] = [{"PinColour": 0, "PinID": i2} for i2 in ids]
        return {
            "DLSVersion": "2.1.6",
            "Name": self.name,
            "NameLocation": 0,
            "ChipType": 0,
            "Size": {"x": round(max(1.0, 0.45 + 0.12 * max(len(self.inputs), len(self.outputs))), 3),
                     "y": round(max(0.5, 0.25 * max(len(self.inputs), len(self.outputs))), 3)},
            "Colour": self.colour,
            "InputPins": self.inputs,
            "OutputPins": self.outputs,
            "SubChips": self.subs,
            "Wires": self.wires,
            "Displays": [],
        }


def load_registry():
    reg = {}
    for f in os.listdir(CHIPS_DIR):
        if f.endswith(".json"):
            d = json.load(open(os.path.join(CHIPS_DIR, f)))
            reg[d["Name"]] = {p["Name"]: p["ID"] for p in d["InputPins"] + d["OutputPins"]}
    return reg


# --------------------------------------------------------------------------
# HDMI TYPE A: the 19-pin connector plus its differential receivers
# --------------------------------------------------------------------------
HDMI_PINS = [
    ("1 D2+", 8), ("2 D2 SHIELD", 1), ("3 D2-", 8),
    ("4 D1+", 8), ("5 D1 SHIELD", 1), ("6 D1-", 8),
    ("7 D0+", 8), ("8 D0 SHIELD", 1), ("9 D0-", 8),
    ("10 CLK+", 1), ("11 CLK SHIELD", 1), ("12 CLK-", 1),
    ("13 CEC", 1), ("14 RESERVED", 1), ("15 SCL", 1), ("16 SDA", 1),
    ("17 GND", 1), ("18 +5V", 1), ("19 HPD", 1),
]


def build_hdmi_type_a(reg):
    c = Chip("HDMI TYPE A", {"r": 0.1, "g": 0.1, "b": 0.14, "a": 1})
    p = {n: c.inp(n, b) for n, b in HDMI_PINS}
    d2 = c.out("D2", 8)
    d1 = c.out("D1", 8)
    d0 = c.out("D0", 8)
    clk = c.out("CLK")
    link = c.out("LINK")

    lanes = [("D2", p["1 D2+"], p["3 D2-"], d2),
             ("D1", p["4 D1+"], p["6 D1-"], d1),
             ("D0", p["7 D0+"], p["9 D0-"], d0)]

    acc = None
    for _, pos, neg, outpin in lanes:
        pb = c.split(pos, 8)   # + line bits
        nb = c.split(neg, 8)   # - line bits
        # recovered data is the + line, passed through
        c.wire(pos, outpin)
        # a pair is valid when every bit differs; AND-reduce the XORs
        lane_valid = None
        for i in range(8):
            x = c.gate("XOR", reg, pb[i], nb[i])
            lane_valid = x if lane_valid is None else c.gate("OND", reg, lane_valid, x)
        acc = lane_valid if acc is None else c.gate("OND", reg, acc, lane_valid)

    cx = c.gate("XOR", reg, p["10 CLK+"], p["12 CLK-"])  # clock pair receiver
    c.wire(p["10 CLK+"], clk)
    acc = c.gate("OND", reg, acc, cx)
    acc = c.gate("OND", reg, acc, p["18 +5V"])
    c.wire(acc, link)
    return c


# --------------------------------------------------------------------------
# TMDS 9B ENCODER (stage 1 of the TMDS 8b/10b link encoding)
# --------------------------------------------------------------------------
def build_tmds_encoder(reg):
    c = Chip("TMDS 9B ENCODER", {"r": 0.04, "g": 0.32, "b": 0.5, "a": 1})
    D = c.inp("D", 8)
    DE = c.inp("DE")
    Q = c.out("Q", 8)
    Q8 = c.out("Q8")

    d = c.split(D, 8)
    d0 = d[0]
    n_d0 = c.inv(reg, d0)

    # transition-minimised chain: q[i] = q[i-1] (X)NOR d[i], chosen by d[0]
    q = [d0]
    for i in range(1, 8):
        xr = c.gate("XOR", reg, q[i - 1], d[i])
        xn = c.gate("XNOR", reg, q[i - 1], d[i])
        a = c.gate("OND", reg, xr, d0)
        b = c.gate("OND", reg, xn, n_d0)
        q.append(c.gate("OR", reg, a, b))

    # N1{D} = number of ones, via half adders and 4-bit adders
    nibbles = []
    for k in range(4):
        h = c.sub("HALF ADDER")
        c.wire(d[2 * k], c.pin(h, reg["HALF ADDER"], "IN A"))
        c.wire(d[2 * k + 1], c.pin(h, reg["HALF ADDER"], "IN B"))
        # 2-bit pair value (bit1 = carry, bit0 = sum) widened to 4 bits
        m = c.sub("1-4BIT")
        c.wire(c.pin(h, reg["HALF ADDER"], "SUM"), (m, 3))
        c.wire(c.pin(h, reg["HALF ADDER"], "C OUT"), (m, 2))
        nibbles.append((m, 4))

    def add4(a, b):
        g = c.sub("4BIT FULL ADDER")
        c.wire(a, c.pin(g, reg["4BIT FULL ADDER"], "IN A"))
        c.wire(b, c.pin(g, reg["4BIT FULL ADDER"], "IN B"))
        return c.pin(g, reg["4BIT FULL ADDER"], "SUM")

    n1 = add4(add4(nibbles[0], nibbles[1]), add4(nibbles[2], nibbles[3]))

    nb = c.split(n1, 4)
    n3, n2, n1b, n0b = nb[3], nb[2], nb[1], nb[0]
    lt4 = c.gate("NOR", reg, n3, n2)                                    # N1 < 4
    nn3, nn1, nn0 = c.inv(reg, n3), c.inv(reg, n1b), c.inv(reg, n0b)
    eq4 = c.gate("OND", reg, c.gate("OND", reg, nn3, n2),
                 c.gate("OND", reg, nn1, nn0))                          # N1 == 4
    q8 = c.gate("OR", reg, lt4, c.gate("OND", reg, eq4, d0))

    # data-enable: control periods encode to zero
    gated = [c.gate("OND", reg, q[i], DE) for i in range(8)]
    c.wire(c.merge(8, gated), Q)
    c.wire(c.gate("OND", reg, q8, DE), Q8)
    return c


# --------------------------------------------------------------------------
# TMDS 9B DECODER
# --------------------------------------------------------------------------
def build_tmds_decoder(reg):
    c = Chip("TMDS 9B DECODER", {"r": 0.04, "g": 0.42, "b": 0.42, "a": 1})
    Qb = c.inp("Q", 8)
    D = c.out("D", 8)
    q = c.split(Qb, 8)
    q0 = q[0]
    n_q0 = c.inv(reg, q0)
    d = [q0]
    for i in range(1, 8):
        xr = c.gate("XOR", reg, q[i], q[i - 1])
        xn = c.gate("XNOR", reg, q[i], q[i - 1])
        d.append(c.gate("OR", reg, c.gate("OND", reg, xr, q0),
                        c.gate("OND", reg, xn, n_q0)))
    c.wire(c.merge(8, d), D)
    return c


# --------------------------------------------------------------------------
# RGB SCREEN (replaces DISP)
# --------------------------------------------------------------------------
def build_rgb_screen(reg):
    c = Chip("RGB SCREEN", {"r": 0.15, "g": 0.15, "b": 0.2, "a": 1})
    ADDR = c.inp("ADDR", 8)
    RED = c.inp("RED", 4)
    GREEN = c.inp("GREEN", 4)
    BLUE = c.inp("BLUE", 4)
    WRITE = c.inp("WRITE")
    CLOCK = c.inp("CLOCK")
    ON = c.inp("ON")
    ROUT = c.out("R OUT", 4)
    GOUT = c.out("G OUT", 4)
    BOUT = c.out("B OUT", 4)

    disp = c.sub("RGB DISPLAY")
    w = c.gate("OND", reg, WRITE, ON)     # nothing is written while off
    clk = c.gate("OND", reg, CLOCK, ON)   # and nothing is clocked

    c.wire(ADDR, (disp, 0))
    c.wire(RED, (disp, 1))
    c.wire(GREEN, (disp, 2))
    c.wire(BLUE, (disp, 3))
    c.wire(w, (disp, 5))     # WRITE
    c.wire(w, (disp, 6))     # REFRESH = write-through, so writes show up
    c.wire(clk, (disp, 7))   # CLOCK
    c.wire((disp, 8), ROUT)
    c.wire((disp, 9), GOUT)
    c.wire((disp, 10), BOUT)

    led = c.sub("LED")       # power indicator
    c.wire(ON, (led, 0))
    return c


# --------------------------------------------------------------------------
# HDMI DISPLAY: 19-pin input -> decode -> screen
# --------------------------------------------------------------------------
def build_hdmi_display(reg):
    c = Chip("HDMI DISPLAY", {"r": 0.07, "g": 0.09, "b": 0.15, "a": 1})
    p = {n: c.inp(n, b) for n, b in HDMI_PINS}
    ADDR = c.inp("ADDR", 8)
    WRITE = c.inp("WRITE")
    CLOCK = c.inp("CLOCK")
    ON = c.inp("ON")

    conn = c.sub("HDMI TYPE A")
    for n, _ in HDMI_PINS:
        c.wire(p[n], c.pin(conn, reg["HDMI TYPE A"], n))

    scr = c.sub("RGB SCREEN")
    # TMDS channel 0 = blue, 1 = green, 2 = red
    for lane, colour, screen_pin in (("D0", "BLUE", "BLUE"),
                                     ("D1", "GREEN", "GREEN"),
                                     ("D2", "RED", "RED")):
        dec = c.sub("TMDS 9B DECODER")
        c.wire(c.pin(conn, reg["HDMI TYPE A"], lane),
               c.pin(dec, reg["TMDS 9B DECODER"], "Q"))
        sp = c.sub("8-4BIT")
        c.wire(c.pin(dec, reg["TMDS 9B DECODER"], "D"), (sp, 0))
        c.wire((sp, 1), c.pin(scr, reg["RGB SCREEN"], screen_pin))  # high nibble

    c.wire(ADDR, c.pin(scr, reg["RGB SCREEN"], "ADDR"))
    c.wire(WRITE, c.pin(scr, reg["RGB SCREEN"], "WRITE"))
    c.wire(CLOCK, c.pin(scr, reg["RGB SCREEN"], "CLOCK"))
    c.wire(ON, c.pin(scr, reg["RGB SCREEN"], "ON"))
    return c


BUILD_ORDER = [build_hdmi_type_a, build_tmds_encoder, build_tmds_decoder,
               build_rgb_screen, build_hdmi_display]


def main():
    reg = load_registry()
    for fn in BUILD_ORDER:
        chip = fn(reg)
        d = chip.to_json(reg)
        json.dump(d, open(os.path.join(CHIPS_DIR, d["Name"] + ".json"), "w"), indent=2)
        reg[d["Name"]] = {q["Name"]: q["ID"] for q in d["InputPins"] + d["OutputPins"]}
        print(f"wrote {d['Name']:18} {len(d['InputPins']):2} in, {len(d['OutputPins'])} out, "
              f"{len(d['SubChips']):3} subchips, {len(d['Wires']):4} wires")


if __name__ == "__main__":
    main()
