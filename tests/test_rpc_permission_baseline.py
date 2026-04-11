from core.security import PUBLIC_RPC_METHODS
from core.rpc_service import NodeRPCService, RPCPermission


SENSITIVE_METHODS = {
    "wallet_getInfo",
    "wallet_getBalance",
    "wallet_getTransactions",
    "account_getTransactions",
    "account_getSubAddresses",
}


def test_sensitive_rpc_methods_not_public():
    overlap = SENSITIVE_METHODS.intersection(PUBLIC_RPC_METHODS)
    assert not overlap, f"Sensitive methods exposed as PUBLIC: {sorted(overlap)}"


def test_account_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("account_getTransactions") == RPCPermission.USER
    assert service.registry.get_permission("account_getSubAddresses") == RPCPermission.USER
    assert service.registry.get_permission("wallet_getTransactions") == RPCPermission.USER
    assert service.registry.get_permission("wallet_getBalance") == RPCPermission.USER


def test_task_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("task_getList") == RPCPermission.PUBLIC
    assert service.registry.get_permission("task_getInfo") == RPCPermission.PUBLIC
    assert service.registry.get_permission("task_getFiles") == RPCPermission.PUBLIC
    assert service.registry.get_permission("task_getLogs") == RPCPermission.PUBLIC
    assert service.registry.get_permission("task_getOutputs") == RPCPermission.PUBLIC
    assert service.registry.get_permission("task_getRuntimeStatus") == RPCPermission.PUBLIC
    assert service.registry.get_permission("task_create") == RPCPermission.USER
    assert service.registry.get_permission("task_cancel") == RPCPermission.USER
    assert service.registry.get_permission("task_raiseDispute") == RPCPermission.USER
    assert service.registry.get_permission("task_acceptResult") == RPCPermission.USER


def test_scheduler_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("scheduler_registerMiner") == RPCPermission.MINER
    assert service.registry.get_permission("scheduler_heartbeat") == RPCPermission.MINER
    assert service.registry.get_permission("scheduler_submitResult") == RPCPermission.MINER
    assert service.registry.get_permission("scheduler_getTask") == RPCPermission.PUBLIC
    assert service.registry.get_permission("scheduler_rateMiner") == RPCPermission.USER
    assert service.registry.get_permission("scheduler_getBlindBatch") == RPCPermission.MINER
    assert service.registry.get_permission("scheduler_submitBlindBatch") == RPCPermission.MINER
    assert service.registry.get_permission("scheduler_getMinerTrust") == RPCPermission.PUBLIC


def test_compute_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("compute_submitOrder") == RPCPermission.USER
    assert service.registry.get_permission("compute_getOrder") == RPCPermission.USER
    assert service.registry.get_permission("compute_getMarket") == RPCPermission.PUBLIC
    assert service.registry.get_permission("compute_getTrapQuestion") == RPCPermission.USER
    assert service.registry.get_permission("compute_submitTrapAnswer") == RPCPermission.USER
    assert service.registry.get_permission("compute_acceptOrder") == RPCPermission.USER
    assert service.registry.get_permission("compute_completeOrder") == RPCPermission.USER
    assert service.registry.get_permission("compute_commitResult") == RPCPermission.USER
    assert service.registry.get_permission("compute_revealResult") == RPCPermission.USER
    assert service.registry.get_permission("compute_getOrderEvents") == RPCPermission.USER
    assert service.registry.get_permission("compute_cancelOrder") == RPCPermission.USER


def test_encrypted_task_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("encryptedTask_create") == RPCPermission.USER
    assert service.registry.get_permission("encryptedTask_submit") == RPCPermission.USER
    assert service.registry.get_permission("encryptedTask_getStatus") == RPCPermission.PUBLIC
    assert service.registry.get_permission("encryptedTask_getResult") == RPCPermission.USER
    assert service.registry.get_permission("encryptedTask_process") == RPCPermission.MINER
    assert service.registry.get_permission("encryptedTask_getBillingReport") == RPCPermission.USER
    assert service.registry.get_permission("encryptedTask_generateKeypair") == RPCPermission.USER
    assert service.registry.get_permission("encryptedTask_registerMiner") == RPCPermission.MINER
    assert service.registry.get_permission("encryptedTask_cancel") == RPCPermission.USER


