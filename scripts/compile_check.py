import py_compile, sys

files = [
    'core/consensus.py',
    'core/rpc_service.py', 
    'main.py',
    'core/dual_witness_exchange.py',
]

ok = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"OK: {f}")
        ok += 1
    except py_compile.PyCompileError as e:
        print(f"FAIL: {f}")
        print(f"  {e}")

print(f"\n{ok}/{len(files)} passed")
sys.exit(0 if ok == len(files) else 1)
