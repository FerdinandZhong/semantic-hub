# Two short customer demos

Use the existing synthetic Finance and Manufacturing datasets.
Studio creates and governs definitions. Playground checks a published model. External agents can retrieve those definitions through MCP.

```text
Source data → Studio definition → Validate and publish → Playground check → External agent through MCP
```

## 1. Finance: one trusted definition of payment outflow

**Say:** “The same payment appears in several tables. A shared definition prevents teams from counting it twice.”

1. Open **Semantic Hub → Finance sample → Open Studio**.
2. Select `total_amount_sgd`. Show the payment tables and relationships on the canvas.
3. Explain the scope: settled sender outflow, expressed in SGD, for the synthetic sample.
4. Optionally show the linked HSBC beneficiary passage from PDF page 7.
5. Validate and publish the definition, or open the existing published version.
6. Open **Playground**, choose that version, and ask the supported question below.
7. Inspect the plan, run it, and show the value with its version and SQL.
8. Ask the unsupported question to demonstrate the model's limits.

**Supported question:** `What is the total settled sender outflow in SGD for the sample?`

**Expected starter result:** **686,572.96 SGD**.

**Unsupported question:** `What was the total settled sender outflow in SGD in 2025?`

The sample covers September 2026. The system should report missing period coverage; it must not return the sample total as a 2025 result.

**Reference SQL for Studio:**

```sql
SELECT SUM(amount_sgd) AS total_amount_sgd
FROM transactions
WHERE status = 'SETTLED';
```

**Say:** “The number comes from synthetic payment records. The real HSBC guide explains beneficiary-field meaning; it does not certify this amount.”

Use **Saved metrics → total_amount_sgd** as the repeatable path without AI interpretation.
The [full finance storyline](finance-customer-demo-story.md) includes document linking and twenty sample questions.

## 2. Manufacturing: shared downtime meaning with a traceable result

**Say:** “Operations and analysts need the same downtime definition before they compare results.”

1. Open **Semantic Hub → Manufacturing sample → Open Studio**.
2. Show `assets`, `sensor_readings`, and `work_orders` on the canvas.
3. Select `planned_downtime_minutes` and inspect its SQL expression and unit.
4. Validate and publish the definition, or open the existing published version.
5. Open **Playground** and select that version.
6. Ask the supported question, inspect the plan, and run it.
7. Show the result, the SQL, and the published version.
8. Ask the unsupported question to explain what this metric cannot establish.

**Supported question:** `Using planned_downtime_minutes, what is the total downtime recorded in the sample work orders?`

**Expected starter result:** **312 minutes**.

**Unsupported question:** `Which machine will fail next week?`

The published aggregate does not provide a predictive-maintenance forecast. The system should explain that limitation without inventing a machine or date.

**Reference SQL for Studio:**

```sql
SELECT SUM(downtime_minutes) AS planned_downtime_minutes
FROM work_orders;
```

**Say:** “This starter expression sums all sample work orders. The metric name alone does not filter for planned work.”

If the customer requires planned-only downtime, define the required filter and validate a new version before making that claim.
Use **Saved metrics → planned_downtime_minutes** for the repeatable demonstration path.

## Close both demos

**Say:** “Semantic Hub publishes the definition, version, lineage, and supporting evidence. Your advanced data-query agent retrieves this context through MCP.”

The two reference SQL results were rechecked against isolated starter fixtures.
They do not validate a locally edited definition or guarantee every natural-language interpretation.
