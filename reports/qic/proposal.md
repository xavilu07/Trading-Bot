# QIC Proposal

- id: cio_805ad892d491
- title: CIO proposal: exclude liquidity_distance_bucket=2-4atr
- hypothesis: Strategy Simulator indicates this single candidate has the strongest current evidence.
- expected_pf: 2.6415
- expected_total_r: 7.8114
- trades_lost: 29
- confidence: LOW
- risk_level: HIGH
- evidence: 20
- agent_votes: [{"agent": "research_director", "confidence": "LOW", "risk_level": "LOW", "stage": "research"}, {"agent": "strategy_director", "confidence": "LOW", "risk_level": "MEDIUM", "stage": "strategy"}, {"agent": "risk_director", "confidence": "HIGH", "risk_level": "HIGH", "stage": "risk"}, {"agent": "simulation_director", "confidence": "LOW", "risk_level": "LOW", "stage": "simulation"}, {"agent": "research_director", "confidence": "LOW", "risk_level": "HIGH", "stage": "research_response"}]
- action: PROPOSE_IMPLEMENTATION
- baseline_trades: 49
- trade_reduction_pct: 59.1837
- risk_objections: ["high_trade_reduction"]
- status: pending
- context: {"baseline_trades": 49, "complexity": 1, "composite_score": 39.4162, "condition_details": [{"evidence": 29, "feature": "liquidity_distance_bucket", "label": "exclude liquidity_distance_bucket=2-4atr", "operator": "==", "value": "2-4atr"}], "conditions": ["exclude liquidity_distance_bucket=2-4atr"], "source": "single_filter", "trade_reduction_pct": 59.1837}
- rationale: Expected PF 2.6415 and TotalR 7.8114 after simulation.
- created_at: 2026-07-06T14:53:22.117354+00:00
