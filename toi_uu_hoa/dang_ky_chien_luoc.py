"""
toi_uu_hoa_low/dang_ky_chien_luoc.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Registry + AUTOLOAD chiến lược plugin (M1 Strategy Plugin Interface).

Tự động quét `chien_luoc/user_strategies/`, nạp mọi lớp kế thừa
`ChienLuocPluginCoSo` bằng `importlib` → đăng ký vào STRATEGY_REGISTRY để
dashboard liệt kê và bộ tối ưu  chạy được, KHÔNG cần sửa module lõi.

Thêm chiến lược mới = thả 1 file .py vào chien_luoc/user_strategies/ rồi
gọi lại `nap_plugins()` (hoặc khởi động lại tiến trình).
"""

import os
import sys
import inspect
import importlib
import pkgutil

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from chien_luoc.base_strategy import ChienLuocPluginCoSo
import chien_luoc.user_strategies as _pkg_user_strategies


STRATEGY_REGISTRY = {}


def nap_plugins(im_lang=True):
    """Quét lại thư mục user_strategies và nạp toàn bộ plugin vào STRATEGY_REGISTRY."""
    STRATEGY_REGISTRY.clear()
    for modinfo in pkgutil.iter_modules(_pkg_user_strategies.__path__):
        if modinfo.name.startswith('_'):
            continue
        mod_name = f"chien_luoc.user_strategies.{modinfo.name}"
        try:

            if mod_name in sys.modules:
                mod = importlib.reload(sys.modules[mod_name])
            else:
                mod = importlib.import_module(mod_name)
        except Exception as e:
            if not im_lang:
                print(f"[WARN] Bỏ qua plugin lỗi '{modinfo.name}': {e}")
            continue

        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, ChienLuocPluginCoSo)
                and obj is not ChienLuocPluginCoSo
                and not inspect.isabstract(obj)
                and obj.__module__ == mod_name
            ):
                try:
                    STRATEGY_REGISTRY[obj.khoa()] = obj
                except Exception as e:
                    if not im_lang:
                        print(f"[WARN] Không đăng ký được '{_name}': {e}")
    return STRATEGY_REGISTRY


def danh_sach_plugins():
    """Trả list metadata plugin cho dashboard: [{khoa, ten, mo_ta, nhom}]."""
    out = []
    for khoa, cls in STRATEGY_REGISTRY.items():
        out.append({
            'khoa': khoa,
            'ten': getattr(cls, 'ten', '') or cls.__name__,
            'mo_ta': getattr(cls, 'mo_ta', '') or '',
            'nhom': getattr(cls, 'nhom', '') or 'Chiến lược plugin',
        })
    out.sort(key=lambda x: x['ten'])
    return out


def lay_plugin(khoa):
    """Trả lớp plugin theo khóa (hoặc None)."""
    return STRATEGY_REGISTRY.get(khoa)



nap_plugins()
