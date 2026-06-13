# Axis-B 交叉驗證(scripts/crosscheck/)

獨立第二軸,對 in-repo 驗證(Axis-A)做交叉確認 —— DEC-H3(雙軸 A+B 收口)+ DEC-H6(harness 簽入 repo)。

## 設計

| 軸 | 執行環境 | 角色 |
|----|----------|------|
| **Axis-A** | 系統 Python(3.14)+ repo | `lib.wiring.build_netlist` → galvanic isolation 判定 + 兩地 node-set + 輸入 hash |
| **Axis-B** | **venv313**(防火牆外,SKiDL) | 由設計意圖**獨立重建**電路 + 原生 ERC + 隔離 set 代數 |

**收口判準**:兩軸對同一 demo 同意(`agree` 隔離判定一致 + `node_sets_equal` 兩地 node-set 相等)
且 Axis-B 對綁地 mutant 會抓到(`mutant.axis_b_caught`)。

## 防火牆(DEC-H4)

- `axis_b_isolation.py` **import skidl** → 僅可用 venv313 執行,**絕不**進 `lib/`。
- in-repo gate `tests/test_crosscheck_results.py` **不** import skidl,只讀 `crosscheck-results.json`
  + 重算 Axis-A hash 驗 freshness;並斷言 `lib/` 無 skidl/kicad/pyspice 的 **import 級**引用。

## 執行

```powershell
# 需 venv313(見 ~/.claude/skills/circuit-design-verify/scripts/env.md 的 bootstrap)
python scripts/crosscheck/run.py
# → 寫 scripts/crosscheck/crosscheck-results.json(witness,已提交)
# → pytest tests/test_crosscheck_results.py 驗 agree + node-set + mutant + freshness
```

venv313 路徑可用環境變數 `CDV_VENV313` 覆寫;預設
`~/.claude/skills/circuit-design-verify/.venv313/Scripts/python.exe`。
無 venv313 → 僅寫 Axis-A 部分(`axis_b=null`),in-repo 測試 skip。

## 產出

- `crosscheck-results.json` — 驗證 witness(**提交**;`input_hash` 防 stale)。
- `_artifacts/axis_a.json` — 中間檔(**gitignore**)。

## CI 分層(DEC-T2)

lean CI 無 SKiDL → in-repo 測試 skip;Axis-B 重跑走 scheduled / 手動 dispatch。
若 netlist 變動但未重跑,freshness hash 不符 → 測試 FAIL,提示重跑(防 stale 矇混)。
