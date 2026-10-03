"""Hikyuu 行情数据初始化脚本（无 GUI，Linux Docker 适用）。

背景
----
Hikyuu 2.8.2 在 Linux 容器内没有官方 CLI 导入工具，其 GUI（HikyuuTDX）底层
逻辑即 ``hikyuu.data.pytdx_to_h5`` 中的 Python 函数。本脚本直接复用这些函数，
通过 pytdx 协议从通达信行情服务器拉取真实行情。

实测事实（详见 ``docs/data/hikyuu_data_capabilities.md``）：
- 容器内可连通 pytdx 服务器（如 180.101.48.170:7709）。
- 依赖 ``pytdx`` / ``tables`` 均已随 hikyuu 安装，无需额外 pip。
- ``import_stock_name(..., ['fund'])`` 会触发 hikyuu 内部 bug
  （``stktype_list.remove(STOCKTYPE.INDEX)`` ValueError），
  必须传 ``['stock', 'fund']``。
- **关键**：``stock.db`` 中的证券必须与 HDF5 中的表一一对应，
  否则 ``StockManager.reload()`` 会段错误（SIGSEGV，实测 exit 139）。
  因此导入 K线后必须执行 :func:`prune_stock_db` 对齐两边。

用法（在容器内）::

    python scripts/data/init_hikyuu_data.py --symbols 510300,159934 --start 2020-01-01
    python scripts/data/init_hikyuu_data.py --all-etf --start 2018-01-01
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
import time
from collections.abc import Iterable, Sequence

# --- 常量 -----------------------------------------------------------------

DEFAULT_TDX_SERVERS: tuple[tuple[str, int], ...] = (
    ("180.101.48.170", 7709),
    ("123.125.108.90", 7709),
)

#: 项目内 Hikyuu 数据目录（容器内路径 = /workspace/data/hikyuu）
DEFAULT_DEST = os.environ.get("HIKYUU_DATA_DIR", "/workspace/data/hikyuu")

#: 用户持仓 + 常用基准 ETF（512660 军工 / 512400 有色 / 159934 黄金 / 159745 建材）
DEFAULT_ETF_SYMBOLS: tuple[str, ...] = (
    "510300",  # 沪深300ETF华泰柏瑞
    "510500",  # 中证500ETF南方
    "512660",  # 军工ETF国泰
    "512400",  # 有色金属ETF南方
    "159934",  # 黄金ETF易方达
    "159915",  # 创业板ETF易方达
    "159745",  # 建材ETF国泰
    "588000",  # 科创50ETF华夏
)


def _log(msg: str) -> None:
    logging.getLogger(__name__).info("%s", msg)


# --- 步骤 1：数据库与配置 -------------------------------------------------


def ensure_config(dest: str = DEFAULT_DEST, *, force: bool = False) -> str:
    """生成/修正 ``~/.hikyuu/hikyuu.ini`` 指向项目数据目录。

    返回 ini 路径。已存在且指向正确目录时不重复写。
    """
    from hikyuu.data.hku_config_template import generate_default_config

    generate_default_config()  # 生成默认模板（已存在则跳过）
    cfg_path = os.path.join(os.path.expanduser("~"), ".hikyuu", "hikyuu.ini")
    if not os.path.exists(cfg_path):
        raise RuntimeError(f"未能生成配置文件: {cfg_path}")

    text = open(cfg_path, encoding="utf-8").read()
    if force or dest not in text:
        import re

        text = re.sub(r"^(tmpdir\s*=\s*).*$", rf"\g<1>{dest}/tmp", text, flags=re.M)
        text = re.sub(r"^(datadir\s*=\s*).*$", rf"\g<1>{dest}", text, flags=re.M)
        text = re.sub(r"^(db\s*=\s*).*stock\.db\s*$", rf"\g<1>{dest}/stock.db", text, flags=re.M)
        text = re.sub(
            r"^((?:sh|sz|bj)_(?:day|min|min5|time|trans)\s*=\s*).*$",
            lambda m: m.group(1) + dest + "/" + os.path.basename(m.group(0)),
            text,
            flags=re.M,
        )
        open(cfg_path, "w", encoding="utf-8").write(text)
        _log(f"已更新配置: {cfg_path} -> {dest}")
    return cfg_path


def ensure_database(dest: str = DEFAULT_DEST) -> str:
    """创建/升级 SQLite 基础信息库，返回 db 路径。"""
    from hikyuu.data.common_sqlite3 import create_database

    os.makedirs(dest, exist_ok=True)
    os.makedirs(os.path.join(dest, "tmp"), exist_ok=True)
    db_path = os.path.join(dest, "stock.db")
    conn = sqlite3.connect(db_path)
    create_database(conn)
    conn.close()
    _log(f"基础信息库就绪: {db_path}")
    return db_path


# --- 步骤 2：导入 ---------------------------------------------------------


def _connect_api(servers: Sequence[tuple[str, int]] = DEFAULT_TDX_SERVERS):
    """逐个尝试 tdx 服务器，返回已连接的 api。全部失败时抛错。"""
    from pytdx.hq import TdxHq_API

    last_err: Exception | None = None
    for host, port in servers:
        api = TdxHq_API()
        try:
            if api.connect(host, port, time_out=10):
                _log(f"已连接行情服务器 {host}:{port}")
                return api
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(f"无法连接任何行情服务器: {servers}。最后错误: {last_err}")


def import_names(conn: sqlite3.Connection, api) -> int:
    """导入指数 + 证券代码表。

    注意必须传 ``['stock', 'fund']``：只传 ``['fund']`` 会触发 hikyuu 内部
    ``stktype_list.remove(STOCKTYPE.INDEX)`` 的 ValueError（实测 bug）。
    """
    from hikyuu.data.pytdx_to_h5 import import_index_name, import_stock_name

    total = import_index_name(conn)
    _log(f"指数代码表: {total} 条")
    for market in ("SH", "SZ"):
        n = import_stock_name(conn, api, market, ["stock", "fund"])
        _log(f"{market} 证券代码表: {n} 条")
        total += n
    conn.commit()
    return total


def import_daily_for(conn: sqlite3.Connection, api, symbols: Iterable[str], dest: str) -> int:
    """只导入指定 symbol 的日线（不跑全市场）。

    返回导入的总 K线数。
    """
    from hikyuu.data.common_h5 import open_h5file
    from hikyuu.data.pytdx_to_h5 import import_one_stock_data

    symset = {s.strip().upper() for s in symbols if s.strip()}
    cur = conn.cursor()
    total = 0
    for market, marketid in (("SH", 1), ("SZ", 2)):
        h5 = open_h5file(dest, market, "DAY")
        try:
            for code in sorted(symset):
                row = cur.execute(
                    "select stockid, marketid, code, valid, type from stock "
                    "where code=? and marketid=?",
                    (code, marketid),
                ).fetchone()
                if row is None:
                    continue
                n, ok, last = import_one_stock_data(conn, api, h5, market, "DAY", row)
                _log(f"  {market}{code}: {n} bars (ok={ok}, last={last})")
                total += n
        finally:
            h5.close()
    conn.commit()
    return total


def prune_stock_db(conn: sqlite3.Connection, dest: str) -> tuple[int, int]:
    """对齐 ``stock.db`` 与 HDF5：删除 HDF5 中无 K线表的证券。

    **这是防止 ``StockManager.reload()`` 段错误的必需步骤**（实测）：
    HDF5 缺少某证券的表而 stock 表里存在该证券时，Hikyuu C++ 层会崩溃。

    返回 ``(保留数, 删除数)``。
    """
    import tables

    present: set[str] = set()
    for market in ("sh", "sz", "bj"):
        path = os.path.join(dest, f"{market}_day.h5")
        if not os.path.exists(path):
            continue
        f = tables.open_file(path, "r")
        try:
            if "/data" in f:
                present |= {t._v_name for t in f.get_node("/data")._v_children.values()}
        finally:
            f.close()

    cur = conn.cursor()
    rows = cur.execute("select stockid, marketid, code from stock").fetchall()
    mkt = {1: "SH", 2: "SZ", 3: "BJ"}
    drop = [sid for sid, mid, code in rows if (mkt.get(mid, "?") + code) not in present]
    if drop:
        cur.executemany("delete from stock where stockid=?", [(i,) for i in drop])
    conn.commit()
    kept = len(rows) - len(drop)
    _log(f"对齐 stock.db 与 HDF5: 保留 {kept}, 删除 {len(drop)}")
    return kept, len(drop)


def update_market_last_date(conn: sqlite3.Connection) -> None:
    """把 Market.lastDate 更新为已有 K线的最新日期（从 HDF5 读取）。

    **注意**：不能用 ``stock.endDate`` —— 有效证券的 endDate 是默认大值
    （实测 ``valid=1`` 时为 ``99999999``），写进 Market 表会让 Hikyuu 在
    ``Loading market information`` 阶段报
    ``Day of month value is out of range 1..31`` 并使市场信息加载失败。
    因此这里从 HDF5 实际读取每个市场的最新日期。
    """
    import tables
    from hikyuu.data.common_sqlite3 import update_last_date

    marketid_map = ((1, "SH", "sh"), (2, "SZ", "sz"), (3, "BJ", "bj"))
    for marketid, market, prefix in marketid_map:
        path = os.path.join(DEST_CACHE[0], f"{prefix}_day.h5")
        if not os.path.exists(path):
            continue
        latest = 0
        f = tables.open_file(path, "r")
        try:
            if "/data" in f:
                for t in f.get_node("/data")._v_children.values():
                    if t.nrows:
                        d = int(t[-1]["datetime"]) // 10000
                        latest = max(latest, d)
        finally:
            f.close()
        if latest:
            update_last_date(conn, marketid, latest)
            _log(f"{market} lastDate -> {latest}")


#: 由 main() 注入的 dest（供 update_market_last_date 使用）
DEST_CACHE: list[str] = [DEFAULT_DEST]


# --- CLI ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="初始化 Hikyuu 日线行情数据")
    ap.add_argument("--dest", default=DEFAULT_DEST, help="Hikyuu 数据目录")
    ap.add_argument("--symbols", default="", help="逗号分隔的证券代码；留空则用默认 ETF 集")
    ap.add_argument("--all-etf", action="store_true", help="使用内置 ETF 集（默认行为）")
    ap.add_argument("--names-only", action="store_true", help="只导入代码表，不导入 K线")
    ap.add_argument("--server", default="", help="指定行情服务器 host:port")
    args = ap.parse_args(argv)

    symbols = (
        [s for s in args.symbols.split(",") if s.strip()]
        if args.symbols.strip()
        else list(DEFAULT_ETF_SYMBOLS)
    )

    servers = DEFAULT_TDX_SERVERS
    if args.server:
        host, _, port = args.server.partition(":")
        servers = ((host, int(port or 7709)),) + tuple(DEFAULT_TDX_SERVERS)

    t0 = time.time()
    DEST_CACHE[0] = args.dest
    ensure_config(args.dest, force=True)
    db_path = ensure_database(args.dest)
    conn = sqlite3.connect(db_path)
    api = _connect_api(servers)
    try:
        import_names(conn, api)
        total = 0
        if not args.names_only:
            _log(f"导入日线: {symbols}")
            total = import_daily_for(conn, api, symbols, args.dest)
        prune_stock_db(conn, args.dest)
        update_market_last_date(conn)
    finally:
        try:
            api.disconnect()
        except Exception:  # noqa: BLE001
            pass
        conn.close()

    _log(f"完成：{total} 根 K线，耗时 {time.time() - t0:.1f}s")
    _log(f"数据目录: {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