def test_file_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("file_initUpload") == RPCPermission.USER
    assert service.registry.get_permission("file_uploadChunk") == RPCPermission.USER
    assert service.registry.get_permission("file_finalizeUpload") == RPCPermission.USER
    assert service.registry.get_permission("file_getUploadProgress") == RPCPermission.USER
    assert service.registry.get_permission("file_getInfo") == RPCPermission.USER
    assert service.registry.get_permission("file_downloadChunk") == RPCPermission.USER
    assert service.registry.get_permission("file_getTaskOutputs") == RPCPermission.USER
    assert service.registry.get_permission("file_downloadTaskOutput") == RPCPermission.USER
    assert service.registry.get_permission("file_cancelUpload") == RPCPermission.USER


def test_e2e_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("e2e_createSession") == RPCPermission.USER
    assert service.registry.get_permission("e2e_handshake") == RPCPermission.USER
    assert service.registry.get_permission("e2e_uploadChunk") == RPCPermission.USER
    assert service.registry.get_permission("e2e_downloadChunk") == RPCPermission.USER
    assert service.registry.get_permission("e2e_closeSession") == RPCPermission.USER


def test_p2p_tunnel_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("p2pTunnel_registerEndpoint") == RPCPermission.USER
    assert service.registry.get_permission("p2pTunnel_requestTicket") == RPCPermission.USER
    assert service.registry.get_permission("p2pTunnel_getStatus") == RPCPermission.USER
    assert service.registry.get_permission("p2pTunnel_startServer") == RPCPermission.USER
    assert service.registry.get_permission("p2pTunnel_getMinerP2PInfo") == RPCPermission.PUBLIC


def test_pricing_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("pricing_getBaseRates") == RPCPermission.PUBLIC
    assert service.registry.get_permission("pricing_getRealTimePrice") == RPCPermission.PUBLIC
    assert service.registry.get_permission("pricing_calculatePrice") == RPCPermission.PUBLIC
    assert service.registry.get_permission("pricing_getMarketState") == RPCPermission.PUBLIC
    assert service.registry.get_permission("pricing_getStrategies") == RPCPermission.PUBLIC
    assert service.registry.get_permission("pricing_getTimeSlotSchedule") == RPCPermission.PUBLIC
    assert service.registry.get_permission("pricing_getPriceForecast") == RPCPermission.PUBLIC


def test_budget_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("budget_deposit") == RPCPermission.USER
    assert service.registry.get_permission("budget_getBalance") == RPCPermission.USER
    assert service.registry.get_permission("budget_lockForTask") == RPCPermission.USER
    assert service.registry.get_permission("budget_getLockInfo") == RPCPermission.USER


def test_settlement_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("settlement_settleTask") == RPCPermission.MINER
    assert service.registry.get_permission("settlement_getRecord") == RPCPermission.USER
    assert service.registry.get_permission("settlement_getDetailedBill") == RPCPermission.USER
    assert service.registry.get_permission("settlement_getMinerEarnings") == RPCPermission.MINER


def test_market_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("market_getDashboard") == RPCPermission.PUBLIC
    assert service.registry.get_permission("market_getSupplyDemandCurve") == RPCPermission.PUBLIC
    assert service.registry.get_permission("market_getQueueStatus") == RPCPermission.PUBLIC
    assert service.registry.get_permission("market_updateSupplyDemand") == RPCPermission.MINER
    assert service.registry.get_permission("market_getQuotes") == RPCPermission.PUBLIC
    assert service.registry.get_permission("market_acceptQuote") == RPCPermission.USER


def test_queue_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("queue_enqueue") == RPCPermission.USER
    assert service.registry.get_permission("queue_getPosition") == RPCPermission.USER
    assert service.registry.get_permission("queue_getEstimatedWaitTime") == RPCPermission.USER
    assert service.registry.get_permission("queue_getStats") == RPCPermission.PUBLIC


