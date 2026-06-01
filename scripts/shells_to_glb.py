"""scripts/shells_to_glb.py — 把 shells/{type}/ 的 STL 補成 GLB（assembly 載入加速）。

用法：
  .venv/Scripts/python.exe scripts/shells_to_glb.py                 # 全部 type
  .venv/Scripts/python.exe scripts/shells_to_glb.py --types A B C   # 指定 type
  .venv/Scripts/python.exe scripts/shells_to_glb.py --overwrite     # 重轉（pcb_body 多色仍保護）

對齊 D7 修正案：逐模組 GLB + 前端載一次快取，保留 assembly 互動。
shells/ 為 live 與範本共用倉，補 GLB 後兩者自動一致（D8）。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from lib.cad.glb_convert import ensure_shell_glbs

_SHELLS_DIR = os.path.join(os.path.dirname(__file__), "..", "shells")


def main() -> int:
    ap = argparse.ArgumentParser(description="shells STL→GLB 後處理")
    ap.add_argument("--types", nargs="*", default=None,
                    help="指定 component type（資料夾名）；省略=全部")
    ap.add_argument("--overwrite", action="store_true",
                    help="重轉既有 GLB（pcb_body 多色版仍保護不覆蓋）")
    args = ap.parse_args()

    result = ensure_shell_glbs(_SHELLS_DIR, types=args.types, overwrite=args.overwrite)
    print(f"[OK] converted {len(result['converted'])}, skipped {len(result['skipped'])}")
    for c in result["converted"]:
        print(f"  + {c}")
    if args.types:
        for s in result["skipped"]:
            print(f"  · skip {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
