"""Quick status check for running node."""
import urllib.request, json, ssl, sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def rpc(method, params=None):
    req = urllib.request.Request(
        'https://127.0.0.1:8545/',
        data=json.dumps({'jsonrpc': '2.0', 'method': method, 'params': params or [], 'id': 1}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    r = urllib.request.urlopen(req, context=ctx)
    return json.loads(r.read().decode())

# Start mining if --mine flag
if '--mine' in sys.argv:
    resp = rpc('mining_start')
    print("Mining start:", resp.get('result', resp.get('error')))
    print()

# Dashboard stats
resp = rpc('dashboard_getStats')
if 'result' in resp:
    d = resp['result']
    print(f"Block Height:     {d['blockHeight']}")
    print(f"Balance (avail):  {d['balance']}")
    print(f"Pending (mature): {d.get('pendingBalance', 'N/A')}")
    print(f"Sector Total:     {d.get('sectorTotal', 0)}")
    print(f"Online Miners:    {d['onlineMiners']}")
    print(f"Miner Address:    {d['minerAddress']}")
    print(f"Blocks Mined:     {d.get('totalBlocksMined', 0)}")
else:
    print("Error:", resp.get('error'))

# Mining status
resp2 = rpc('mining_getStatus')
if 'result' in resp2:
    m = resp2['result']
    print(f"Mining:           {m['isMining']}")
    print(f"Blocks Mined:     {m['blocksMined']}")
    print(f"Total Rewards:    {m['totalRewards']}")
    print(f"GPU:              {m.get('gpuName', 'N/A')}")
else:
    print("Mining Error:", resp2.get('error'))