def test_blockchain_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("blockchain_getHeight") == RPCPermission.PUBLIC
    assert service.registry.get_permission("blockchain_getBlock") == RPCPermission.PUBLIC
    assert service.registry.get_permission("blockchain_getLatestBlocks") == RPCPermission.PUBLIC


def test_order_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("order_getList") == RPCPermission.PUBLIC
    assert service.registry.get_permission("order_getDetail") == RPCPermission.PUBLIC


def test_staking_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("staking_getRecords") == RPCPermission.PUBLIC
    assert service.registry.get_permission("staking_stake") == RPCPermission.USER
    assert service.registry.get_permission("staking_unstake") == RPCPermission.USER


def test_rpc_meta_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("rpc_listMethods") == RPCPermission.PUBLIC


def test_tee_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("tee_registerNode") == RPCPermission.MINER
    assert service.registry.get_permission("tee_submitAttestation") == RPCPermission.MINER
    assert service.registry.get_permission("tee_getNodeInfo") == RPCPermission.PUBLIC
    assert service.registry.get_permission("tee_listNodes") == RPCPermission.PUBLIC
    assert service.registry.get_permission("tee_createConfidentialTask") == RPCPermission.USER
    assert service.registry.get_permission("tee_deployConfidentialModel") == RPCPermission.USER
    assert service.registry.get_permission("tee_getTaskResult") == RPCPermission.USER
    assert service.registry.get_permission("tee_getPricing") == RPCPermission.PUBLIC
    assert service.registry.get_permission("tee_getRolloutAudit") == RPCPermission.ADMIN
    assert service.registry.get_permission("tee_getKmsAudit") == RPCPermission.ADMIN


def test_orderbook_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("orderbook_submitAsk") == RPCPermission.MINER
    assert service.registry.get_permission("orderbook_submitBid") == RPCPermission.USER
    assert service.registry.get_permission("orderbook_cancelOrder") == RPCPermission.USER
    assert service.registry.get_permission("orderbook_getOrderBook") == RPCPermission.PUBLIC
    assert service.registry.get_permission("orderbook_getMarketPrice") == RPCPermission.PUBLIC
    assert service.registry.get_permission("orderbook_getMyOrders") == RPCPermission.USER
    assert service.registry.get_permission("orderbook_getMatches") == RPCPermission.PUBLIC


def test_futures_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("futures_createContract") == RPCPermission.USER
    assert service.registry.get_permission("futures_depositMargin") == RPCPermission.USER
    assert service.registry.get_permission("futures_getContract") == RPCPermission.PUBLIC
    assert service.registry.get_permission("futures_listContracts") == RPCPermission.PUBLIC
    assert service.registry.get_permission("futures_cancelContract") == RPCPermission.USER
    assert service.registry.get_permission("futures_settleContract") == RPCPermission.USER
    assert service.registry.get_permission("futures_getPricingCurve") == RPCPermission.PUBLIC


def test_billing_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("billing_recordUsage") == RPCPermission.MINER
    assert service.registry.get_permission("billing_calculateCost") == RPCPermission.PUBLIC
    assert service.registry.get_permission("billing_getDetailedBilling") == RPCPermission.USER
    assert service.registry.get_permission("billing_getRates") == RPCPermission.PUBLIC
    assert service.registry.get_permission("billing_estimateTask") == RPCPermission.PUBLIC


def test_data_lifecycle_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("dataLifecycle_registerAsset") == RPCPermission.USER
    assert service.registry.get_permission("dataLifecycle_requestDestruction") == RPCPermission.USER
    assert service.registry.get_permission("dataLifecycle_getDestructionProof") == RPCPermission.USER
    assert service.registry.get_permission("dataLifecycle_listAssets") == RPCPermission.USER


def test_ephemeral_key_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("ephemeralKey_createSession") == RPCPermission.USER
    assert service.registry.get_permission("ephemeralKey_getSessionKey") == RPCPermission.USER
    assert service.registry.get_permission("ephemeralKey_rotateKey") == RPCPermission.USER


