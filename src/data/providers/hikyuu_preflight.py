"""Hikyuu 数据完整性 Preflight —— 在 ``StockManager.reload()`` 之前检查。

为什么需要
----------
实测（Hikyuu 2.8.2，Linux x64，本次开发过程）：当 ``stock.db`` 中的证券
记录与 HDF5 中实际存在的 K线表**不一致**时，``StockManager.reload()``
不抛 Python 异常，而是**直接段错误**（SIGSEGV，进程 exit 139），
无法被 ``try/except`` 捕获。

因此必须在 reload 之前做结构一致性检查；发现不一致立即抛
:class:`HikyuuDataIntegrityError`（普通 Python 异常），停止流程。

检查项（对应任务书第三节）
-------------------------
1. ``stock.db`` 是否存在
2. HDF5 文件是否存在
3. 必要 market 数据是否存在（Market 表至少含 SH/SZ）
4. ``stock.db`` 中待加载证券是否有对应 HDF5 K线表（**核心**）
5. ``Market.lastDate`` 是否为合法实际日期
6. ``valid=1`` 证券的 ``endDate=99999999`` 是否污染了 ``lastDate``
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date

__all__ = [
    "HikyuuDataIntegrityError",
    "PreflightReport",
    "preflight",
]


class HikyuuDataIntegrityError(RuntimeError):
    """Hikyuu 数据目录结构不一致 —— 若继续 reload 会导致段错误。

    继承 ``RuntimeError`` 而非 ``ValueError``：这是**环境/数据状态**问题，
    不是调用方参数错误。
    """

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        body = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(
            "Hikyuu 数据完整性检查未通过，已阻止 StockManager.reload()"
            "（继续执行会导致段错误 exit 139）：\n" + body
        )


@dataclass
class PreflightReport:
    """preflight 检查结果（全部通过时返回，供调用方记录）。"""

    dest: str
    db_path: str
    h5_files: dict[str, str] = field(default_factory=dict)
    db_stock_count: int = 0
    h5_table_count: int = 0
    markets: list[str] = field(default_factory=list)
    last_dates: dict[str, int] = field(default_factory=dict)
    max_h5_date: int = 0
    #: Market 表存在但无 HDF5 数据的市场（非必要市场，仅记录）
    absent_markets: list[str] = field(default_factory=list)

    def summary(self) -> str:
        extra = f", 无数据市场={self.absent_markets}" if self.absent_markets else ""
        return (
            f"preflight OK: dest={self.dest}, "
            f"stock.db={self.db_stock_count} 证券, "
            f"HDF5={self.h5_table_count} 表, "
            f"markets={self.markets}, "
            f"lastDate={self.last_dates}{extra}"
        )


#: SQLite 中 marketid → 市场简称
_MARKETID_TO_NAME = {1: "SH", 2: "SZ", 3: "BJ"}
#: 市场简称 → HDF5 文件前缀
_MARKET_TO_PREFIX = {"SH": "sh", "SZ": "sz", "BJ": "bj"}

#: 合法的 year*10000+month*100+day 下限（1990-12-19 上交所开市）
_MIN_VALID_DATE = 19901219


def _read_h5_tables(path: str) -> tuple[set[str], int]:
    """读取 HDF5 中 ``/data`` 下的表名集合与最新日期。

    返回 ``(表名集合, 最大日期 YYYYMMDD)``。
    """
    import tables

    names: set[str] = set()
    latest = 0
    f = tables.open_file(path, "r")
    try:
        if "/data" in f:
            group = f.get_node("/data")
            for t in group._v_children.values():
                names.add(t._v_name)
                if getattr(t, "nrows", 0):
                    d = int(t[-1]["datetime"]) // 10000
                    latest = max(latest, d)
    finally:
        f.close()
    return names, latest


def _is_valid_ymd(v: int) -> bool:
    """判断整数是否为合法的 YYYYMMDD 日期。"""
    if not isinstance(v, int) or v < _MIN_VALID_DATE:
        return False
    s = str(v)
    if len(s) != 8:
        return False
    y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8])
    try:
        date(y, m, d)
    except ValueError:
        return False
    return True


def preflight(dest: str, *, require_markets: tuple[str, ...] = ("SH", "SZ")) -> PreflightReport:
    """在 ``StockManager.reload()`` 之前做结构一致性检查。

    :param dest: Hikyuu 数据目录（``datadir``）
    :param require_markets: 必须存在市场信息的市场
    :raises HikyuuDataIntegrityError: 任一项检查未通过
    :returns: :class:`PreflightReport`（检查通过时）
    """
    problems: list[str] = []

    # --- 检查 1：stock.db 存在 ---
    db_path = os.path.join(dest, "stock.db")
    if not os.path.isdir(dest):
        raise HikyuuDataIntegrityError([f"数据目录不存在: {dest}"])
    if not os.path.exists(db_path):
        raise HikyuuDataIntegrityError(
            [f"stock.db 不存在: {db_path}（请先运行 scripts/data/init_hikyuu_data.py）"]
        )

    # --- 读取 stock.db ---
    conn = sqlite3.connect(db_path)
    try:
        try:
            market_rows = conn.execute("select marketid, market, lastDate from market").fetchall()
        except sqlite3.Error as e:
            raise HikyuuDataIntegrityError([f"读取 Market 表失败: {e}"]) from e
        stock_rows = conn.execute(
            "select marketid, code, valid, endDate from stock"
        ).fetchall()
    finally:
        conn.close()

    # --- 检查 3：必要 market 数据存在 ---
    markets = [str(r[1]) for r in market_rows]
    missing_markets = [m for m in require_markets if m not in markets]
    if missing_markets:
        problems.append(
            f"Market 表缺少必要市场: {missing_markets}（现有: {markets}）"
        )

    # --- 检查 5 / 6：Market.lastDate 合法性 ---
    last_dates: dict[str, int] = {}
    for marketid, market, lastdate in market_rows:
        last_dates[str(market)] = int(lastdate or 0)
        if int(lastdate or 0) == 0:
            continue
        if not _is_valid_ymd(int(lastdate)):
            problems.append(
                f"Market.lastDate 非法: {market}={lastdate}"
                "（合法格式 YYYYMMDD；=99999999 通常意味着误用了 stock.endDate）"
            )

    # --- 收集 stock.db 中 valid 证券 ---
    db_tables: set[str] = set()
    for marketid, code, valid, enddate in stock_rows:
        if not valid:
            continue
        mkt = _MARKETID_TO_NAME.get(int(marketid))
        if mkt is None:
            problems.append(f"未知 marketid: {marketid}（code={code}）")
            continue
        db_tables.add(mkt + str(code))
        # 检查 6：valid=1 不得把 endDate=99999999 当成日期用
        if int(enddate or 0) == 99999999:
            # 这是 Hikyuu 对「仍在交易」证券的正常标记，本身不是问题；
            # 但若它出现在 Market.lastDate 里，上面的检查 5 会捕获。
            continue

    # --- 检查 2：HDF5 文件存在 ---
    h5_files: dict[str, str] = {}
    h5_tables: set[str] = set()
    max_h5_date = 0
    absent_markets: list[str] = []
    for mkt in markets:
        prefix = _MARKET_TO_PREFIX.get(mkt)
        if prefix is None:
            continue
        path = os.path.join(dest, f"{prefix}_day.h5")
        if not os.path.exists(path):
            # 必要市场缺失 → 阻断；非必要市场（如 BJ）缺失 → 仅记录
            if mkt in require_markets:
                problems.append(f"HDF5 日线文件缺失: {path}")
            else:
                absent_markets.append(mkt)
            continue
        h5_files[mkt] = path
        try:
            names, latest = _read_h5_tables(path)
        except Exception as e:  # noqa: BLE001 - HDF5 损坏
            problems.append(f"读取 HDF5 失败 {path}: {e}")
            continue
        h5_tables |= names
        max_h5_date = max(max_h5_date, latest)

    for mkt in require_markets:
        if mkt not in h5_files and mkt not in absent_markets:
            if not any(mkt in p for p in problems):
                problems.append(f"必要市场 {mkt} 无 HDF5 数据文件")

    if not h5_files:
        problems.append("没有任何 HDF5 日线文件存在（K线数据未导入）")

    # --- 检查 4（核心）：stock.db 与 HDF5 一致 ---
    if not problems:
        missing_kdata = sorted(db_tables - h5_tables)
        extra_kdata = sorted(h5_tables - db_tables)
        if missing_kdata:
            problems.append(
                f"{len(missing_kdata)} 个 valid 证券在 HDF5 中无 K线表"
                f"（示例: {missing_kdata[:5]}）"
                " —— 不一致会导致 reload 段错误。"
                "请运行 scripts/data/init_hikyuu_data.py 的 prune 步骤对齐。"
            )
        if extra_kdata:
            problems.append(
                f"{len(extra_kdata)} 个 HDF5 表在 stock.db 中无对应 valid 证券"
                f"（示例: {extra_kdata[:5]}）—— 同样属于结构不一致。"
            )

    if problems:
        raise HikyuuDataIntegrityError(problems)

    return PreflightReport(
        dest=dest,
        db_path=db_path,
        h5_files=h5_files,
        db_stock_count=len(db_tables),
        h5_table_count=len(h5_tables),
        markets=markets,
        last_dates=last_dates,
        max_h5_date=max_h5_date,
        absent_markets=absent_markets,
    )
