"""lib/verification — Verification Spine（產出物驗證脊柱）。

把正確性判定從「肉眼看截圖」搬到「可計算的契約 + verdict gate」。

層級：
  L0  產出完整性     l0_integrity.py（已實作）
  L1  結構/語義正確   （Phase 2/3）
  L2  排版/視覺品質   （Phase 3）
  L3  黃金回歸        （Phase 4）

用法：
    from lib.verification import check_mesh, gate
    import sys
    rpt = check_mesh("output/foo.stl")
    sys.exit(gate(rpt))
"""
from .report import (
    Verdict,
    CheckResult,
    VerificationReport,
    gate,
    BLOCKING_LAYERS,
)
from .l0_integrity import check_svg, check_png, check_mesh
from .contract import check_cad_output_contract, check_model_registry, check_scene_graph_meshes
from .l1_geometry import check_placement_collisions
from .l1_netlist import check_netlist, check_wiring_netlist
from .pcb_layout import audit_pcb_layout
from .l2_layout import audit_schematic_layout, check_schematic_svg
from .l3_golden import extract_metrics, compare_golden, save_baseline, load_baseline

__all__ = [
    "Verdict",
    "CheckResult",
    "VerificationReport",
    "gate",
    "BLOCKING_LAYERS",
    "check_svg",
    "check_png",
    "check_mesh",
    "check_cad_output_contract",
    "check_model_registry",
    "check_scene_graph_meshes",
    "check_placement_collisions",
    "check_netlist",
    "check_wiring_netlist",
    "audit_pcb_layout",
    "audit_schematic_layout",
    "check_schematic_svg",
    "extract_metrics",
    "compare_golden",
    "save_baseline",
    "load_baseline",
]