def test_p2p_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("p2p_setupConnection") == RPCPermission.USER
    assert service.registry.get_permission("p2p_createOffer") == RPCPermission.USER
    assert service.registry.get_permission("p2p_createAnswer") == RPCPermission.USER
    assert service.registry.get_permission("p2p_getConnectionStatus") == RPCPermission.USER
    assert service.registry.get_permission("p2p_listConnections") == RPCPermission.USER
    assert service.registry.get_permission("p2p_closeConnection") == RPCPermission.USER
    assert service.registry.get_permission("p2p_getNATInfo") == RPCPermission.PUBLIC


def test_did_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("did_create") == RPCPermission.USER
    assert service.registry.get_permission("did_resolve") == RPCPermission.PUBLIC
    assert service.registry.get_permission("did_bindWallet") == RPCPermission.USER
    assert service.registry.get_permission("did_issueCredential") == RPCPermission.ADMIN
    assert service.registry.get_permission("did_verifyCredential") == RPCPermission.PUBLIC
    assert service.registry.get_permission("did_getReputation") == RPCPermission.PUBLIC
    assert service.registry.get_permission("did_getReputationTier") == RPCPermission.PUBLIC
    assert service.registry.get_permission("did_checkSybilRisk") == RPCPermission.PUBLIC


def test_mq_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("mq_publish") == RPCPermission.USER
    assert service.registry.get_permission("mq_subscribe") == RPCPermission.USER
    assert service.registry.get_permission("mq_getQueueStats") == RPCPermission.PUBLIC
    assert service.registry.get_permission("mq_emitEvent") == RPCPermission.USER


def test_redundancy_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("redundancy_storeData") == RPCPermission.USER
    assert service.registry.get_permission("redundancy_retrieveData") == RPCPermission.USER
    assert service.registry.get_permission("redundancy_createBackup") == RPCPermission.ADMIN
    assert service.registry.get_permission("redundancy_getStats") == RPCPermission.PUBLIC


def test_load_test_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("loadTest_runScenario") == RPCPermission.ADMIN
    assert service.registry.get_permission("loadTest_getResults") == RPCPermission.ADMIN
    assert service.registry.get_permission("loadTest_getMetrics") == RPCPermission.PUBLIC


def test_zk_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("zk_generateProof") == RPCPermission.MINER
    assert service.registry.get_permission("zk_verifyProof") == RPCPermission.PUBLIC
    assert service.registry.get_permission("zk_getProofStats") == RPCPermission.PUBLIC


def test_security_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("security_checkRequest") == RPCPermission.PUBLIC
    assert service.registry.get_permission("security_reportThreat") == RPCPermission.USER
    assert service.registry.get_permission("security_getStats") == RPCPermission.PUBLIC
    assert service.registry.get_permission("security_checkSybil") == RPCPermission.PUBLIC


def test_audit_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("audit_submitContract") == RPCPermission.USER
    assert service.registry.get_permission("audit_getReport") == RPCPermission.USER
    assert service.registry.get_permission("audit_autoSettle") == RPCPermission.MINER
    assert service.registry.get_permission("audit_getSettlementHistory") == RPCPermission.USER


def test_revenue_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("revenue_recordEarning") == RPCPermission.MINER
    assert service.registry.get_permission("revenue_getMinerStats") == RPCPermission.USER
    assert service.registry.get_permission("revenue_getLeaderboard") == RPCPermission.PUBLIC
    assert service.registry.get_permission("revenue_getForecast") == RPCPermission.USER


def test_monitor_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("monitor_getHealth") == RPCPermission.PUBLIC
    assert service.registry.get_permission("monitor_getDashboard") == RPCPermission.PUBLIC
    assert service.registry.get_permission("monitor_getAlerts") == RPCPermission.ADMIN
    assert service.registry.get_permission("monitor_recordMetric") == RPCPermission.MINER


def test_sdk_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("sdk_getOpenAPISpec") == RPCPermission.PUBLIC
    assert service.registry.get_permission("sdk_generateSDK") == RPCPermission.PUBLIC
    assert service.registry.get_permission("sdk_getEndpoints") == RPCPermission.PUBLIC
    assert service.registry.get_permission("sdk_getExamples") == RPCPermission.PUBLIC


