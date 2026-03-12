#!/bin/bash
# POUW Chain - 3 节点压力测试脚本
# 用法: bash scripts/stress_test.sh [rpc_port] [num_requests]

RPC_PORT=${1:-8545}
NUM_REQUESTS=${2:-100}
BASE_URL="http://localhost:$RPC_PORT"

echo "========================================"
echo "  POUW Chain 压力测试"
echo "  目标: $BASE_URL"
echo "  请求数: $NUM_REQUESTS"
echo "========================================"

# 1. 连续查询链信息 (吞吐量测试)
echo ""
echo "[TEST 1] chain_getInfo 吞吐量..."
START=$(date +%s%N)
SUCCESS=0
FAIL=0
for i in $(seq 1 $NUM_REQUESTS); do
    RESP=$(curl -s -X POST "$BASE_URL" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"chain_getInfo","params":[],"id":'$i'}' \
        --connect-timeout 2 --max-time 5)
    if echo "$RESP" | grep -q '"result"'; then
        SUCCESS=$((SUCCESS + 1))
    else
        FAIL=$((FAIL + 1))
    fi
done
END=$(date +%s%N)
ELAPSED=$(( (END - START) / 1000000 ))
TPS=$(echo "scale=2; $NUM_REQUESTS * 1000 / $ELAPSED" | bc 2>/dev/null || echo "N/A")
echo "  成功: $SUCCESS / $NUM_REQUESTS"
echo "  耗时: ${ELAPSED}ms"
echo "  TPS: $TPS"

# 2. 查询余额 (读操作)
echo ""
echo "[TEST 2] utxo_getBalance 读取性能..."
START=$(date +%s%N)
SUCCESS=0
for i in $(seq 1 $((NUM_REQUESTS / 2))); do
    RESP=$(curl -s -X POST "$BASE_URL" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"utxo_getBalance","params":{"address":"test_addr_'$i'","sector":"MAIN"},"id":'$i'}' \
        --connect-timeout 2 --max-time 5)
    if echo "$RESP" | grep -q '"result"\|"error"'; then
        SUCCESS=$((SUCCESS + 1))
    fi
done
END=$(date +%s%N)
ELAPSED=$(( (END - START) / 1000000 ))
echo "  成功: $SUCCESS / $((NUM_REQUESTS / 2))"
echo "  耗时: ${ELAPSED}ms"

# 3. 区块查询 (按高度)
echo ""
echo "[TEST 3] chain_getBlock 区块查询..."
SUCCESS=0
for i in 0 1 2 3 4; do
    RESP=$(curl -s -X POST "$BASE_URL" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"chain_getBlock","params":{"height":'$i'},"id":'$i'}')
    if echo "$RESP" | grep -q '"hash"'; then
        SUCCESS=$((SUCCESS + 1))
        HEIGHT=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['height'])" 2>/dev/null)
        echo "  区块 #$i: 存在 (height=$HEIGHT)"
    else
        echo "  区块 #$i: 不存在"
    fi
done

# 4. 并发压力
echo ""
echo "[TEST 4] 并发 RPC 请求 (10并发 x 10轮)..."
START=$(date +%s%N)
for round in $(seq 1 10); do
    for j in $(seq 1 10); do
        curl -s -X POST "$BASE_URL" \
            -H "Content-Type: application/json" \
            -d '{"jsonrpc":"2.0","method":"node_getStatus","params":[],"id":'$j'}' \
            --connect-timeout 2 --max-time 5 > /dev/null 2>&1 &
    done
    wait
done
END=$(date +%s%N)
ELAPSED=$(( (END - START) / 1000000 ))
echo "  100 并发请求耗时: ${ELAPSED}ms"

echo ""
echo "========================================"
echo "  压力测试完成"
echo "========================================"
