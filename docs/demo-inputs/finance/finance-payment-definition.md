# Payment definition and reconciliation

SYNTHETIC DEMO MATERIAL. This document describes the bundled finance fixture. It is not a bank policy or evidence of real customer activity.

Coverage: 1 September 2026 through 30 September 2026. The booking date uses UTC, not Asia/Singapore local time.

The total_amount_sgd metric measures settled sender outflow. Its expression is SUM(payments.amount_sgd). One payments row represents one settled transaction viewed from its sender. payments.customer_id identifies the sender customer; payments.jurisdiction is that customer's jurisdiction, not the receiver location.

Only transactions with status SETTLED produce payments rows. REJECTED transactions remain in transactions but do not enter payments or ledger_postings. Exclude rejected transfers from settled sender outflow.

Each settled transaction has a negative debit and an equal positive credit in ledger_postings. Summing signed postings nets to zero. Summing absolute postings counts both sides. Neither is the settled sender outflow metric.

Evidence links explain the meaning of payments, transactions.status, payments.amount_sgd, and total_amount_sgd. They do not change SQL, create a join, or establish financial risk.
