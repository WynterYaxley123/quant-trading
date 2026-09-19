"""Hikyuu provider —— 从 Hikyuu ``StockManager`` 取行情并归一化。

数据来源：Hikyuu 的 HDF5 / SQLite 数据目录（由
``scripts/data/init_hikyuu_data.py`` 通过 pytdx 导入，见
``docs/data/hikyuu_data_capabilities.md``）。

本模块**只做读取与转换**，不做下载、不做回测。
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Mapping, Sequence

import pandas as pd

from ..schema import DataIntegrityError, normalize_frame, validate_frame
from .base import DataProvider, ProviderCapabilities, ProviderUnavailable

__all__ = ["HikyuuProvider", "kdata_to_frame"]


def _to_hikyuu_datetime(d: object):
    """把 date/str/int 转成 ``hikyuu.Datetime``（YYYYMMDD0000 形式）。"""
    import hikyuu

    if isinstance(d, datetime):
        dd = d.date()
    elif isinstance(d, date):
        dd = d
    elif isinstance(d, str):
        dd = datetime.strptime(d.replace("-", "")[:8], "%Y%m%d").date()
    elif isinstance(d, int):
        dd = datetime.strptime(str(d)[:8], "%Y%m%d").date()
    else:
        dd = date(int(d.year), int(d.month), int(d.day))  # type: ignore[attr-defined]
    return hikyuu.Datetime(int(dd.strftime("%Y%m%d")))


def kdata_to_frame(kdata, symbol: str, **extra) -> pd.DataFrame:
    """把 Hikyuu ``KData`` 转成 canonical frame。

    实测字段（Hikyuu 2.8.2）：``datetime`` / ``open`` / ``high`` / ``low`` /
    ``close`` / ``volume`` / ``amount``。

    注意：KData 迭代返回的 ``open`` 等已是**元单位价格**（Hikyuu 内部以
    0.001 元存储，暴露给 Python 时已换算）。此处不做二次缩放。
    """
    rows = []
    for i in range(len(kdata)):
        r = kdata[i]
        d = r.datetime
        rows.append(
            {
                "date": date(int(d.year), int(d.month), int(d.day)),
                "symbol": symbol,
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": float(r.volume),
                "amount": float(r.amount),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["date", "symbol", "open", "high", "low", "close", "volume", "amount"])
    df = normalize_frame(pd.DataFrame(rows), symbol=symbol, **extra)
    return df


class HikyuuProvider(DataProvider):
    """从已加载的 Hikyuu ``StockManager`` 读日线。"""

    name = "hikyuu"

    def __init__(self, *, auto_load: bool = True, config_file: str | None = None):
        """
        :param auto_load: 若 StockManager 为空，是否自动 ``load_hikyuu``。
        :param config_file: 传给 ``load_hikyuu`` 的配置路径；None 用默认
            ``~/.hikyuu/hikyuu.ini``。
        """
        self._auto_load = auto_load
        self._config_file = config_file

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            asset_types=frozenset({"ETF", "STOCK", "INDEX"}),
            ktypes=frozenset({"DAY"}),
            provides_adjust_factor=False,
            is_pit=True,
            history_start=1990,
        )

    def is_available(self) -> bool:
        """探测 Hikyuu 是否可用（包 + 数据已加载）。探测过程不抛异常。"""
        try:
            import hikyuu  # noqa: F401
        except ImportError:
            return False
        try:
            sm = self._get_sm()
            return len(sm) > 0
        except Exception:
            return False

    # -- 内部 ---------------------------------------------------------------

    def _get_sm(self):
        import hikyuu

        sm = hikyuu.StockManager.instance()
        if len(sm) == 0 and self._auto_load:
            # 关键护栏：reload 之前必须做结构一致性检查，
            # 否则 stock.db 与 HDF5 不一致会导致段错误（实测 exit 139）。
            from . import hikyuu_preflight

            dest = self._resolve_datadir()
            if dest is not None:
                hikyuu_preflight.preflight(dest)  # 不一致时抛 HikyuuDataIntegrityError
            if self._config_file:
                hikyuu.load_hikyuu(config_file=self._config_file)
            else:
                hikyuu.load_hikyuu()
            sm = hikyuu.StockManager.instance()
        return sm

    def _resolve_datadir(self) -> str | None:
        """从 hikyuu.ini 读取 datadir，用于 preflight。读不到返回 None。"""
        import configparser

        cfg = self._config_file or os.path.join(
            os.path.expanduser("~"), ".hikyuu", "hikyuu.ini"
        )
        if not os.path.exists(cfg):
            return None
        try:
            p = configparser.ConfigParser()
            p.read(cfg, encoding="utf-8")
            return p.get("hikyuu", "datadir", fallback=None)
        except Exception:  # noqa: BLE001 - 配置损坏交由 load_hikyuu 报错
            return None

    def _resolve(self, symbol: str):
        """把 ``510300`` / ``sh510300`` / ``SH510300`` 解析成 Stock 对象。

        实测（Hikyuu 2.8.2）：``sm['510300']``（裸代码）返回一个**空 Stock**
        且不抛异常（``valid=False``）；必须带市场前缀（``sh510300``）才能取到。
        因此裸 6 位代码要显式补 ``sh``/``sz`` 前缀试探。

        找不到时抛 ``ProviderUnavailable``（而不是返回 None 让调用方猜）。
        """
        sm = self._get_sm()
        s = symbol.strip()
        # 候选顺序：原样 → 带 sh/sz 前缀（裸 6 位代码必须补前缀）
        cands: list[str] = [s]
        low = s.lower()
        bare = low[2:] if low[:2] in ("sh", "sz", "bj") else low
        if len(bare) == 6 and bare.isdigit():
            cands.extend([f"sh{bare}", f"sz{bare}", f"bj{bare}"])
        else:
            cands.extend([low, s.upper()])

        seen: set[str] = set()
        for cand in cands:
            if cand in seen:
                continue
            seen.add(cand)
            try:
                stk = sm[cand]
            except Exception:
                continue
            if stk is not None and getattr(stk, "valid", False):
                return stk
        raise ProviderUnavailable(
            self.name, f"symbol {symbol!r} 未在 StockManager 中找到或已失效"
        )

    # -- 取数 ---------------------------------------------------------------

    def fetch_daily(
        self,
        symbols: Sequence[str],
        start: object,
        end: object,
    ) -> Mapping[str, pd.DataFrame]:
        import hikyuu

        try:
            sm = self._get_sm()
        except Exception as e:  # pragma: no cover - 环境问题
            raise ProviderUnavailable(self.name, f"StockManager 加载失败: {e}") from e

        if len(sm) == 0:
            raise ProviderUnavailable(
                self.name,
                "StockManager 为空，行情数据尚未初始化（见 scripts/data/init_hikyuu_data.py）",
            )

        q = hikyuu.Query(_to_hikyuu_datetime(start), _to_hikyuu_datetime(end))
        out: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            stk = self._resolve(sym)
            kd = stk.get_kdata(q)
            if len(kd) == 0:
                continue  # 无数据不伪造
            df = kdata_to_frame(kd, symbol=sym)
            validate_frame(df)
            out[sym] = df
        return out

    def asset_type_of(self, symbol: str) -> str:
        """返回证券类型字符串（``ETF`` / ``STOCK`` / ``INDEX`` …）。"""
        stk = self._resolve(symbol)
        return str(stk.type)

    def list_symbols(self) -> list[str]:
        """列出 StockManager 中全部有效证券的 ``market+code``。"""
        sm = self._get_sm()
        out: list[str] = []
        for s in sm:
            try:
                if getattr(s, "valid", False):
                    out.append(str(s.market).lower() + str(s.code))
            except Exception:
                continue
        return out
