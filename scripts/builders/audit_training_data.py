"""訓練資料適配性審計：交叉比對生成器產出 vs REGISTRY SSOT vs pipeline 實際需求。"""
import sys, json, pathlib
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent / "training"))

from collections import Counter, defaultdict

# ── 1. 從 REGISTRY 取 SSOT ──────────────────────────────────
from lib.registry import COMPONENT_REGISTRY
registry_types = set(COMPONENT_REGISTRY.keys())
print(f"REGISTRY 元件總數: {len(registry_types)}")

# ── 2. 從 training/config.py 取 TAXONOMY ────────────────────
from config import TAXONOMY_CONFIG
taxonomy_types = TAXONOMY_CONFIG["all_valid_types"]
print(f"TAXONOMY 元件總數: {len(taxonomy_types)}")

# ── 3. 比對 REGISTRY vs TAXONOMY ────────────────────────────
in_reg_not_tax = registry_types - taxonomy_types
in_tax_not_reg = taxonomy_types - registry_types
print(f"\n=== REGISTRY vs TAXONOMY 差異 ===")
if in_reg_not_tax:
    print(f"  REGISTRY 有但 TAXONOMY 沒有 ({len(in_reg_not_tax)}):")
    for t in sorted(in_reg_not_tax):
        print(f"    - {t}")
if in_tax_not_reg:
    print(f"  TAXONOMY 有但 REGISTRY 沒有 ({len(in_tax_not_reg)}):")
    for t in sorted(in_tax_not_reg):
        print(f"    - {t}")
if not in_reg_not_tax and not in_tax_not_reg:
    print("  [OK] perfectly aligned")

# ── 4. LoRA-A 生成器覆蓋率 ──────────────────────────────────
from data_generator import DataGenerator, _CATEGORY_AUX_POOL, EDUCATIONAL_RATIONALE

print(f"\n=== LoRA-A 生成器覆蓋率 ===")
# 檢查 AUX_POOL 涵蓋的元件
aux_pool_types = set()
for cat, pools in _CATEGORY_AUX_POOL.items():
    for role, types in pools:
        aux_pool_types.update(types)

# Brain/Power/Control 從 TAXONOMY 取
core_types = set()
for role in ("Brain", "Power", "Control"):
    core_types.update(TAXONOMY_CONFIG["component_taxonomy"][role])

gen_a_types = aux_pool_types | core_types
missing_in_gen_a = taxonomy_types - gen_a_types
print(f"  AUX_POOL 涵蓋: {len(aux_pool_types)} 種")
print(f"  Core 涵蓋: {len(core_types)} 種")
print(f"  總涵蓋: {len(gen_a_types)} / {len(taxonomy_types)}")
if missing_in_gen_a:
    print(f"  缺失 ({len(missing_in_gen_a)}):")
    for t in sorted(missing_in_gen_a):
        print(f"    - {t}")

# 檢查 EDUCATIONAL_RATIONALE 覆蓋
missing_edu = taxonomy_types - set(EDUCATIONAL_RATIONALE.keys())
if missing_edu:
    print(f"  EDUCATIONAL_RATIONALE 缺失 ({len(missing_edu)}):")
    for t in sorted(missing_edu):
        print(f"    - {t}")

# ── 5. LoRA-B 生成器覆蓋率 ──────────────────────────────────
from data_generator_b import (
    WEIGHT_G, THERMAL_MW, CURRENT_MA,
    CATEGORY_TEMPLATES, DataGeneratorB,
)

print(f"\n=== LoRA-B 生成器覆蓋率 ===")

# Templates 涵蓋的元件
template_types = set()
for cat, tmpls in CATEGORY_TEMPLATES.items():
    for t in tmpls:
        template_types.add(t["brain"])
        template_types.add(t["power"])
        template_types.add(t["control"])
        template_types.update(t["aux"])
print(f"  Templates 涵蓋: {len(template_types)} 種")
missing_template = taxonomy_types - template_types
if missing_template:
    print(f"  Templates 未出現 ({len(missing_template)}):")
    for t in sorted(missing_template):
        print(f"    - {t}")

# WEIGHT_G 覆蓋
missing_weight = taxonomy_types - set(WEIGHT_G.keys())
if missing_weight:
    print(f"  WEIGHT_G 缺失 ({len(missing_weight)}):")
    for t in sorted(missing_weight):
        print(f"    - {t}")

