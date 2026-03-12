# POUW Chain Quick Start Guide

##  One-Click Start

### Windows Users

**Method 1: Double-Click Launch**
```
Double-click to run: 启动.bat
```

**Method 2: PowerShell**
```powershell
# Regular user (light node, no mining)
.\start.ps1

# Miner mode
.\start.ps1 -Mining

# Compute provider mode  
.\start.ps1 -Provider
```

**Stop Service:**
```powershell
.\stop.ps1
```

---

##  Access Addresses

| Service | Address |
|---------|---------|
| Frontend UI | http://localhost:3002 |
| Backend RPC | https://127.0.0.1:8545 (HTTPS, self-signed TLS) |

---

##  User Roles

| Role | Use Case | Mining |
|------|----------|--------|
|  Light Node | Regular users, purchase compute services |  |
|  Miner | Earn token rewards through mining |  |
|  Provider | Rent out computing power for income |  |

---

##  Manual Start

**Terminal 1 - Backend:**
```bash
cd c:\Users\17006\Desktop\maincoin
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd c:\Users\17006\Desktop\maincoin\frontend
npm run dev
```

---

##  First-Time Checklist

- [ ] Python 3.9+ installed
- [ ] Node.js 18+ installed
- [ ] Run `pip install -r requirements.txt`
- [ ] Run `cd frontend && npm install`
- [ ] Back up mnemonic phrase (displayed on first launch)

---

##  FAQ

**Q: Port already in use?**
```powershell
.\stop.ps1  # Stop all services first
.\start.ps1 # Then restart
```

**Q: How to change ports?**
Edit `rpc.port` and `p2p.port` in `config.yaml`

**Q: How to switch to miner mode?**
```powershell
.\start.ps1 -Mining
```
Or edit `config.yaml` and set `mining.enabled: true`
