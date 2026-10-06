"""Evaluate the master timeline at a given frame: characters, hands, props, lights, UV fluorescence, camera.

Acting vocabulary (episodes/<ep>/acting.json, times already resolved by timeline.py):
  channel keys   [t, value, dur=0.35]  hold the previous value, then ease to `value`, arriving at t
  hand keys      [t, target, dur=0.4]  same easing, target is one of:
                   "rest" | "home" | "<anchor>" | "prop:<name>" | "fridge_handle" | "menu_L" | "menu_R"
                   {"bone": name, "off": [x,y,z]}           offset in one of this character's bones
                   {"body": [x,y,z]}                         offset in the character root frame
                   {"carry": prop, "pos": [..], "rot": [..], "space": "world"|"self"}
                                                             put the HELD prop at that pose
  prop events    [t, "grab", "patrick.R"|"patrick.L"|"bear.R"|"fridge_door"] / [t, "release", {"z": 1.08}]
"""
import math
import random

from mathutils import Euler, Matrix, Quaternion, Vector

from characters import Ry, Rz, Tr, frame_from


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, e):
    if isinstance(a, dict):
        return {k: lerp(a[k], b[k], e) for k in a}
    if isinstance(a, (list, tuple)):
        return [x + (y - x) * e for x, y in zip(a, b)]
    return a + (b - a) * e


def channel(keys, t, default):
    if not keys:
        return default
    v = keys[0][1]
    for k in keys:
        kt, kv = k[0], k[1]
        d = k[2] if len(k) > 2 else 0.35
        if t >= kt:
            v = kv
        elif t > kt - d:
            v = lerp(v, kv, ease((t - (kt - d)) / d))
            break
        else:
            break
    return v


def blend_M(M0, M1, e):
    q0, q1 = M0.to_quaternion(), M1.to_quaternion()
    if q0.dot(q1) < 0:
        q1 = -q1
    M = q0.slerp(q1, e).to_matrix().to_4x4()
    M.translation = M0.translation.lerp(M1.translation, e)
    return M


def eul(rot):
    return Euler([math.radians(a) for a in rot], "XYZ")


def place(pos, yaw, rot=None):
    M = Matrix.Translation(pos) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
    return M @ eul(rot).to_matrix().to_4x4() if rot else M


def pose_M(k):
    """{"pos", "yaw", "rot"?} -> matrix"""
    return place(k["pos"], k.get("yaw", 0.0), k.get("rot"))


class Blinks:
    def __init__(self, scripted, seed, lo, hi, dur):
        r = random.Random(seed)
        self.ev = [(t, d) for t, d in scripted]
        t = r.uniform(0.6, 2.0)
        while t < 95:
            if all(abs(t - s) > 0.9 for s, _ in scripted):
                self.ev.append((t, dur))
            t += r.uniform(lo, hi)

    def __call__(self, t):
        v = 0.0
        for s, d in self.ev:
            if s <= t <= s + d:
                x = (t - s) / d
                v = max(v, ease(x / 0.35) if x < 0.35 else 1.0 if x < 0.45 else 1 - ease((x - 0.45) / 0.55))
        return v


