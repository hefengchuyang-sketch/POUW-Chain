# POUW Multi-Sector Chain API Documentation

## Overview

POUW Multi-Sector Chain is a multi-sector blockchain system based on Proof of Useful Work (PoUW). This document describes the API interfaces of the core modules.

---

## 1. RPC Service API

### Connection Information

- **Default Port**: 8545
- **Protocol**: JSON-RPC 2.0 over HTTPS (self-signed TLS certificate)
- **Content-Type**: application/json
- **Base URL**: `https://127.0.0.1:8545`

> **Note**: When using curl, add the `-k` parameter to skip self-signed certificate verification.

### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": {},
  "id": 1
}
```

### Response Format

```json
{
  "jsonrpc": "2.0",
  "result": {},
  "id": 1
}
```

---

### Transaction-Related

#### `tx_send`
Send a signed transaction to the network

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| transaction | object | Transaction data object |

**Returns**:
```json
{
  "txid": "abc123...",
  "status": "in_mempool",
  "timestamp": 1704067200.0
}
```

#### `tx_get`
Query a transaction by TXID

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| txid | string | Transaction ID |

**Returns**: Transaction object

#### `tx_getByAddress`
Query transactions related to an address

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| address | string | Address |
| limit | number | Result limit (default 50) |

**Returns**: Array of transaction objects

---

### Mempool-Related

#### `mempool_getInfo`
Get mempool status

**Returns**:
```json
{
  "count": 100,
  "total_fees": 1.5,
  "total_size": 25600
}
```

#### `mempool_getPending`
Get pending transactions

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| limit | number | Result limit (default 20) |
| sector | string | Sector filter (optional) |

---

### Block-Related

#### `block_getLatest`
Get the latest block

**Returns**: Block object

#### `block_getByHeight`
Get block by height

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| height | number | Block height |

#### `block_getByHash`
Get block by hash

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| hash | string | Block hash |

#### `chain_getHeight`
Get current block height

**Returns**: number

#### `chain_getInfo`
Get chain information

**Returns**:
```json
{
  "chain_id": "pouw-mainnet-v1",
  "height": 12345,
  "syncing": false,
  "node_id": "abc123",
  "peers": 10,
  "timestamp": 1704067200.0
}
```

---

### Account-Related

#### `account_getBalance`
Query address balance

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| address | string | Address |
| sector | string | Sector (optional) |

**Returns**:
```json
{
  "MAIN": 100.5,
  "H100": 50.0,
  "RTX4090": 200.0
}
```

#### `account_getUTXOs`
Get available UTXOs for an address

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| address | string | Address |
| sector | string | Sector (optional) |
| limit | number | Result limit (default 100) |

#### `account_getNonce`
Get address nonce

---

### Network-Related

#### `node_getInfo`
Get node information

**Returns**:
```json
{
  "node_id": "abc123",
  "version": "1.0.0",
  "network": "pouw-mainnet",
  "height": 12345,
  "syncing": false,
  "peers": 10,
  "uptime": 86400,
  "capabilities": ["tx", "block", "witness", "compute"]
}
```

#### `node_getPeers`
Get peer node list

#### `node_isSyncing`
Check if the node is syncing

---

### Compute Market

#### `compute_submitOrder`
Submit a compute order

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| sector | string | Target sector |
| amount | number | Compute demand (TFLOPS) |
| duration | number | Duration (hours) |
| price | number | Bid price (MAIN/TFLOPS/hour) |

#### `compute_getOrder`
Query a compute order

#### `compute_getMarket`
Get compute market information

---

### Governance

#### `governance_vote`
Submit a governance vote

**Parameters**:
| Name | Type | Description |
|------|------|-------------|
| proposal_id | string | Proposal ID |
| vote | string | Vote choice (FOR/AGAINST/ABSTAIN) |
| signature | string | Signature |

#### `governance_getProposals`
Get governance proposal list

---

## 2. User Database API

### UserDatabase Class

#### `create_user(username, password)`
Create a new user

**Parameters**:
- `username`: Username (3-50 characters)
- `password`: Password (at least 6 characters)

**Returns**:
```python
{
    "success": True,
    "user": {...},
    "mnemonic": "word1 word2 ..."
}
```

#### `login(username, password)`
User login

**Returns**: User object or None

#### `get_user_by_id(user_id)`
Get user by ID

#### `get_wallets(user_id)`
Get user wallet list

#### `create_wallet(user_id, sector, name)`
Create a new wallet

---

## 3. Blockchain API

### BlockchainState Class

#### `get_height(sector="MAIN")`
Get current height

#### `get_latest_block(sector="MAIN")`
Get the latest block

#### `get_block_by_hash(block_hash)`
Get block by hash

#### `get_block_by_height(height, sector="MAIN")`
Get block by height

#### `add_block(block, tx_store=None)`
Add a block to the chain

**Returns**: `(bool, str)` - (success/failure, message)

---

## 4. Transaction API

### Mempool Class

#### `add(transaction)`
Add a transaction to the mempool

**Returns**: `(bool, str)` - (success/failure, message)

#### `get(txid)`
Get a transaction

#### `remove(txid)`
Remove a transaction

#### `get_pending(limit, sector=None)`
Get pending transaction list

#### `get_stats()`
Get statistics

### TransactionBuilder Class

#### `build_transfer(from_addr, to_addr, amount, sector, fee=0)`
Build a transfer transaction

---

## 5. Compute Market API

### ComputeMarket Class

#### `create_order(requester, sector, compute_units, price, duration)`
Create a compute order

**Returns**: `(order_id, order_object)`

#### `register_node(node_id, sector, capacity, price)`
Register a compute node

#### `assign_nodes(order_id, limit=10)`
Assign nodes to an order

---

## 6. Exchange/Treasury API

### ExchangeEngine Class

#### `place_order(address, sector, amount, price, is_buy)`
Place an order

**Returns**: Order object

#### `match_orders()`
Match orders

### Treasury Class

#### `deposit(amount, source, description)`
Deposit funds

#### `withdraw(amount, destination, description)`
Withdraw funds

#### `get_balance()`
Get balance

---

## 7. Governance API

### GovernanceModule Class

#### `stake(address, amount)`
Stake tokens

#### `unstake(address, amount)`
Unstake tokens

#### `create_proposal(creator, type, title, description, params)`
Create a proposal

#### `vote(proposal_id, voter, choice)`
Vote

#### `execute_proposal(proposal_id)`
Execute a proposal

---

## 8. P2P Network API

### EnhancedP2PNode Class

#### `connect_to_network(bootstrap_nodes)`
Connect to the network

#### `broadcast_transaction(tx_data)`
Broadcast a transaction

#### `broadcast_block(block_data)`
Broadcast a block

#### `sync_mempool(peer_id)`
Sync the mempool

---

## 9. PoUW Consensus API

### UnifiedBlockBuilder Class

#### `submit_pouw_proof(proof)`
Submit a PoUW proof

#### `submit_task(task)`
Submit a PoUW task

#### `mine_block(miner_address, timeout=60)`
Mine a block

#### `start_mining(miner_address, interval=15)`
Start continuous mining

#### `stop_mining()`
Stop mining

---

## Error Codes

| Code | Meaning |
|------|---------|
| -32700 | Parse error |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid parameters |
| -32603 | Internal error |
| -40001 | Unauthorized |
| -40002 | Transaction not found |
| -40003 | Transaction rejected |
| -40004 | Insufficient balance |
| -40005 | Invalid signature |
| -40006 | Node syncing |

---

## Sectors

| Sector | Purpose | Target Block Time |
|--------|---------|-------------------|
| MAIN | Value anchor / Cross-sector settlement | 30s |
| H100 | Large model inference / Training | 20s |
| RTX4090 | Video rendering / HPC | 25s |
| RTX3080 | General GPU computing | 30s |
| CPU | CPU-intensive tasks | 45s |
