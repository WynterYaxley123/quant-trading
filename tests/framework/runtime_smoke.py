"""最小运行链路 smoke test。

目的：确认写在 D:\\quant-trading 的代码，Docker 确实可以执行。

只做：
    - import hikyuu / rqalpha / akshare
    - 打印环境信息
    - 返回 exit code 0

不做策略、不跑回测、不下载数据。
"""

import sys


def main() -> int:
    print("=" * 50)
    print("QUANT FRAMEWORK RUNTIME SMOKE TEST")
    print("=" * 50)

    print(f"python:      {sys.version.split()[0]}")
    print(f"executable:  {sys.executable}")

    import hikyuu  # noqa: PLC0415
    import numpy  # noqa: PLC0415
    import pandas  # noqa: PLC0415
    import rqalpha  # noqa: PLC0415

    print(f"hikyuu:      {hikyuu.__version__}")
    print(f"rqalpha:     {rqalpha.__version__}")
    print(f"numpy:       {numpy.__version__}")
    print(f"pandas:      {pandas.__version__}")

    try:
        import akshare  # noqa: PLC0415

        print(f"akshare:     {akshare.__version__}")
    except ImportError:
        print("akshare:     IMPORT_FAILED")
        return 1

    print("-" * 50)
    print("RUNTIME_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
