-- Paste this statement into total_amount_sgd reference SQL.
-- Use the independent transaction table to reconcile the payments metric.
SELECT SUM(amount_sgd) AS total_amount_sgd
FROM transactions
WHERE status = 'SETTLED';
