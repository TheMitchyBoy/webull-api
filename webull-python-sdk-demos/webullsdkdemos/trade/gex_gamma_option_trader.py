# Copyright 2026 Webull
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class GexGammaSnapshot:
    symbol: str
    call_gamma: float
    put_gamma: float
    total_gamma: Optional[float] = None
    timestamp: Optional[str] = None


@dataclass
class OptionOrderConfig:
    market: str
    symbol: str
    strike_price: str
    init_exp_date: str
    quantity: int = 1
    order_type: str = "MARKET"
    limit_price: Optional[str] = None
    option_strategy: str = "SINGLE"
    time_in_force: str = "GTC"
    entrust_type: str = "QTY"


class GexGammaOptionTrader:
    """Automatic option trader that follows the strongest GEX gamma direction.

    This trader places a single long call or long put option order for an
    underlying symbol based on the current GEX gamma snapshot.

    It assumes an external GEX feed calls `process_snapshot` for each update.
    """

    def __init__(self, api: Any, account_id: str, order_config: OptionOrderConfig):
        self.api = api
        self.account_id = account_id
        self.order_config = order_config
        self.active_client_order_id: Optional[str] = None
        self.active_option_type: Optional[str] = None

    def _build_option_payload(self, option_type: str) -> List[Dict[str, Any]]:
        order_type = self.order_config.order_type
        if self.order_config.limit_price is None:
            order_type = "MARKET"

        payload = [
            {
                "client_order_id": uuid.uuid4().hex,
                "order_type": order_type,
                "quantity": str(self.order_config.quantity),
                "option_strategy": self.order_config.option_strategy,
                "side": "BUY",
                "time_in_force": self.order_config.time_in_force,
                "entrust_type": self.order_config.entrust_type,
                "orders": [
                    {
                        "side": "BUY",
                        "quantity": str(self.order_config.quantity),
                        "symbol": self.order_config.symbol,
                        "strike_price": self.order_config.strike_price,
                        "init_exp_date": self.order_config.init_exp_date,
                        "instrument_type": "OPTION",
                        "option_type": option_type,
                        "market": self.order_config.market,
                    }
                ],
            }
        ]

        if self.order_config.limit_price is not None:
            payload[0]["limit_price"] = str(self.order_config.limit_price)

        return payload

    @staticmethod
    def determine_option_side(snapshot: GexGammaSnapshot) -> str:
        """Select the option side with the larger gamma exposure."""
        if snapshot.call_gamma >= snapshot.put_gamma:
            return "CALL"
        return "PUT"

    def _category_header(self) -> str:
        market = self.order_config.market.upper()
        return f"{market}_OPTION"

    def _clear_active_order(self) -> None:
        self.active_client_order_id = None
        self.active_option_type = None

    def cancel_active_order(self) -> Optional[Any]:
        if not self.active_client_order_id:
            return None
        result = self.api.order_v2.cancel_option(self.account_id, self.active_client_order_id)
        self._clear_active_order()
        return result

    def place_option_order(self, option_type: str) -> Any:
        payload = self._build_option_payload(option_type)
        self.api.order_v2.add_custom_headers({"category": self._category_header()})
        response = self.api.order_v2.place_option(self.account_id, payload)
        self.api.order_v2.remove_custom_headers()

        if response and isinstance(response, dict):
            client_order_id = payload[0]["client_order_id"]
            self.active_client_order_id = client_order_id
            self.active_option_type = option_type
        else:
            self.active_client_order_id = payload[0]["client_order_id"]
            self.active_option_type = option_type

        return response

    def process_snapshot(self, snapshot: GexGammaSnapshot) -> Any:
        """Receive a GEX gamma update and update option orders accordingly."""
        desired_option_type = self.determine_option_side(snapshot)

        if self.active_option_type == desired_option_type and self.active_client_order_id:
            return {
                "status": "unchanged",
                "reason": f"already holding {desired_option_type}",
                "client_order_id": self.active_client_order_id,
            }

        if self.active_client_order_id:
            self.cancel_active_order()

        response = self.place_option_order(desired_option_type)
        return {
            "status": "placed",
            "direction": desired_option_type,
            "client_order_id": self.active_client_order_id,
            "response": response,
        }


if __name__ == "__main__":
    print("This module implements GEX gamma option trading logic.")
    print("Use GexGammaOptionTrader with a webullsdktrade API client and a live GEX feed.")