class Performance:
    def __init__(self, tl, setcfg, S, pat, bear):
        self.tl, self.cfg, self.S = tl, setcfg, S
        self.fps = tl["fps"]
        self.rigs = {"patrick": pat, "bear": bear}
        A = tl["acting"]
        self.A = A
        self.blink = {
            "patrick": Blinks([(k[0], k[1]) for k in A["patrick"].get("blinks", [])], 3, 2.2, 4.6, 0.16),
            "bear": Blinks([(k[0], k[1]) for k in A["bear"].get("blinks", [])], 9, 4.0, 7.5, 0.3),
        }
        self.mouth = tl["mouth"]
        self.B = {"patrick": {}, "bear": {}}
        self.handM = {}
        # props: world matrices + attachment state
        P = setcfg["props"]
        fr = setcfg["fridge"]
        self.fridge_M = S["fridge_M"]
        self.fdim = S["fridge_dim"]
        self.door_angle = 0.0
        self.propM = {name: pose_M(P[name]) for name in ("glass", "uvlamp")}
        self.propM["bottle"] = self.door_M(0.0) @ Matrix.Translation(fr["bottle_in_door"])
        self.paths = A.get("paths", {})
        for name in S["props"]:
            if name in self.propM or name in ("fridge_door", "dimmer_knob", "menu_L", "menu_R", "register"):
                continue
            if name in self.paths:
                self.propM[name] = pose_M(channel(self.paths[name], 0.0, None))
            elif name in P:
                self.propM[name] = pose_M(P[name])
        self.init_attach = dict(setcfg.get("extras", {}).get("attach", {}))
        self.attach = {}  # prop -> (parent key, offset)
        self.settle = {}  # prop -> (t0, M_from, M_to)
        self.events = sorted([(e[0], name, e[1], e[2] if len(e) > 2 else None, e[3] if len(e) > 3 else {})
                              for name, evs in A.get("props", {}).items() for e in evs], key=lambda x: x[0])
        self.snap = {}  # prop -> (t0, dur, offset_from): grab that settles the prop into its grip
        self.ev_i = 0
        self.grips = {k: (Matrix.Translation(v["pos"]) @ eul(v["rot"]).to_matrix().to_4x4()) for k, v in setcfg["grips"].items()}
        self.from_path = {}  # prop -> (t0, M_from, dur): blend back onto its swim path after a release
        # ripples on the tank water: [t0, t1, emitter, interval, strength]
        self.rip_ev = []
        for r in A.get("ripples", []):
            t, iv = r[0], r[3]
            while t < r[1] - 1e-6:
                self.rip_ev.append([t, r[2], r[4] if len(r) > 4 else 1.0, None])
                t += iv
        self.rip_ev.sort(key=lambda e: e[0])

    # ------------------------------------------------------------ helpers
    def door_M(self, ang):
        w, d = self.fdim["w"], self.fdim["d"]
        return self.fridge_M @ Tr(w / 2, -d / 2, 0) @ Rz(ang)

    def menu_Ms(self, t):
        k = channel(self.A["props_pose"]["menu"], t, None)
        M = Matrix.Translation(k["pos"]) @ eul(k["rot"]).to_matrix().to_4x4()
        MR = M @ Ry(-178 * k["close"])
        return M, MR

    def root_M(self, who, t):
        base = self.cfg["characters"][who]
        r = channel(self.A[who].get("root", []), t, {"pos": base["pos"], "yaw": base["yaw"]})
        return place(r["pos"], r["yaw"])

    def target(self, who, side, tg, t, rootM):
        """-> (position Vector, Quaternion | None)"""
        B = self.B[who]
        if isinstance(tg, str):
            if tg == "rest":
                return Vector(self.cfg["anchors"][f"{'pat' if who == 'patrick' else 'bear'}_rest_{side}"]), None
            if tg == "home":
                return rootM @ Vector(self.cfg["home"][who][side]), None
            if tg.startswith("prop:"):
                name = tg[5:]
                M = self.propM[name] @ self.grips[name]
                return M.translation.copy(), M.to_quaternion()
            if tg == "fridge_handle":
                w, h = self.fdim["w"], self.fdim["h"]
                M = self.door_M(self.door_angle) @ Tr(-w + 0.05, -0.095, h / 2)
                return M.translation.copy(), M.to_quaternion()
            if tg == "dimmer":
                M = self.dimmer_M @ self.grips["dimmer"]
                return M.translation.copy(), M.to_quaternion()
            if tg in ("menu_L", "menu_R"):
                M, MR = self.menu_Ms(t)
                p = (M @ Vector((-0.235, -0.02, 0.0))) if tg == "menu_L" else (MR @ Vector((0.235, -0.02, 0.0)))
                return p, None
            return Vector(self.cfg["anchors"][tg]), None
        if "bone" in tg:
            M = B.get(tg["bone"])
            if M is None:
                return rootM @ Vector(self.cfg["home"][who][side]), None
            return M @ Vector(tg.get("off", (0, 0, 0))), None
        if "world" in tg:
            return Vector(tg["world"]), (eul(tg["rot"]).to_quaternion() if "rot" in tg else None)
        if "body" in tg:
            return rootM @ Vector(tg["body"]), (None if "rot" not in tg else (rootM.to_quaternion() @ eul(tg["rot"]).to_quaternion()))
        if "carry" in tg:
            name = tg["carry"]
            Mp = Matrix.Translation(tg["pos"]) @ eul(tg.get("rot", (0, 0, 0))).to_matrix().to_4x4()
            if tg.get("space") == "self":
                Mp = rootM @ Mp
            att = self.attach.get(name)
            off = att[1] if att else self.grips[name].inverted()
            Hm = Mp @ off.inverted()
            return Hm.translation.copy(), Hm.to_quaternion()
        raise ValueError(tg)

    def auto_q(self, who, side, pos, rootM):
        B = self.B[who]
        S = B.get(f"upper_{side}")
        sp = S.translation if S is not None else rootM.translation
        up = rootM.to_3x3().col[2]
        return frame_from(pos, pos - sp, up).to_quaternion()

    def hand(self, who, side, t, rootM):
        keys = self.A[who].get("hands", {}).get(side, [[0.0, "rest"]])
        cur = None
        for i, k in enumerate(keys):
            kt, tg = k[0], k[1]
            d = k[2] if len(k) > 2 else 0.4
            if t >= kt:
                cur = (tg, None)
            elif t > kt - d:
                cur = (cur[0] if cur else tg, (tg, ease((t - (kt - d)) / d)))
                break
            else:
                break
        if cur is None:
            cur = (keys[0][1], None)
        p0, q0 = self.target(who, side, cur[0], t, rootM)
        q0 = q0 or self.auto_q(who, side, p0, rootM)
        if cur[1] is None:
            return p0, q0
        p1, q1 = self.target(who, side, cur[1][0], t, rootM)
        q1 = q1 or self.auto_q(who, side, p1, rootM)
        e = cur[1][1]
        if q0.dot(q1) < 0:
            q1 = -q1
        return p0.lerp(p1, e), q0.slerp(q1, e)

    def chans(self, who, t):
        C = self.A[who].get("channels", {})
        ch = {k: channel(v, t, 0.0) for k, v in C.items()}
        f = min(int(round(t * self.fps)), len(self.mouth[who]) - 1)
        m = self.mouth[who][f]
        ch["mouth"] = m
        base_lid = ch.get("lid", 0.12 if who == "patrick" else 0.35)
        ch["lid"] = base_lid + (1 - base_lid) * self.blink[who](t)
        ch["breath"] = math.sin(2 * math.pi * t / (3.6 if who == "patrick" else 4.8))
        hp, hy, hr = ch.get("head", [0, 0, 0])
        # speech adds a small, restrained head motion driven by the actual audio
        mm = sum(self.mouth[who][max(0, f - k)] for k in range(6)) / 6
        ch["head"] = (hp + (2.2 if who == "patrick" else 1.4) * mm, hy, hr)
        ch["tail"] = 3 * math.sin(2 * math.pi * t / 5.3)
        if who == "bear":
            tap = 0.0
            for ev in self.A["bear"].get("taps", []):
                t0, n, iv = ev[0], ev[1], ev[2]
                if t0 <= t <= t0 + n * iv:
                    x = ((t - t0) / iv) % 1.0
                    tap = math.sin(math.pi * x) ** 2
            ch["tap_R"] = tap
        return ch

    # ------------------------------------------------------------ main
    def evaluate(self, f):
        t = f / self.fps
        A = self.A
        out = {}
        # door & dimmer first (targets depend on them)
        self.door_angle = channel(A["props_pose"].get("fridge_door", []), t, 0.0)
        dial = channel(A["props_pose"].get("dimmer", []), t, 0.0)
        self.dimmer_M = self.S["dimmer_M"]
        out[self.S["props"]["fridge_door"]] = self.door_M(self.door_angle)
        out[self.S["props"]["dimmer_knob"]] = self.dimmer_M @ Rz(-dial)
        menuM, menuR = self.menu_Ms(t)
        out[self.S["props"]["menu_L"]] = menuM
        out[self.S["props"]["menu_R"]] = menuR
        for name in self.paths:
            if name not in self.attach and name not in self.from_path:
                self.propM[name] = self.path_M(name, t)

        for who in ("patrick", "bear"):
            rootM = self.root_M(who, t)
            ch = self.chans(who, t)
            hands = {s: self.hand(who, s, t, rootM) for s in "LR"}
            parts, B = self.rigs[who].pose(rootM, ch, hands)
            self.B[who] = B
            for ob, M in parts:
                out[ob] = M
        for name, a in list(self.init_attach.items()):  # props that start in a pocket, on a hook, ...
            off = Matrix.Translation(a["pos"]) @ eul(a.get("rot", (0, 0, 0))).to_matrix().to_4x4()
            self.attach[name] = (a["parent"], off)
            self.propM[name] = self.parent_M(a["parent"]) @ off
            del self.init_attach[name]

        # prop events at this frame
        while self.ev_i < len(self.events) and self.events[self.ev_i][0] <= t + 1e-6:
            _, name, kind, arg, opt = self.events[self.ev_i]
            if kind == "grab":
                P = self.parent_M(arg)
                self.attach[name] = (arg, P.inverted() @ self.propM[name])
                if opt.get("snap"):
                    self.snap[name] = (t, opt["snap"], self.attach[name][1])
                    self.attach[name] = (arg, self.grips[name].inverted())
                self.settle.pop(name, None)
                self.from_path.pop(name, None)
            elif kind == "release" and arg and "path" in arg:
                self.attach.pop(name, None)
                self.from_path[name] = (t, self.propM[name].copy(), arg["path"])
            elif kind == "release" and arg and "place" in arg:
                self.attach.pop(name, None)
                self.settle[name] = (t, self.propM[name].copy(), pose_M(arg["place"]), arg.get("dur", 0.12))
            elif kind == "release":
                self.attach.pop(name, None)
                M0 = self.propM[name].copy()
                loc = M0.translation.copy()
                if arg and "z" in arg:
                    loc.z = arg["z"]
                fwd = M0.to_3x3() @ Vector((0, 1, 0))
                yaw = math.degrees(math.atan2(-fwd.x, fwd.y))
                self.settle[name] = (t, M0, place(loc, yaw), 0.12)
            self.ev_i += 1
        for name in self.propM:
            if name in self.attach:
                key, off = self.attach[name]
                if name in self.snap:
                    t0, sd, off0 = self.snap[name]
                    off = blend_M(off0, off, ease((t - t0) / sd))
                self.propM[name] = self.parent_M(key) @ off
            elif name in self.settle:
                t0, M0, M1, sd = self.settle[name]
                self.propM[name] = blend_M(M0, M1, ease((t - t0) / sd))
            elif name in self.from_path:
                t0, M0, sd = self.from_path[name]
                e = ease((t - t0) / sd)
                self.propM[name] = blend_M(M0, self.path_M(name, t), e)
                if e >= 1:
                    del self.from_path[name]
            out[self.S["props"][name]] = self.propM[name]

        # register screen state (inactive screens scaled to zero)
        state = channel(A["props_pose"].get("screen", []), t, "idle")
        for name, ob in self.S["screens"].items():
            M = self.S["register_M"] @ Tr(0, 0, 0.2) @ Matrix.Rotation(math.radians(30), 4, "X") @ Tr(0, 0.0102, 0)
            if name != (state if isinstance(state, str) else "idle"):
                M = M @ Matrix.Diagonal((0, 0, 0, 1))
            out[ob] = M

        # lights + UV
        L = {k: channel(v, t, 1.0) for k, v in A.get("lights", {}).items()}
        uv = channel(A.get("uv", []), t, 0.0)
        lamp = self.propM["uvlamp"]
        beam_o = lamp @ Vector((0, 0, 0.085))
        beam_d = (lamp.to_3x3() @ Vector((0, 0, -1))).normalized()
        spotM = lamp @ Tr(0, 0, 0.08)
        out[self.S["lights"]["uv_spot"]] = spotM
        vals = dict(lights=L, uv=uv, beam_o=tuple(beam_o), beam_d=tuple(beam_d))

        if self.S.get("ripples"):
            vals["ripple_alpha"] = self.ripples(t, out)
        hd = self.B["patrick"]["head"]
        vals["track"] = {"bill": tuple(hd @ Vector((0, 0.36, -0.05))), "eye": tuple(hd @ Vector((0.088, 0.135, 0.04))),
                         "head": tuple(hd.translation)}
        for name in self.paths:
            vals["track"][name] = tuple(self.propM[name].translation)
        cam = self.camera(t)
        return out, vals, cam

    def path_M(self, name, t):
        """Swim path (world keys) plus a gentle idle: small yaw sway and bob, different per animal."""
        k = channel(self.paths[name], t, None)
        ph = (sum(map(ord, name)) % 17) * 0.37
        M = pose_M(k)
        return M @ Matrix.Rotation(math.radians(4 * math.sin(2.3 * t + ph)), 4, "Z") @ Matrix.Translation((0, 0, 0.0015 * math.sin(1.7 * t + ph)))

    def ripple_src(self, emitter):
        if emitter == "head":
            return self.B["patrick"]["head"].translation
        if emitter == "bill":
            return self.B["patrick"]["head"] @ Vector((0, 0.2, -0.05))
        if isinstance(emitter, str) and emitter.startswith("prop:"):
            return self.propM[emitter[5:]].translation
        return Vector((emitter[0], emitter[1], 0))

    def ripples(self, t, out):
        """Expanding rings on the water surface; a pool of objects is reused round-robin."""
        tk = self.S["tank"]
        pool = self.S["ripples"]
        life = 1.7
        w, d, _ = tk["size"]
        cx, cy = tk["center"]
        for ob in pool:
            out[ob] = Matrix.Diagonal((0, 0, 0, 1))
        alphas = [0.0] * len(pool)
        for i, e in enumerate(self.rip_ev):
            if e[0] > t + 1e-6:
                break
            if e[3] is None:
                p = self.ripple_src(e[1])
                e[3] = (min(cx + w / 2 - 0.03, max(cx - w / 2 + 0.03, p.x)), min(cy + d / 2 - 0.03, max(cy - d / 2 + 0.03, p.y)))
            x = (t - e[0]) / life
            if x >= 1:
                continue
            r = 0.012 + 0.13 * (1 - (1 - x) ** 2)
            k = i % len(pool)
            out[pool[k]] = Matrix.Translation((e[3][0], e[3][1], tk["top"] + 0.0015)) @ Matrix.Diagonal((r, r, 1, 1))
            alphas[k] = 0.5 * e[2] * (1 - x) ** 1.5
        return alphas

    def parent_M(self, key):
        if key == "fridge_door":
            return self.door_M(self.door_angle)
        if key.startswith("prop:"):
            return self.propM[key[5:]]
        who, part = key.split(".")
        return self.B[who][f"hand_{part}" if part in ("L", "R") else part]

    def focus_point(self, name):
        if isinstance(name, list):
            return Vector(name)
        if name == "patrick_head":
            return self.B["patrick"]["head"] @ Vector((0, 0.12, 0.03))
        if name == "bear_head":
            return self.B["bear"]["head"] @ Vector((0, 0.2, 0.05))
        if name == "register_screen":
            return self.S["register_M"] @ Vector((0, 0.01, 0.2))
        if name.startswith("prop:"):
            return self.propM[name[5:]].translation + Vector((0, 0, 0.07))
        return Vector((0, 0, 1.5))

    def camera(self, t):
        shots = self.tl["shots"]
        i = max(k for k, s in enumerate(shots) if s[0] <= t + 1e-6)
        s = shots[i]
        t0 = s[0]
        t1 = shots[i + 1][0] if i + 1 < len(shots) else self.tl["duration"]
        preset = dict(self.cfg["cameras"][s[1]])
        opt = s[2] if len(s) > 2 else {}
        preset.update({k: v for k, v in opt.items() if k in ("pos", "look", "lens", "focus", "fstop")})
        pos, look = Vector(preset["pos"]), Vector(preset["look"])
        if "offset" in opt:
            pos += Vector(opt["offset"])
            look += Vector(opt["offset"])
        x = (t - t0) / max(1e-3, t1 - t0)
        push = opt.get("push", 0.025)
        pos = pos.lerp(look, push * x)
        if "drift" in opt:
            pos += Vector(opt["drift"]) * x
        q = (look - pos).to_track_quat("-Z", "Y")
        M = q.to_matrix().to_4x4()
        M.translation = pos
        fp = self.focus_point(preset.get("focus", [0, 0, 1.5]))
        dist = max(0.1, (fp - pos).dot(q @ Vector((0, 0, -1))))
        return dict(M=M, lens=preset["lens"], focus=dist, fstop=preset.get("fstop", 2.8), shot=s[1])
