# Fixed FX and reporting scope

SYNTHETIC DEMO MATERIAL. Applicable to the September 2026 fixture only. No live market rates or customer exchange rates are represented.

fx_rates.sgd_rate means SGD for one unit of the transaction currency. The fixed fixture rates are: SGD = 1.000000; USD = 1.300000; HKD = 0.170000.

For each transactions row, multiply transactions.amount by the matching fx_rates.sgd_rate. Round the converted amount to two decimal places using ROUND_HALF_UP. Store that value in transactions.amount_sgd. A settled payments.amount_sgd row carries the converted value once.

Convert each transaction before aggregation. Do not sum unlike currencies and then apply one rate. Do not apply an FX rate again to payments.amount_sgd, because that field is already in SGD.

The sender account currency determines transaction currency in this fixture. The fixed FX table has no effective-date column. It cannot answer historical daily rates or real-time exchange-rate questions.

The documents and source rows do not contain fees, account balances, profitability, observed exchange-rate movements, or verified AML findings.