def test_p2p_task_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("p2pTask_create") == RPCPermission.USER
    assert service.registry.get_permission("p2pTask_distribute") == RPCPermission.USER
    assert service.registry.get_permission("p2pTask_getStatus") == RPCPermission.PUBLIC
    assert service.registry.get_permission("p2pTask_getList") == RPCPermission.PUBLIC
    assert service.registry.get_permission("p2pTask_getStats") == RPCPermission.PUBLIC
    assert service.registry.get_permission("p2pTask_cancel") == RPCPermission.USER
    assert service.registry.get_permission("p2pTask_registerMiner") == RPCPermission.USER
    assert service.registry.get_permission("p2pTask_getMiners") == RPCPermission.PUBLIC
    assert service.registry.get_permission("p2pTask_getResult") == RPCPermission.USER


def test_cluster_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("cluster_hardware") == RPCPermission.PUBLIC
    assert service.registry.get_permission("cluster_execute") == RPCPermission.PUBLIC


def test_frontend_alias_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("status") == RPCPermission.PUBLIC
    assert service.registry.get_permission("miner_getSectorList") == RPCPermission.PUBLIC
    assert service.registry.get_permission("miner_getGpuList") == RPCPermission.PUBLIC
    assert service.registry.get_permission("miner_getEarnings") == RPCPermission.PUBLIC
    assert service.registry.get_permission("market_getComputeOrders") == RPCPermission.PUBLIC
    assert service.registry.get_permission("market_createOrder") == RPCPermission.USER
    assert service.registry.get_permission("blockchain_getBlocks") == RPCPermission.PUBLIC
    assert service.registry.get_permission("blockchain_getTransaction") == RPCPermission.PUBLIC
    assert service.registry.get_permission("network_getStatus") == RPCPermission.PUBLIC
    assert service.registry.get_permission("network_getPeerList") == RPCPermission.PUBLIC
    assert service.registry.get_permission("network_getRecentTransactions") == RPCPermission.PUBLIC
    assert service.registry.get_permission("billing_getDetailed") == RPCPermission.USER
    assert service.registry.get_permission("dashboard_getSummary") == RPCPermission.PUBLIC
    assert service.registry.get_permission("dashboard_getSectorDistribution") == RPCPermission.PUBLIC
    assert service.registry.get_permission("exchange_getOrderBook") == RPCPermission.PUBLIC
    assert service.registry.get_permission("exchange_getMarketInfo") == RPCPermission.PUBLIC
    assert service.registry.get_permission("exchange_createOrder") == RPCPermission.USER
    assert service.registry.get_permission("p2p_getStatus") == RPCPermission.PUBLIC
    assert service.registry.get_permission("dataLifecycle_getStatus") == RPCPermission.PUBLIC


def test_governance_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("governance_vote") == RPCPermission.USER
    assert service.registry.get_permission("governance_getProposals") == RPCPermission.PUBLIC
    assert service.registry.get_permission("governance_getProposal") == RPCPermission.PUBLIC
    assert service.registry.get_permission("governance_createProposal") == RPCPermission.USER


def test_contrib_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("contrib_createProposal") == RPCPermission.USER
    assert service.registry.get_permission("contrib_vote") == RPCPermission.USER
    assert service.registry.get_permission("contrib_getProposals") == RPCPermission.PUBLIC
    assert service.registry.get_permission("contrib_getProposal") == RPCPermission.PUBLIC
    assert service.registry.get_permission("contrib_getVoterPower") == RPCPermission.PUBLIC
    assert service.registry.get_permission("contrib_simulateVote") == RPCPermission.PUBLIC
    assert service.registry.get_permission("contrib_stake") == RPCPermission.USER
    assert service.registry.get_permission("contrib_unstake") == RPCPermission.USER
    assert service.registry.get_permission("contrib_finalizeProposal") == RPCPermission.USER
    assert service.registry.get_permission("contrib_executeProposal") == RPCPermission.ADMIN
    assert service.registry.get_permission("contrib_getStats") == RPCPermission.PUBLIC
    assert service.registry.get_permission("contrib_checkProposerEligibility") == RPCPermission.PUBLIC
    assert service.registry.get_permission("contrib_getProposalTimeRemaining") == RPCPermission.PUBLIC
    assert service.registry.get_permission("contrib_checkExpiredProposals") == RPCPermission.ADMIN
    assert service.registry.get_permission("contrib_getPassRequirements") == RPCPermission.PUBLIC


