"""
TRADEKING — Engine Registry
All 8 analysis engines
"""
from engines.engine_01_oi_state import OIStateEngine
from engines.engine_02_unusual_flow import UnusualFlowEngine
from engines.engine_03_futures_basis import FuturesBasisEngine
from engines.engine_04_iv_skew import IVSkewEngine
from engines.engine_05_liquidity_pool import LiquidityPoolEngine
from engines.engine_06_microstructure import MicrostructureEngine
from engines.engine_07_macro import MacroEngine
from engines.engine_08_trap import TrapFingerprintEngine

ENGINE_REGISTRY = {
    "engine_01_oi_state": OIStateEngine,
    "engine_02_unusual_flow": UnusualFlowEngine,
    "engine_03_futures_basis": FuturesBasisEngine,
    "engine_04_iv_skew": IVSkewEngine,
    "engine_05_liquidity_pool": LiquidityPoolEngine,
    "engine_06_microstructure": MicrostructureEngine,
    "engine_07_macro": MacroEngine,
    "engine_08_trap": TrapFingerprintEngine,
}

__all__ = [
    "ENGINE_REGISTRY",
    "OIStateEngine",
    "UnusualFlowEngine",
    "FuturesBasisEngine",
    "IVSkewEngine",
    "LiquidityPoolEngine",
    "MicrostructureEngine",
    "MacroEngine",
    "TrapFingerprintEngine",
]
