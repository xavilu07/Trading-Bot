# QIC Proposal

- id: cio_805ad892d491
- title: CIO proposal: exclude liquidity_distance_bucket=2-4atr
- hypothesis: Strategy Simulator indicates this single candidate has the strongest current evidence.
- expected_pf: 2.6415
- expected_total_r: 7.8114
- trades_lost: 29
- confidence: LOW
- risk_level: LOW
- evidence: 20
- agent_votes: [{"agent": "research_director", "confidence": "LOW", "risk_level": "LOW", "stage": "research"}, {"agent": "strategy_director", "confidence": "LOW", "risk_level": "MEDIUM", "stage": "strategy"}, {"agent": "risk_director", "confidence": "MEDIUM", "risk_level": "LOW", "stage": "risk"}, {"agent": "simulation_director", "confidence": "LOW", "risk_level": "LOW", "stage": "simulation"}, {"agent": "research_director", "confidence": "LOW", "risk_level": "LOW", "stage": "research_response"}]
- status: pending
- context: {"condition_details": [{"evidence": 29, "feature": "liquidity_distance_bucket", "label": "exclude liquidity_distance_bucket=2-4atr", "operator": "==", "value": "2-4atr"}], "conditions": ["exclude liquidity_distance_bucket=2-4atr"]}
- rationale: Expected PF 2.6415 and TotalR 7.8114 after simulation.
- created_at: 2026-07-04T16:18:29.313433+00:00