def test_dashboard_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("dashboard_getStats") == RPCPermission.PUBLIC
    assert service.registry.get_permission("dashboard_getRecentTasks") == RPCPermission.PUBLIC
    assert service.registry.get_permission("dashboard_getRecentProposals") == RPCPermission.PUBLIC
    assert service.registry.get_permission("dashboard_getBlockChart") == RPCPermission.PUBLIC
    assert service.registry.get_permission("dashboard_getRewardTrend") == RPCPermission.PUBLIC


def test_miner_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("miner_getList") == RPCPermission.PUBLIC
    assert service.registry.get_permission("miner_getInfo") == RPCPermission.PUBLIC
    assert service.registry.get_permission("miner_getBehaviorReport") == RPCPermission.PUBLIC
    assert service.registry.get_permission("miner_register") == RPCPermission.USER
    assert service.registry.get_permission("miner_updateProfile") == RPCPermission.USER


def test_stats_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("stats_getNetwork") == RPCPermission.PUBLIC
    assert service.registry.get_permission("stats_getBlocks") == RPCPermission.PUBLIC
    assert service.registry.get_permission("stats_getTasks") == RPCPermission.PUBLIC


def test_tx_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("tx_send") == RPCPermission.USER
    assert service.registry.get_permission("tx_get") == RPCPermission.PUBLIC
    assert service.registry.get_permission("tx_getByAddress") == RPCPermission.PUBLIC


def test_mempool_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("mempool_getInfo") == RPCPermission.PUBLIC
    assert service.registry.get_permission("mempool_getPending") == RPCPermission.PUBLIC


def test_block_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("block_getLatest") == RPCPermission.PUBLIC
    assert service.registry.get_permission("block_getByHeight") == RPCPermission.PUBLIC
    assert service.registry.get_permission("block_getByHash") == RPCPermission.PUBLIC


def test_chain_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("chain_getHeight") == RPCPermission.PUBLIC
    assert service.registry.get_permission("chain_getInfo") == RPCPermission.PUBLIC
    assert service.registry.get_permission("chain_updateMechanismStrategy") == RPCPermission.ADMIN
    assert service.registry.get_permission("sbox_getEncryptionPolicy") == RPCPermission.PUBLIC
    assert service.registry.get_permission("sbox_setEncryptionPolicy") == RPCPermission.ADMIN
    assert service.registry.get_permission("sbox_getDowngradeAudit") == RPCPermission.PUBLIC


def test_mining_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("mining_getStatus") == RPCPermission.PUBLIC
    assert service.registry.get_permission("mining_start") == RPCPermission.USER
    assert service.registry.get_permission("mining_stop") == RPCPermission.USER
    assert service.registry.get_permission("mining_getRewards") == RPCPermission.PUBLIC
    assert service.registry.get_permission("mining_setMode") == RPCPermission.USER
    assert service.registry.get_permission("mining_getScore") == RPCPermission.PUBLIC


def test_sector_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("sector_getExchangeRates") == RPCPermission.PUBLIC
    assert service.registry.get_permission("sector_requestExchange") == RPCPermission.USER
    assert service.registry.get_permission("sector_getExchangeHistory") == RPCPermission.PUBLIC
    assert service.registry.get_permission("sector_cancelExchange") == RPCPermission.USER


def test_privacy_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("privacy_getStatus") == RPCPermission.PUBLIC
    assert service.registry.get_permission("privacy_rotateAddress") == RPCPermission.USER


def test_node_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("node_getInfo") == RPCPermission.PUBLIC
    assert service.registry.get_permission("node_getPeers") == RPCPermission.PUBLIC
    assert service.registry.get_permission("node_isSyncing") == RPCPermission.PUBLIC


def test_witness_domain_permissions_after_handler_migration():
    service = NodeRPCService()
    assert service.registry.get_permission("witness_request") == RPCPermission.MINER
    assert service.registry.get_permission("witness_getStatus") == RPCPermission.PUBLIC
