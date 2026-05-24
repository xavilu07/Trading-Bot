from __future__ import annotations

from trading_signals.analysis.market_regime import detect_session, detect_trade_location
from trading_signals.app.settings import Settings
from trading_signals.application.dto.analysis_result import AnalysisResult
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.domain.value_objects.enums import SignalDecision


class LiquiditySweepMTFV1:
    strategy_id = "liquidity_sweep_mtf"
    strategy_version = "v1"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(self, analysis: AnalysisResult, evaluation_id: str, created_at: str) -> StrategyEvaluation:
        entry = analysis.entry_snapshot
        higher = analysis.higher_snapshot
        passed: list[str] = []
        failed: list[str] = []
        penalties: list[str] = []
        score = float(entry.setup_score)
        volume_ratio = float(entry.metadata.get("volume_ratio_vs_average_20", 0.0))
        rsi = float(entry.metadata.get("rsi", 50.0))
        break_of_structure = str(entry.metadata.get("break_of_structure", "none"))
        nearest_distance = float(entry.metadata.get("nearest_distance_to_liquidity_atr", entry.distance_to_liquidity_atr))
        secondary_score_threshold = self.settings.setup_score_threshold + 15
        session = detect_session(entry.timestamp)
        effective_setup_score_threshold = self.settings.setup_score_threshold + (10 if session == "ASIA" else 0)
        effective_secondary_score_threshold = secondary_score_threshold + (10 if session == "ASIA" else 0)
        soft_distance_limit = self.settings.max_distance_to_liquidity_atr * 2
        directional_distance_check = "passed"
        nearest_liquidity_check = "passed" if nearest_distance <= self.settings.max_distance_to_liquidity_atr else "extreme"
        relaxed_gates_enabled = bool(getattr(self.settings, "relaxed_strategy_gates_enabled", False))
        secondary_direction = "none"
        if break_of_structure == "bullish_bos":
            secondary_direction = SignalDecision.LONG.value
        elif break_of_structure == "bearish_bos":
            secondary_direction = SignalDecision.SHORT.value
        trace = [
            f"trend_1h={entry.trend}",
            f"trend_4h={higher.trend}",
            f"market_structure={entry.market_structure}",
            f"liquidity_sweep={entry.liquidity_sweep}",
            f"break_of_structure={break_of_structure}",
            f"session={session}",
            f"relaxed_strategy_gates_enabled={str(relaxed_gates_enabled).lower()}",
            f"base_setup_score={entry.setup_score}",
            f"min_setup_score_required={effective_setup_score_threshold}",
            f"secondary_setup_score_required={effective_secondary_score_threshold}",
        ]

        def hard_check(condition: bool, passed_name: str, failed_name: str) -> None:
            if condition:
                passed.append(passed_name)
            else:
                failed.append(failed_name)

        def penalize(condition: bool, passed_name: str, failed_name: str, points: float) -> None:
            nonlocal score
            if condition:
                passed.append(passed_name)
            else:
                failed.append(failed_name)
                penalties.append(f"{failed_name}:{points}")
                score -= points

        hard_check((entry.atr / entry.close) >= self.settings.atr_min_threshold, "volatility", "volatility_failed")
        hard_check(entry.body_ratio >= self.settings.min_body_ratio, "candle_confirmation", "body_ratio_below_threshold")

        penalize(entry.trend == higher.trend, "timeframe_alignment", "timeframe_alignment_penalty", 10)
        atr_ratio = entry.atr / entry.close if entry.close else 0.0
        range_quality_checks = [
            volume_ratio > 1.2,
            entry.body_ratio > 0.5,
            atr_ratio > self.settings.atr_min_threshold,
        ]
        range_quality_candidate = entry.market_structure == "range" and entry.setup_score >= 75 and sum(range_quality_checks) >= 2
        range_quality_allowed = relaxed_gates_enabled and range_quality_candidate
        if entry.market_structure == "range":
            failed.append("market_structure_range_penalty")
            penalties.append("market_structure_range_penalty:10")
            score -= 10
            if range_quality_allowed:
                passed.append("market_structure_range_allowed")
        else:
            passed.append("market_structure")

        if entry.distance_to_liquidity_atr <= self.settings.max_distance_to_liquidity_atr:
            passed.append("distance_to_liquidity")
        elif entry.distance_to_liquidity_atr <= soft_distance_limit:
            directional_distance_check = "penalty"
            failed.append("distance_to_liquidity_penalty")
            penalties.append("distance_to_liquidity_penalty:10")
            score -= 10
        else:
            directional_distance_check = "extreme"
            failed.append("distance_to_liquidity_extreme")
            penalties.append("distance_to_liquidity_extreme_penalty:20")
            score -= 20

        if nearest_distance > self.settings.max_distance_to_liquidity_atr:
            failed.append("nearest_liquidity_extreme")

        trade_location = str(entry.metadata.get("trade_location", detect_trade_location(entry)))
        rr_value = entry.metadata.get("risk_reward")
        if rr_value is None:
            rr_value = entry.metadata.get("risk_reward_tp1", entry.metadata.get("rr"))
        rr_valid = False
        if rr_value is not None:
            try:
                rr_valid = float(rr_value) >= self.settings.min_rr
            except (TypeError, ValueError):
                rr_valid = False
        long_counter_htf_checks = [
            entry.liquidity_sweep == "bullish_sweep",
            break_of_structure == "bullish_bos",
            volume_ratio > 1.2,
            entry.body_ratio > 0.5,
            trade_location in {"discount_zone", "near_support"},
            directional_distance_check == "passed",
            rr_valid,
        ]
        long_counter_htf_checks_count = sum(long_counter_htf_checks)
        long_counter_htf_allowed = (
            relaxed_gates_enabled
            and
            entry.trend == "bullish"
            and higher.trend == "bearish"
            and long_counter_htf_checks_count >= 3
        )

        secondary_trend_aligned = entry.trend == higher.trend and entry.trend in {"bullish", "bearish"}
        secondary_volume_favorable = volume_ratio >= 1.2
        secondary_rsi_aligned = (
            (secondary_direction == SignalDecision.LONG.value and rsi >= 50)
            or (secondary_direction == SignalDecision.SHORT.value and rsi <= 50)
        )
        secondary_nearest_liquidity_valid = nearest_distance <= self.settings.max_distance_to_liquidity_atr
        secondary_has_structure = entry.market_structure != "range" or break_of_structure in {"bullish_bos", "bearish_bos"}
        secondary_core_requirements_met = (
            entry.liquidity_sweep == "none"
            and secondary_trend_aligned
            and break_of_structure in {"bullish_bos", "bearish_bos"}
            and secondary_volume_favorable
            and secondary_rsi_aligned
            and secondary_nearest_liquidity_valid
            and secondary_has_structure
        )
        secondary_confluence_bonus = 0.0
        if entry.liquidity_sweep == "none" and secondary_trend_aligned:
            if break_of_structure in {"bullish_bos", "bearish_bos"}:
                secondary_confluence_bonus += 10
            if secondary_nearest_liquidity_valid:
                secondary_confluence_bonus += 15
            if secondary_volume_favorable:
                secondary_confluence_bonus += 5
            if secondary_rsi_aligned:
                secondary_confluence_bonus += 5
        if secondary_confluence_bonus:
            score += secondary_confluence_bonus
            penalties.append(f"secondary_confluence_bonus:+{secondary_confluence_bonus:g}")
        secondary_requirements_met = secondary_core_requirements_met and session != "ASIA" and score >= effective_secondary_score_threshold
        if entry.liquidity_sweep == "none" and not secondary_requirements_met:
            failed.append("secondary_setup_requirements_failed")
            penalties.append("secondary_setup_requirements_failed:20")
            score -= 20
            if session == "ASIA":
                failed.append("asia_secondary_setup_blocked")

        score = round(max(0.0, min(score, 100.0)), 2)
        if score >= effective_setup_score_threshold:
            passed.append("quality_score")
        else:
            failed.append("quality_score_failed")

        decision = SignalDecision.NO_TRADE.value
        confidence = min(0.95, max(0.1, score / 100))
        has_hard_failures = any(
            item in failed
            for item in {
                "volatility_failed",
                "body_ratio_below_threshold",
                "quality_score_failed",
            }
        )
        if not relaxed_gates_enabled and "secondary_setup_requirements_failed" in failed:
            has_hard_failures = True
        if not has_hard_failures:
            range_long_allowed = (
                entry.market_structure == "range"
                and entry.liquidity_sweep == "bullish_sweep"
                and range_quality_allowed
            )
            range_short_allowed = (
                entry.market_structure == "range"
                and entry.liquidity_sweep == "bearish_sweep"
                and range_quality_allowed
            )
            if (
                entry.trend == "bullish"
                and entry.liquidity_sweep == "bullish_sweep"
                and entry.market_structure in {"bullish", "range"}
                and (higher.trend != "bearish" or long_counter_htf_allowed)
                and "distance_to_liquidity_extreme" not in failed
                and (entry.market_structure == "bullish" or range_long_allowed)
                and (session != "ASIA" or score >= 85)
            ):
                decision = SignalDecision.LONG.value
                passed.append("primary_sweep_setup")
                passed.append("directional_confluence")
            elif (
                entry.trend == "bearish"
                and entry.liquidity_sweep == "bearish_sweep"
                and entry.market_structure in {"bearish", "range"}
                and higher.trend != "bullish"
                and "distance_to_liquidity_extreme" not in failed
                and (entry.market_structure == "bearish" or range_short_allowed)
                and (session != "ASIA" or score >= 85)
            ):
                decision = SignalDecision.SHORT.value
                passed.append("primary_sweep_setup")
                passed.append("directional_confluence")
            elif (
                session != "ASIA"
                and
                entry.trend == higher.trend == "bullish"
                and entry.liquidity_sweep == "none"
                and break_of_structure == "bullish_bos"
                and secondary_volume_favorable
                and secondary_rsi_aligned
                and secondary_nearest_liquidity_valid
                and secondary_has_structure
                and score >= effective_secondary_score_threshold
            ):
                decision = SignalDecision.LONG.value
                passed.extend([
                    "secondary_setup",
                    "secondary_trend_alignment",
                    "secondary_volume_confirmation",
                    "secondary_break_of_structure",
                    "secondary_rsi_alignment",
                    "secondary_nearest_liquidity",
                ])
            elif (
                session != "ASIA"
                and
                entry.trend == higher.trend == "bearish"
                and entry.liquidity_sweep == "none"
                and break_of_structure == "bearish_bos"
                and secondary_volume_favorable
                and secondary_rsi_aligned
                and secondary_nearest_liquidity_valid
                and secondary_has_structure
                and score >= effective_secondary_score_threshold
            ):
                decision = SignalDecision.SHORT.value
                passed.extend([
                    "secondary_setup",
                    "secondary_trend_alignment",
                    "secondary_volume_confirmation",
                    "secondary_break_of_structure",
                    "secondary_rsi_alignment",
                    "secondary_nearest_liquidity",
                ])
            else:
                fallback_direction = SignalDecision.NO_TRADE.value
                if entry.liquidity_sweep == "bullish_sweep" or secondary_direction == SignalDecision.LONG.value:
                    fallback_direction = SignalDecision.LONG.value
                elif entry.liquidity_sweep == "bearish_sweep" or secondary_direction == SignalDecision.SHORT.value:
                    fallback_direction = SignalDecision.SHORT.value

                if entry.trend == "bullish" and higher.trend == "bearish" and not long_counter_htf_allowed:
                    failed.append("higher_timeframe_contradicts_long")
                elif (
                    fallback_direction == SignalDecision.LONG.value
                    and long_counter_htf_allowed
                    and score >= 80
                    and "distance_to_liquidity_extreme" not in failed
                    and session != "ASIA"
                ):
                    decision = SignalDecision.LONG.value
                    passed.append("directional_confluence_soft_allowed")
                    passed.append("long_counter_htf_reversal")
                elif entry.trend == "bearish" and higher.trend == "bullish":
                    failed.append("higher_timeframe_contradicts_short")
                else:
                    htf_contradicts_fallback = (
                        (fallback_direction == SignalDecision.LONG.value and higher.trend == "bearish")
                        or (fallback_direction == SignalDecision.SHORT.value and higher.trend == "bullish")
                    )
                    if (
                        fallback_direction != SignalDecision.NO_TRADE.value
                        and score >= 80
                        and not htf_contradicts_fallback
                        and "distance_to_liquidity_extreme" not in failed
                        and session != "ASIA"
                        and relaxed_gates_enabled
                    ):
                        decision = fallback_direction
                        passed.append("directional_confluence_soft_allowed")
                    else:
                        failed.append("directional_confluence_failed")

        trace.extend(
            [
                f"final_setup_score={score}",
                f"penalties={','.join(penalties) if penalties else 'none'}",
                f"volume_ratio={volume_ratio}",
                f"body_ratio={entry.body_ratio}",
                f"atr_ratio={atr_ratio}",
                f"range_quality_checks={sum(range_quality_checks)}",
                f"range_quality_candidate={range_quality_candidate}",
                f"range_quality_allowed={range_quality_allowed}",
                f"asia_session_threshold_adjustment={10 if session == 'ASIA' else 0}",
                f"long_counter_htf_allowed={str(long_counter_htf_allowed).lower()}",
                f"long_counter_htf_checks={long_counter_htf_checks_count}",
                f"rsi={rsi}",
                f"secondary_confluence_bonus={secondary_confluence_bonus:g}",
                f"directional_distance_check={directional_distance_check}",
                f"nearest_liquidity_check={nearest_liquidity_check}",
                f"liquidity_rule_applied={'nearest_secondary_continuation' if 'secondary_setup' in passed else 'directional_sniper'}",
                f"setup_type={'SECONDARY_SIGNAL' if 'secondary_setup' in passed else 'PRIMARY_SWEEP_SIGNAL' if 'primary_sweep_setup' in passed else 'NO_SIGNAL'}",
            ]
        )

        return StrategyEvaluation(
            id=evaluation_id,
            scan_run_id=entry.scan_run_id,
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            symbol=entry.symbol,
            entry_timeframe=analysis.entry_timeframe,
            higher_timeframe=analysis.higher_timeframe,
            entry_snapshot_id=entry.id,
            higher_snapshot_id=higher.id,
            decision=decision,
            decision_trace=trace,
            rejection_reasons=failed.copy(),
            passed_filters=passed,
            failed_filters=failed,
            setup_score=score,
            confidence=round(confidence, 2),
            created_at=created_at,
        )
