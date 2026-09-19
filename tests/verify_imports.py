import sys

mods = []


def t(name):
    try:
        m = __import__(name)
        v = getattr(m, "__version__", "n/a")
        print("PASS {} {}".format(name, v))
        mods.append((name, True))
    except Exception as e:
        print("FAIL {} :: {}: {}".format(name, type(e).__name__, str(e)[:300]))
        mods.append((name, False))


for n in ["hikyuu", "rqalpha", "akshare", "numpy", "pandas",
          "scipy", "matplotlib", "pytest", "jupyter"]:
    t(n)

bad = [n for n, ok in mods if not ok]
print("SUMMARY {}/{} ok".format(len(mods) - len(bad), len(mods)))
sys.exit(1 if bad else 0)
