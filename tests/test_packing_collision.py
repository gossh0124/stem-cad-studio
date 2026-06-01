"""test_packing_collision.py — packing 收斂式碰撞修復（VS-3D-Z 生成側）。"""
from lib.assembly_solver._types import _Comp
from lib.assembly_solver.packing import _check_collisions


def _comp(t: str, x: float, y: float, L: float, W: float,
          z: float = 0.0, H: float = 10.0) -> _Comp:
    return _Comp(type=t, role="Sensor", L=L, W=W, H=H,
                 weight_g=5.0, thermal_mw=0.0, ports=[], x=x, y=y, z=z)


def _has_overlap(comps) -> bool:
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            a, b = comps[i], comps[j]
            ox = min(a.x + a.L, b.x + b.L) - max(a.x, b.x)
            oy = min(a.y + a.W, b.y + b.W) - max(a.y, b.y)
            oz = min(a.z + a.H, b.z + b.H) - max(a.z, b.z)
            if ox > 0 and oy > 0 and oz > 0:
                return True
    return False


class TestPackingConvergence:
    def test_no_initial_collision(self):
        comps = [_comp("A", 0, 0, 10, 10), _comp("B", 20, 20, 10, 10)]
        dec = []
        _check_collisions(comps, dec, 100, 100)
        assert not _has_overlap(comps)
        assert any("無碰撞" in d.description for d in dec)

    def test_overlap_resolved_when_space_available(self):
        # 兩元件重疊，殼夠大 → 收斂式推移應完全消除
        comps = [_comp("A", 0, 0, 20, 20), _comp("B", 5, 5, 20, 20)]
        dec = []
        _check_collisions(comps, dec, 200, 200)
        assert not _has_overlap(comps), "收斂後仍有重疊"
        assert any("消除" in d.description for d in dec)

    def test_three_way_pileup_resolved(self):
        # 三元件互疊，舊版單次 pass 推 B 可能撞 C；收斂式應全消
        comps = [_comp("A", 0, 0, 15, 15), _comp("B", 5, 5, 15, 15),
                 _comp("C", 10, 10, 15, 15)]
        dec = []
        _check_collisions(comps, dec, 300, 300)
        assert not _has_overlap(comps)

    def test_residual_reported_when_no_space(self):
        # 4 個 50x50x50 元件塞進 60x60x60 殼 → x/y/z 均不足，誠實回報殘留（不假裝修好）
        comps = [_comp(f"C{i}", 0, 0, 50, 50, z=0.0, H=50.0) for i in range(4)]
        dec = []
        _check_collisions(comps, dec, 60, 60, inner_h=60.0)
        assert any("殘留" in d.description for d in dec), \
            "空間不足時應回報殘留碰撞，而非假裝成功"

    def test_clamp_keeps_in_bounds(self):
        # 推移後不應超出 inner 邊界
        comps = [_comp("A", 0, 0, 30, 30), _comp("B", 2, 2, 30, 30)]
        dec = []
        inner_l, inner_w = 100, 100
        _check_collisions(comps, dec, inner_l, inner_w)
        for c in comps:
            assert c.x >= 0 and c.x + c.L <= inner_l + 0.01
            assert c.y >= 0 and c.y + c.W <= inner_w + 0.01

    def test_z_overlap_detected(self):
        # 同 x/y 位置、z 方向重疊 → 應偵測到碰撞並修復
        comps = [
            _comp("A", 0, 0, 10, 10, z=0.0, H=15.0),
            _comp("B", 0, 0, 10, 10, z=10.0, H=15.0),
        ]
        dec = []
        _check_collisions(comps, dec, 100, 100, inner_h=100.0)
        assert not _has_overlap(comps), "z 重疊應被推移修復"
        assert any("消除" in d.description for d in dec), "應偵測到碰撞並成功消除"

    def test_z_no_overlap_stacked(self):
        # 相同 x/y 但 z 方向完全分離（堆疊）→ 不應視為碰撞
        comps = [
            _comp("A", 0, 0, 10, 10, z=0.0, H=10.0),
            _comp("B", 0, 0, 10, 10, z=10.0, H=10.0),
        ]
        dec = []
        _check_collisions(comps, dec, 100, 100, inner_h=100.0)
        assert not _has_overlap(comps)
        assert any("無碰撞" in d.description for d in dec)

    def test_3d_shift_resolves_z_collision(self):
        # 三軸均重疊，z 重疊最小 → 應優先沿 z 推移並消除碰撞
        comps = [
            _comp("A", 0, 0, 20, 20, z=0.0, H=10.0),
            _comp("B", 5, 5, 20, 20, z=8.0, H=10.0),
        ]
        dec = []
        _check_collisions(comps, dec, 200, 200, inner_h=200.0)
        assert not _has_overlap(comps), "3D 碰撞應收斂消除"

    def test_z_clamp_keeps_in_bounds(self):
        # z 推移後 comp.z + comp.H 不應超出 inner_h
        comps = [
            _comp("A", 0, 0, 10, 10, z=0.0, H=30.0),
            _comp("B", 0, 0, 10, 10, z=5.0, H=30.0),
        ]
        dec = []
        inner_h = 60.0
        _check_collisions(comps, dec, 200, 200, inner_h=inner_h)
        for c in comps:
            assert c.z >= 0.0, f"z 不可為負：{c.z}"
            assert c.z + c.H <= inner_h + 0.01, f"超出 inner_h：z={c.z}, H={c.H}"

    def test_inner_h_none_no_z_clamp(self):
        # H5: inner_h=None 時不 clamp z（對齊 inner_l/w None 模式）
        # 兩元件 z 重疊，inner_h=None → 推移不受 inner_h 限制，仍消除碰撞
        comps = [
            _comp("A", 0, 0, 10, 10, z=0.0, H=20.0),
            _comp("B", 0, 0, 10, 10, z=15.0, H=20.0),
        ]
        dec = []
        _check_collisions(comps, dec, 200, 200, inner_h=None)
        assert not _has_overlap(comps), "inner_h=None 時 z 碰撞仍應消除"
