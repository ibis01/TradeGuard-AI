"""
TradeGuard AI - Binance Adapter Tests (Sprint 6).

Verifies that:
1. Binance adapter implements ExchangeAdapter interface
2. Testnet mode is safe by default
3. API failures fail-closed
4. Paper vs live separation is enforced
5. Credentials are not hardcoded
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_binance_adapter_implements_interface():
    """Verify BinanceAdapter implements ExchangeAdapter interface."""
    from binance_adapter import BinanceAdapter
    from exchange_adapter import ExchangeAdapter
    
    # Verify inheritance
    assert issubclass(BinanceAdapter, ExchangeAdapter)
    
    # Verify required methods exist
    assert hasattr(BinanceAdapter, 'execute_order')
    assert hasattr(BinanceAdapter, 'get_balance')
    assert hasattr(BinanceAdapter, 'get_open_positions')


def test_binance_adapter_requires_credentials():
    """Verify BinanceAdapter fails without API credentials."""
    from binance_adapter import BinanceAdapter
    
    # Clear environment variables
    env_backup = {
        'BINANCE_API_KEY': os.environ.pop('BINANCE_API_KEY', None),
        'BINANCE_API_SECRET': os.environ.pop('BINANCE_API_SECRET', None)
    }
    
    try:
        with patch('ccxt.binance'):
            with pytest.raises(ValueError) as exc_info:
                BinanceAdapter(use_testnet=True)
            
            assert "credentials not found" in str(exc_info.value).lower()
    
    finally:
        # Restore environment
        for key, value in env_backup.items():
            if value is not None:
                os.environ[key] = value


def test_binance_adapter_defaults_to_testnet():
    """Verify BinanceAdapter defaults to testnet for safety."""
    from binance_adapter import BinanceAdapter
    
    # Mock ccxt and environment
    with patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key', 'BINANCE_API_SECRET': 'test_secret'}):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            adapter = BinanceAdapter()  # No use_testnet argument
            
            # Verify testnet is enabled by default
            assert adapter.use_testnet is True
            
            # Verify sandbox mode was enabled
            # ccxt.binance is called with a dict as positional arg, not kwargs
            assert len(mock_binance.call_args_list) > 0
            first_call_args = mock_binance.call_args_list[0][0]  # Positional args
            assert len(first_call_args) > 0
            config_dict = first_call_args[0]  # First positional arg is the config dict
            assert config_dict['sandbox'] is True


def test_binance_adapter_execute_order_success():
    """Verify BinanceAdapter can execute orders successfully."""
    from binance_adapter import BinanceAdapter
    
    with patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key', 'BINANCE_API_SECRET': 'test_secret'}):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.create_market_order.return_value = {
                'id': '12345',
                'average': 60000.0,
                'status': 'closed'
            }
            mock_binance.return_value = mock_exchange
            
            adapter = BinanceAdapter(use_testnet=True)
            
            trade_intent = {
                "trade_id": 1,
                "symbol": "BTC",
                "side": "long",
                "quantity": 0.01,
                "entry_price": 60000.0,
                "stop_loss": 59500.0,
                "take_profit": 61000.0,
                "proposal_hash": "test_hash"
            }
            
            result = adapter.execute_order(trade_intent)
            
            assert result["status"] == "SUCCESS"
            assert result["mode"] == "live"
            assert result["order_id"] == "12345"
            assert result["execution_price"] == 60000.0


def test_binance_adapter_execute_order_failure():
    """Verify BinanceAdapter fails closed on API errors."""
    from binance_adapter import BinanceAdapter
    
    with patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key', 'BINANCE_API_SECRET': 'test_secret'}):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.create_market_order.side_effect = Exception("API Error")
            mock_binance.return_value = mock_exchange
            
            adapter = BinanceAdapter(use_testnet=True)
            
            trade_intent = {
                "trade_id": 1,
                "symbol": "BTC",
                "side": "long",
                "quantity": 0.01,
                "entry_price": 60000.0
            }
            
            result = adapter.execute_order(trade_intent)
            
            # Must fail closed
            assert result["status"] == "ERROR"
            assert "failed" in result["message"].lower()


def test_binance_adapter_get_balance_success():
    """Verify BinanceAdapter can fetch balance."""
    from binance_adapter import BinanceAdapter
    
    with patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key', 'BINANCE_API_SECRET': 'test_secret'}):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_balance.return_value = {
                'USDT': {'free': 10000.0, 'used': 0.0, 'total': 10000.0}
            }
            mock_binance.return_value = mock_exchange
            
            adapter = BinanceAdapter(use_testnet=True)
            result = adapter.get_balance()
            
            assert result["status"] == "SUCCESS"
            assert result["balance"] == 10000.0
            assert result["currency"] == "USDT"
            assert result["mode"] == "live"


def test_binance_adapter_get_balance_failure():
    """Verify BinanceAdapter fails closed on balance fetch errors."""
    from binance_adapter import BinanceAdapter
    
    with patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key', 'BINANCE_API_SECRET': 'test_secret'}):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_balance.side_effect = Exception("API Error")
            mock_binance.return_value = mock_exchange
            
            adapter = BinanceAdapter(use_testnet=True)
            result = adapter.get_balance()
            
            # Must fail closed
            assert result["status"] == "ERROR"
            assert result["balance"] == 0.0


def test_binance_adapter_get_positions_success():
    """Verify BinanceAdapter can fetch positions."""
    from binance_adapter import BinanceAdapter
    
    with patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key', 'BINANCE_API_SECRET': 'test_secret'}):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.fetch_balance.return_value = {
                'total': {
                    'BTC': 0.5,
                    'ETH': 10.0,
                    'USDT': 10000.0
                }
            }
            mock_binance.return_value = mock_exchange
            
            adapter = BinanceAdapter(use_testnet=True)
            result = adapter.get_open_positions()
            
            assert result["status"] == "SUCCESS"
            assert result["mode"] == "live"
            assert len(result["positions"]) == 2  # BTC and ETH (not USDT)


def test_binance_adapter_no_credentials_in_code():
    """Verify no credentials are hardcoded in source code."""
    import binance_adapter
    import inspect
    
    source = inspect.getsource(binance_adapter)
    
    # Check for common credential patterns
    forbidden_patterns = [
        'api_key = "',
        'api_secret = "',
        'apikey = "',
        'secret = "',
        'password = "'
    ]
    
    for pattern in forbidden_patterns:
        assert pattern not in source.lower(), (
            f"SECURITY VIOLATION: Hardcoded credentials found in binance_adapter.py"
        )


def test_binance_adapter_symbol_conversion():
    """Verify symbol is correctly converted to Binance format."""
    from binance_adapter import BinanceAdapter
    
    with patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key', 'BINANCE_API_SECRET': 'test_secret'}):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_exchange.create_market_order.return_value = {
                'id': '12345',
                'average': 60000.0
            }
            mock_binance.return_value = mock_exchange
            
            adapter = BinanceAdapter(use_testnet=True)
            
            trade_intent = {
                "trade_id": 1,
                "symbol": "BTC",
                "side": "long",
                "quantity": 0.01,
                "entry_price": 60000.0
            }
            
            adapter.execute_order(trade_intent)
            
            # Verify symbol was converted to BTC/USDT
            call_args = mock_exchange.create_market_order.call_args
            assert call_args[1]['symbol'] == "BTC/USDT"
            assert call_args[1]['side'] == "buy"


def test_binance_adapter_mainnet_requires_explicit_opt_in():
    """Verify mainnet requires explicit use_testnet=False."""
    from binance_adapter import BinanceAdapter
    
    with patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key', 'BINANCE_API_SECRET': 'test_secret'}):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            # Default should be testnet
            adapter_default = BinanceAdapter()
            assert adapter_default.use_testnet is True
            
            # Check first call (testnet)
            first_call_args = mock_binance.call_args_list[0][0]
            first_config = first_call_args[0]
            assert first_config['sandbox'] is True
            
            # Explicit mainnet
            adapter_mainnet = BinanceAdapter(use_testnet=False)
            assert adapter_mainnet.use_testnet is False
            
            # Check second call (mainnet)
            second_call_args = mock_binance.call_args_list[1][0]
            second_config = second_call_args[0]
            assert second_config['sandbox'] is False