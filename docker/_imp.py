import sys

print("Python", sys.version.split()[0])
try:
    import hikyuu

    print("SUCCESS: hikyuu version =", getattr(hikyuu, "__version__", "(no attr)"))
except Exception as e:
    print("FAILED:", type(e).__name__)
    print("  msg:", str(e)[:300])