# CURRENT_MA 覆蓋
missing_current = taxonomy_types - set(CURRENT_MA.keys())
if missing_current:
    print(f"  CURRENT_MA 缺失 ({len(missing_current)}):")
    for t in sorted(missing_current):
        print(f"    - {t}")

# ── 6. REGISTRY 數值 vs 訓練數值比對 ────────────────────────
print(f"\n=== REGISTRY vs 訓練資料數值比對 ===")
discrepancies = []
for ctype in sorted(taxonomy_types):
    if ctype not in COMPONENT_REGISTRY:
        continue
    spec = COMPONENT_REGISTRY[ctype]

    # current_ma（跳過 Power 角色：REGISTRY 記錄供電能力，訓練資料記錄消耗=0）
    _power_types = set(TAXONOMY_CONFIG["component_taxonomy"].get("Power", []))
    reg_ma = spec.current_ma
    gen_b_ma = CURRENT_MA.get(ctype)
    if ctype not in _power_types:
        if gen_b_ma is not None and abs(reg_ma - gen_b_ma) > max(reg_ma * 0.3, 5):
            discrepancies.append(f"  {ctype} current_ma: REG={reg_ma} vs GenB={gen_b_ma} (差異 > 30%)")

    # weight_g
    reg_w = spec.weight_g
    gen_b_w = WEIGHT_G.get(ctype)
    if gen_b_w is not None and abs(reg_w - gen_b_w) > max(reg_w * 0.3, 2):
        discrepancies.append(f"  {ctype} weight_g: REG={reg_w} vs GenB={gen_b_w} (差異 > 30%)")

    # thermal_mw
    reg_t = spec.thermal_mw
    gen_b_t = THERMAL_MW.get(ctype)
    if gen_b_t is not None and reg_t > 0 and abs(reg_t - gen_b_t) > max(reg_t * 0.3, 50):
        discrepancies.append(f"  {ctype} thermal_mw: REG={reg_t} vs GenB={gen_b_t} (差異 > 30%)")

if discrepancies:
    print(f"  發現 {len(discrepancies)} 筆差異（>30% 或 >5mA/2g/50mW）:")
    for d in discrepancies:
        print(d)
else:
    print("  所有數值在 30% 容差內 [OK]")

# ── 7. 實際生成樣本品質檢查 ─────────────────────────────────
print(f"\n=== 實際生成樣本品質 ===")
gen = DataGenerator()
import random
random.seed(42)
samples_a = [gen._build_sample(i) for i in range(100)]

# 驗證 JSON 可解析
parse_ok = 0
parse_fail = 0
for s in samples_a:
    comp_text = s["completion"].replace("<|eot_id|>", "")
    try:
        obj = json.loads(comp_text)
        parse_ok += 1
        # 驗證必要欄位
        assert "project_name" in obj
        assert "project_category" in obj
        assert "cot_plan" in obj
        assert "components" in obj
        assert "inventory_mentions" in obj
        assert obj["inventory_mentions"] == []
        roles = {c["role"] for c in obj["components"]}
        assert "Brain" in roles
        assert "Power" in roles
        assert "Control" in roles
    except Exception as e:
        parse_fail += 1
        if parse_fail <= 3:
            print(f"  Parse 失敗: {e}")

print(f"  LoRA-A: {parse_ok}/100 JSON 可解析且結構正確")

# Category 分佈
cat_dist = Counter(s["category"] for s in samples_a)
print(f"  Category 分佈: {dict(cat_dist)}")

# RAG context 注入率
rag_count = sum(1 for s in samples_a if "[參考案例]" in s["prompt"])
print(f"  RAG context 注入率: {rag_count}% (目標 ~25%)")

# LoRA-B (messages format)
random.seed(42)
gen_b = DataGeneratorB()
samples_b = gen_b.generate_synthetic_data(n=50)
parse_ok_b = 0
for s in samples_b:
    msgs = s.get("messages", [])
    if not msgs:
        continue
    assistant_text = msgs[-1].get("content", "") if msgs[-1].get("role") == "assistant" else ""
    try:
        obj = json.loads(assistant_text)
        parse_ok_b += 1
    except Exception:
        pass

print(f"  LoRA-B: {parse_ok_b}/{len(samples_b)} JSON 可解析")

# LoRA-B category 分佈
cat_dist_b = Counter(s.get("_meta", {}).get("category", "?") for s in samples_b)
print(f"  LoRA-B Category 分佈: {dict(cat_dist_b)}")

print(f"\n{'='*60}")
print("審計完成")
