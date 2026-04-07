from core.rpc_service import NodeRPCService


class _DummyBlock:
    def __init__(self, timestamp=0.0, txs=None):
        self.timestamp = timestamp
        self.transactions = txs or []


class _DummyConsensus:
    def __init__(self):
        self.sector = "MAIN"
        self.current_difficulty = 7
        self._sbox_mining_enabled = True
        self.consensus_mode = "mixed"
        self.consensus_sbox_ratio = 0.65
        self.chain = [_DummyBlock(timestamp=123.0, txs=[{"id": 1}])]

    def get_chain_height(self):
        return 3

    def get_chain_info(self):
        return {
            "consensus_selected_distribution": {
                "window": 10,
                "counts": {"POUW": 4, "SBOX_POUW": 6, "POW": 0},
                "sbox_ratio": 0.6,
                "pouw_ratio": 0.4,
                "pow_ratio": 0.0,
            },
            "consensus_mined_distribution": {
                "window": 8,
                "counts": {"POUW": 3, "SBOX_POUW": 5, "POW": 0},
                "sbox_ratio": 0.625,
                "pouw_ratio": 0.375,
                "pow_ratio": 0.0,
            },
        }


def test_chain_get_info_contains_mixed_consensus_fields():
    svc = NodeRPCService()
    svc.consensus_engine = _DummyConsensus()

    info = svc._chain_get_info()

    assert info["consensusMode"] == "mixed"
    assert info["consensusSboxRatio"] == 0.65
    assert "consensusSelectedDistribution" in info
    assert "consensusMinedDistribution" in info
    assert info["consensusSelectedDistribution"]["window"] == 10
    assert info["consensusMinedDistribution"]["counts"]["SBOX_POUW"] == 5
