"""Minimal Digital Logic Sim (DLS 2.1.6) netlist simulator.

Every custom chip in these projects bottoms out in built-in NAND gates plus
built-in bus split/merge helpers, so chips can be flattened and evaluated.
Unconnected inputs read as 0 (DLS default).

Bus convention observed in these projects:
  4-1BIT / 8-1BIT  (splitter): input pin 0, output pins 1..N ; pin k = bit (N-k)
  1-4BIT / 1-8BIT  (merge):    input pins 0..N-1, output pin N ; pin j = bit (N-1-j)
  8-4BIT           (nibble split, 8 in): out pin 1 = high nibble, out pin 2 = low
  4-8BIT           (nibble merge):       in pin 0 = high nibble, in pin 1 = low
"""
import json, glob, os, collections

SPLITSRC = {"4-1BIT": 4, "8-1BIT": 8}
SPLIT    = {"1-4BIT": 4, "1-8BIT": 8}
NIBSPLIT = {"8-4BIT": 8}
NIBMERGE = {"4-8BIT": 8}
NAND_IN, NAND_OUT = (0, 1), 2


class Compiled:
    def __init__(self):
        self.nets = []          # list of net ids
        self.nand = []          # (net0, net1, netout)
        self.busops = []        # (kind, w, [nets])
        self.ins = {}           # name -> net
        self.outs = {}          # name -> net
        self.roms = []          # (addr, outB, outA) net triples
        self.displays = []      # ([in nets 0..7], [out nets r,g,b])


class Project:
    def __init__(self, root):
        self.chips = {}
        for f in glob.glob(os.path.join(root, "Chips", "*.json")):
            d = json.load(open(f))
            self.chips[d["Name"]] = d
        self._cache = {}
        self.rom = [0] * 256

    def compile(self, chipname):
        if chipname in self._cache:
            return self._cache[chipname]
        chip = self.chips[chipname]
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            r = x
            while parent[r] != r:
                r = parent[r]
            while parent[x] != r:
                parent[x], x = r, parent[x]
            return r

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        c = Compiled()
        rom_insts, disp_insts = [], []
        nand_nodes = []
        bus_nodes = []
        boundary = []   # (kind, name, node)

        def walk(ch, path):
            top = (path == ())
            for p in ch.get("InputPins", []):
                find((path, p["ID"], 0))
                if top: boundary.append(("IN", p["Name"], (path, p["ID"], 0), p.get("BitCount", 1)))
            for p in ch.get("OutputPins", []):
                find((path, p["ID"], 0))
                if top: boundary.append(("OUT", p["Name"], (path, p["ID"], 0), p.get("BitCount", 1)))
            for s in ch.get("SubChips", []):
                iid, nm = s["ID"], s["Name"]
                sub = self.chips.get(nm)
                if nm == "NAND":
                    for pid in (0, 1, 2):
                        find((path, iid, pid))
                    nand_nodes.append((path, iid))
                elif sub is not None:
                    for p in sub.get("InputPins", []) + sub.get("OutputPins", []):
                        find((path, iid, p["ID"]))
                        union((path, iid, p["ID"]), (path + (iid,), p["ID"], 0))
                elif nm == "ROM 256x16":
                    for pid in (0, 1, 2):
                        find((path, iid, pid))
                    rom_insts.append((path, iid))
                elif nm == "RGB DISPLAY":
                    for pid in range(11):
                        find((path, iid, pid))
                    disp_insts.append((path, iid))
                elif nm in SPLITSRC or nm in SPLIT or nm in NIBSPLIT or nm in NIBMERGE:
                    w = SPLITSRC.get(nm) or SPLIT.get(nm) or 8
                    pins = list(range(0, w + 2)) if not (nm in SPLIT or nm in SPLITSRC) else list(range(0, w + 2))
                    for pid in pins:
                        find((path, iid, pid))
                    bus_nodes.append((path, iid, nm, w))
                else:
                    bus_nodes.append((path, iid, "OPAQUE:" + nm, 1))
            for w_ in ch.get("Wires", []):
                a, b = w_["SourcePinAddress"], w_["TargetPinAddress"]
                union((path, a["PinOwnerID"], a["PinID"]), (path, b["PinOwnerID"], b["PinID"]))
            for s in ch.get("SubChips", []):
                if s["Name"] in self.chips:
                    walk(self.chips[s["Name"]], path + (s["ID"],))

        walk(chip, ())
        netid = {}
        for node in list(parent):
            r = find(node)
            if r not in netid:
                netid[r] = len(netid)
        def n(node):
            r = find(node)
            return netid.get(r, -1)

        for path, iid in nand_nodes:
            c.nand.append((n((path, iid, 0)), n((path, iid, 1)), n((path, iid, 2))))
        for path, iid, nm, w in bus_nodes:
            if nm in SPLITSRC:
                c.busops.append(("split", w, n((path, iid, 0)), [n((path, iid, k)) for k in range(1, w + 1)]))
            elif nm in SPLIT:
                c.busops.append(("merge", w, [n((path, iid, j)) for j in range(w)], n((path, iid, w))))
            elif nm in NIBSPLIT:
                c.busops.append(("nibsplit", 8, n((path, iid, 0)), [n((path, iid, 1)), n((path, iid, 2))]))
            elif nm in NIBMERGE:
                c.busops.append(("nibmerge", 8, [n((path, iid, 0)), n((path, iid, 1))], n((path, iid, 2))))
        for path, iid in rom_insts:
            c.roms.append((n((path, iid, 0)), n((path, iid, 1)), n((path, iid, 2))))
        for path, iid in disp_insts:
            c.displays.append(([n((path, iid, k)) for k in range(8)],
                               [n((path, iid, k)) for k in (8, 9, 10)]))
        c.nnets = len(netid)
        for kind, name, node, bits in boundary:
            if kind == "IN":
                c.ins[name] = n(node)
            else:
                c.outs[name] = n(node)
        self._cache[chipname] = c
        return c

    def load_rom(self, hexpath):
        img = [0] * 256
        for line in open(hexpath):
            line = line.split("#")[0].strip()
            if not line:
                continue
            parts = line.split()
            img[int(parts[0], 16)] = int(parts[1], 16)
        self.rom = img
        return img

    def sim(self, chipname):
        return Sim(self, chipname)

    def run(self, chipname, cin, sweeps=200):
        c = self.compile(chipname)
        val = [0] * c.nnets
        for k, v in c.ins.items():
            val[v] = cin.get(k, 0)
        for _ in range(sweeps):
            nv = list(val)
            for a, b, o in c.nand:
                nv[o] = 0 if (val[a] and val[b]) else 1
            for kind, w, src, dst in c.busops:
                if kind == "split":
                    v = val[src]
                    for i, d in enumerate(dst):
                        nv[d] = (v >> (w - 1 - i)) & 1
                elif kind == "merge":
                    v = 0
                    for s in src:
                        v = (v << 1) | (val[s] & 1)
                    nv[dst] = v
                elif kind == "nibsplit":
                    v = val[src]
                    nv[dst[0]] = (v >> 4) & 0xF
                    nv[dst[1]] = v & 0xF
                elif kind == "nibmerge":
                    nv[dst] = ((val[src[0]] & 0xF) << 4) | (val[src[1]] & 0xF)
            if nv == val:
                break
            val = nv
        return {k: val[v] for k, v in c.outs.items()}


