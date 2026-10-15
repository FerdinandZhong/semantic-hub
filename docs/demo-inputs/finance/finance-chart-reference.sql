-- Presenter check for page 3. This is not the scalar metric verification query.
SELECT jurisdiction, SUM(amount_sgd) AS settled_sender_outflow_sgd
FROM payments
GROUP BY jurisdiction
ORDER BY jurisdiction;
