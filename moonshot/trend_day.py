# Copyright 2018 QuantRocket LLC - All Rights Reserved
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

import pandas as pd
from moonshot import Moonshot

class TrendDayStrategy(Moonshot):
    """
    Intraday strategy that buys (sells) if the security is up (down) more
    than 2% from yesterday's close as of 2:00 PM. Enters at 2:15 PM and
    exits the position at the market close.
    """

    CODE = 'trend-day'
    DB = 'etf-sampler-15min'
    DB_TIME_FILTERS = ['14:00:00', '15:45:00']
    DB_FIELDS = ['Open','Close']
    POSITIONS_CLOSED_DAILY = True

    def prices_to_signals(self, prices):

        closes = prices.loc["Close"]
        opens = prices.loc["Open"]

        # Take a cross section (xs) of prices to get a specific time's price;
        # the close of the 15:45 bar is the session close
        session_closes = closes.xs("15:45:00", level="Time")
        # the open of the 14:00 bar is the 14:00 price
        afternoon_prices = opens.xs("14:00:00", level="Time")

        # calculate the return from yesterday's close to 14:00
        prior_closes = session_closes.shift()
        returns = (afternoon_prices - prior_closes) / prior_closes

        # Go long if up more than 2%, go short if down more than -2%
        long_signals = returns > 0.02
        short_signals = returns < -0.02

        # Combine long and short signals
        signals = long_signals.astype(int).where(long_signals, -short_signals.astype(int))
        return signals

    def signals_to_target_weights(self, signals, prices):

        # allocate 20% of capital to each position, or equally divide capital
        # among positions, whichever is less
        target_weights = self.allocate_fixed_weights_capped(signals, 0.20, cap=1.0)
        return target_weights

    def target_weights_to_positions(self, target_weights, prices):

        # We enter on the same day as the signals/target_weights
        positions = target_weights.copy()
        return positions

    def positions_to_gross_returns(self, positions, prices):

        closes = prices.loc["Close"]

        # Our signal came at 14:00 and we enter at 14:15 (the close of the 14:00 bar)
        entry_prices = closes.xs("14:00:00", level="Time")
        session_closes = closes.xs("15:45:00", level="Time")

        # Our return is the 14:15-16:00 return, multiplied by the position
        pct_changes = (session_closes - entry_prices) / entry_prices
        gross_returns = pct_changes * positions
        return gross_returns

    def order_stubs_to_orders(self, orders, prices):

        # enter using market orders
        orders["Exchange"] = "SMART"
        orders["OrderType"] = "MKT"
        orders["Tif"] = "Day"

        # exit using MOC orders
        child_orders = self.orders_to_child_orders(orders)
        child_orders.loc[:, "OrderType"] = "MOC"

        orders = pd.concat([orders, child_orders])
        return orders
