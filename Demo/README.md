# Demo (One-Click)

This folder contains a reproducible end-to-end demo package for:

- Frontend/Backend order flow fixes
- Free order placement
- Mining account visibility for accepted orders and running programs
- Order result delivery back to the order account
- Runnable Docker setup

## Quick Start

1. Run one click script:

```bat
Demo\start-demo.bat
```

2. Stop and clean:

```bat
Demo\stop-demo.bat
```

## What the demo verifies

- Creates two accounts:
  - Order Account
  - Mining Account
- Starts mining account in `task_only` mode
- Places a free order from Order Account
- Mining Account accepts the order
- Mining status shows:
  - accepted orders
  - running programs
- Completes order and writes result back to order
- Prints order result and demo balances
- Calls additional feature APIs (`chain_getInfo`, `blockchain_getHeight`, free `orderbook_submitBid`)

## Docker endpoint

- RPC: `http://127.0.0.1:18545`
- P2P: `127.0.0.1:19333`

## Recording

Use your preferred recorder (OBS or Xbox Game Bar) and capture:

1. Run `Demo\start-demo.bat`
2. Console output from `demo_runner.py`
3. Optional API checks with your own client
4. Run `Demo\stop-demo.bat`
