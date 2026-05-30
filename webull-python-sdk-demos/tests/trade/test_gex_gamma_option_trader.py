import unittest
from unittest.mock import Mock

from webullsdkdemos.trade.gex_gamma_option_trader import (
    GexGammaOptionTrader,
    GexGammaSnapshot,
    OptionOrderConfig,
)


class TestGexGammaOptionTrader(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.api.order_v2 = Mock()
        self.api.order_v2.place_option.return_value = {"status_code": 200}
        self.api.order_v2.cancel_option.return_value = {"status_code": 200}
        self.order_config = OptionOrderConfig(
            market="US",
            symbol="AAPL",
            strike_price="200.0",
            init_exp_date="2025-08-15",
            quantity=1,
            order_type="MARKET",
        )
        self.trader = GexGammaOptionTrader(self.api, account_id="test_account", order_config=self.order_config)

    def test_determine_option_side_prefers_call(self):
        snapshot = GexGammaSnapshot(symbol="AAPL", call_gamma=1200.0, put_gamma=800.0)
        self.assertEqual(self.trader.determine_option_side(snapshot), "CALL")

    def test_determine_option_side_prefers_put(self):
        snapshot = GexGammaSnapshot(symbol="AAPL", call_gamma=400.0, put_gamma=1400.0)
        self.assertEqual(self.trader.determine_option_side(snapshot), "PUT")

    def test_process_snapshot_places_call_option_order(self):
        snapshot = GexGammaSnapshot(symbol="AAPL", call_gamma=1200.0, put_gamma=800.0)
        result = self.trader.process_snapshot(snapshot)

        self.api.order_v2.add_custom_headers.assert_called_once()
        self.api.order_v2.place_option.assert_called_once()
        self.api.order_v2.remove_custom_headers.assert_called_once()
        self.assertEqual(result["status"], "placed")
        self.assertEqual(result["direction"], "CALL")
        self.assertIsNotNone(result["client_order_id"])

    def test_process_snapshot_switches_to_put_after_call(self):
        snapshot_call = GexGammaSnapshot(symbol="AAPL", call_gamma=1000.0, put_gamma=500.0)
        self.trader.process_snapshot(snapshot_call)
        first_order_id = self.trader.active_client_order_id

        snapshot_put = GexGammaSnapshot(symbol="AAPL", call_gamma=300.0, put_gamma=900.0)
        result = self.trader.process_snapshot(snapshot_put)

        self.api.order_v2.cancel_option.assert_called_once_with("test_account", first_order_id)
        self.assertEqual(result["direction"], "PUT")
        self.assertEqual(result["status"], "placed")

    def test_process_snapshot_ignores_same_direction(self):
        snapshot = GexGammaSnapshot(symbol="AAPL", call_gamma=1200.0, put_gamma=800.0)
        first_result = self.trader.process_snapshot(snapshot)
        second_result = self.trader.process_snapshot(snapshot)

        self.assertEqual(second_result["status"], "unchanged")
        self.api.order_v2.place_option.assert_called_once()


if __name__ == "__main__":
    unittest.main()