class Sim:
    """State-preserving evaluator: call step() repeatedly to clock a circuit.

    Bistable nets keep their previous value because the fixed-point sweep starts
    from the last settled state, matching DLS's incremental updating.
    """

    def __init__(self, proj, chipname):
        self.c = proj.compile(chipname)
        self.proj = proj
        self.val = [0] * self.c.nnets
        self.back = [[0] * 256 for _ in self.c.displays]
        self.front = [[0] * 256 for _ in self.c.displays]
        self.prev_clk = [0] * len(self.c.displays)

    def _settle(self, sweeps):
        """In-place (Gauss-Seidel) iteration: cross-coupled latches converge,
        and feed-forward chains settle in roughly one pass."""
        c = self.c
        val = self.val
        for _ in range(sweeps):
            changed = False
            for a, b, o in c.nand:
                nv = 0 if (val[a] and val[b]) else 1
                if val[o] != nv:
                    val[o] = nv
                    changed = True
            for kind, w, src, dst in c.busops:
                if kind == "split":
                    v = val[src]
                    for i, d in enumerate(dst):
                        nv = (v >> (w - 1 - i)) & 1
                        if val[d] != nv:
                            val[d] = nv; changed = True
                elif kind == "merge":
                    v = 0
                    for s_ in src:
                        v = (v << 1) | (val[s_] & 1)
                    if val[dst] != v:
                        val[dst] = v; changed = True
                elif kind == "nibsplit":
                    v = val[src]
                    for d, nv in ((dst[0], (v >> 4) & 0xF), (dst[1], v & 0xF)):
                        if val[d] != nv:
                            val[d] = nv; changed = True
                elif kind == "nibmerge":
                    nv = ((val[src[0]] & 0xF) << 4) | (val[src[1]] & 0xF)
                    if val[dst] != nv:
                        val[dst] = nv; changed = True
            for addr_n, outb_n, outa_n in c.roms:
                w16 = self.proj.rom[val[addr_n] & 0xFF]
                for net, nv in ((outb_n, (w16 >> 8) & 0xFF), (outa_n, w16 & 0xFF)):
                    if val[net] != nv:
                        val[net] = nv; changed = True
            for di, (in_nets, out_nets) in enumerate(c.displays):
                col = self.front[di][val[in_nets[0]] & 0xFF]
                for net, nv in ((out_nets[0], col & 0xF), (out_nets[1], (col >> 4) & 0xF),
                                (out_nets[2], (col >> 8) & 0xF)):
                    if val[net] != nv:
                        val[net] = nv; changed = True
            if not changed:
                return True
        return False

    def step(self, cin, sweeps=200):
        c = self.c
        pre = list(self.val)                 # state before this step
        for k, v in c.ins.items():
            self.val[v] = cin.get(k, 0)

        self.settled = self._settle(sweeps)

        # RGB panel: act on the rising edge using the values sampled before it
        changed = False
        for di, (in_nets, out_nets) in enumerate(c.displays):
            clk = self.val[in_nets[7]]
            if clk and not self.prev_clk[di]:
                addr = pre[in_nets[0]] & 0xFF
                r, g, b = pre[in_nets[1]] & 0xF, pre[in_nets[2]] & 0xF, pre[in_nets[3]] & 0xF
                if pre[in_nets[4]]:                  # RESET
                    self.back[di] = [0] * 256
                elif pre[in_nets[5]]:                # WRITE
                    self.back[di][addr] = r | (g << 4) | (b << 8)
                if pre[in_nets[6]]:                  # REFRESH
                    self.front[di] = list(self.back[di])
                changed = True
            self.prev_clk[di] = clk
        if changed:
            self.settled = self._settle(sweeps) and self.settled
        return self.read()

    def framebuffer(self):
        return list(self.front[0]) if self.front else []

    def read(self):
        return {k: self.val[v] for k, v in self.c.outs.items()}
