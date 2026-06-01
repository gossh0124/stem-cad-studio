"""驗證 load_thermal_index() 在檔不存在時會 build + write。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pathlib import Path
from lib.thermal_index import load_thermal_index, THERMAL_INDEX_PATH


def main() -> int:
    if THERMAL_INDEX_PATH.exists():
        THERMAL_INDEX_PATH.unlink()
        print(f'刪除舊檔：{THERMAL_INDEX_PATH}')
    assert not THERMAL_INDEX_PATH.exists()
    idx = load_thermal_index()
    print(f'load_thermal_index 返回 {len(idx)} 個 entry')
    assert THERMAL_INDEX_PATH.exists(), '應該自動寫入但檔仍不存在'
    print(f'✅ 自動寫入確認：{THERMAL_INDEX_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
