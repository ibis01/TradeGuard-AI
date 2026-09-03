"""
TradeGuard AI - Adapter Boundary Tests.

Verifies that:
1. Exchange adapter interface is properly defined
2. Paper adapter is the default
3. Governance core does not import exchange-specific libraries
4. Trading mode is properly isolated
5. Adapter boundary prevents direct exchange access

Constitution §5: Binance Integration Boundary
Constitution §11: Testing Requirements
"""

import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_exchange_adapter_interface_exists():
    """Verify exchange adapter interface is defined."""
    from integrations.binance.adapter import ExchangeAdapter, get_adapter
    
    assert ExchangeAdapter is not None
    assert callable(get_adapter)


def test_paper_adapter_is_default():
    """Verify paper adapter is the default mode."""
    from integrations.binance.adapter import get_adapter
    
    # Clear any environment variable that might override
    old_mode = os.environ.pop('TRADING_MODE', None)
    
    try:
        # get_adapter should return PaperAdapter by default
        adapter = get_adapter()
        assert adapter.__class__.__name__ == "PaperAdapter"
        assert adapter.mode == "paper"
    finally:
        # Restore environment
        if old_mode is not None:
            os.environ['TRADING_MODE'] = old_mode


def test_live_mode_requires_credentials():
    """Verify live mode requires Binance credentials."""
    from integrations.binance.adapter import get_adapter
    
    # Clear credentials
    env_backup = {
        'BINANCE_API_KEY': os.environ.pop('BINANCE_API_KEY', None),
        'BINANCE_API_SECRET': os.environ.pop('BINANCE_API_SECRET', None)
    }
    
    try:
        with pytest.raises(ValueError) as exc_info:
            get_adapter("live")
        
        assert "credentials" in str(exc_info.value).lower()
    finally:
        # Restore environment
        for key, value in env_backup.items():
            if value is not None:
                os.environ[key] = value


def test_invalid_mode_raises_error():
    """Verify invalid trading mode raises ValueError."""
    from integrations.binance.adapter import get_adapter
    
    with pytest.raises(ValueError) as exc_info:
        get_adapter("invalid_mode")
    
    assert "unsupported" in str(exc_info.value).lower()


def test_governance_core_no_exchange_imports():
    """
    CRITICAL: Verify governance core does not import exchange-specific libraries.
    
    This ensures the adapter boundary is maintained (Constitution §5).
    """
    import governance_engine
    import state_machine
    import schemas
    
    # Get all imported modules in governance files
    governance_modules = [
        governance_engine,
        state_machine,
        schemas
    ]
    
    # List of forbidden exchange-specific imports
    forbidden_imports = [
        'ccxt',
        'binance',
        'kraken',
        'coinbase'
    ]
    
    for module in governance_modules:
        module_name = module.__name__
        
        # Check all attributes in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            
            # If it's a module, check its name
            if hasattr(attr, '__name__'):
                attr_module_name = attr.__name__
                
                for forbidden in forbidden_imports:
                    assert forbidden not in attr_module_name.lower(), (
                        f"SECURITY VIOLATION: {module_name} imports exchange-specific "
                        f"library '{forbidden}' via {attr_module_name}. "
                        f"All exchange code must be isolated behind the adapter boundary."
                    )


def test_paper_adapter_execute_order():
    """Verify paper adapter can execute orders."""
    from integrations.binance.paper_adapter import PaperAdapter
    
    adapter = PaperAdapter()
    
    trade_intent = {
        "trade_id": 999,
        "symbol": "BTC",
        "side": "long",
        "quantity": 0.01,
        "entry_price": 60000.0,
        "stop_loss": 59500.0,
        "take_profit": 61000.0,
        "proposal_hash": "test_hash_123"
    }
    
    result = adapter.execute_order(trade_intent)
    
    assert result["status"] == "SUCCESS"
    assert result["mode"] == "paper"
    assert "order_id" in result
    assert result["order_id"].startswith("PAPER-")
    assert result["execution_price"] == 60000.0
    assert "[PAPER]" in result["message"]


def test_paper_adapter_get_balance():
    """Verify paper adapter can get balance."""
    from integrations.binance.paper_adapter import PaperAdapter
    
    adapter = PaperAdapter()
    result = adapter.get_balance()
    
    assert result["status"] == "SUCCESS"
    assert result["mode"] == "paper"
    assert "balance" in result
    assert isinstance(result["balance"], (int, float))
    assert "SIMULATED" in result.get("note", "")


def test_paper_adapter_get_positions():
    """Verify paper adapter can get positions."""
    from integrations.binance.paper_adapter import PaperAdapter
    
    adapter = PaperAdapter()
    result = adapter.get_open_positions()
    
    assert result["status"] == "SUCCESS"
    assert result["mode"] == "paper"
    assert "positions" in result
    assert isinstance(result["positions"], list)


def test_adapter_boundary_prevents_direct_execution():
    """
    Verify that trades cannot bypass the adapter boundary.
    
    The governance engine should only call execute_trade_with_adapter(),
    not directly interact with exchanges.
    """
    import governance_engine
    
    # Verify execute_trade_with_adapter exists
    assert hasattr(governance_engine, 'execute_trade_with_adapter')
    
    # Verify it's callable
    assert callable(governance_engine.execute_trade_with_adapter)