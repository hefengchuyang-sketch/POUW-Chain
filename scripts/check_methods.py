"""Extract RPC method names from frontend and compare with backend registry"""
import re

# Extract frontend methods
with open('frontend/src/api/index.ts', 'r', encoding='utf-8') as f:
    content = f.read()

frontend_methods = sorted(set(re.findall(r"rpcCall\('([^']+)'", content)))
print(f"Frontend calls {len(frontend_methods)} unique RPC methods:")
for m in frontend_methods:
    print(f"  {m}")

# Extract backend registered methods
with open('core/rpc_service.py', 'r', encoding='utf-8') as f:
    rpc_content = f.read()

backend_methods = set(re.findall(r'registry\.register\(\s*"([^"]+)"', rpc_content))

# Also check rpc_handlers folder
import os
handlers_dir = 'core/rpc_handlers'
if os.path.exists(handlers_dir):
    for fname in os.listdir(handlers_dir):
        if fname.endswith('.py'):
            with open(os.path.join(handlers_dir, fname), 'r', encoding='utf-8') as f:
                hcontent = f.read()
            handler_methods = re.findall(r'registry\.register\(\s*"([^"]+)"', hcontent)
            backend_methods.update(handler_methods)

print(f"\nBackend registers {len(backend_methods)} methods")

# Compare
missing_in_backend = [m for m in frontend_methods if m not in backend_methods]
print(f"\n=== {len(missing_in_backend)} Frontend methods NOT in backend ===")
for m in missing_in_backend:
    print(f"  MISSING: {m}")
    # Try to find similar backend method
    prefix = m.split('_')[0]
    similar = [b for b in sorted(backend_methods) if b.startswith(prefix + '_')]
    if similar:
        print(f"    Similar: {similar}")
