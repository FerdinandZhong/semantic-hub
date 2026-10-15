# Reference SQL for the four local datasets

For the separate public pharmaceutical intelligence model, use its [six reference queries](pharma-intelligence.md#validation-references) and [demo story](pharma-intelligence-demo-story.md).

Verified against the checked-in `sectors/v1` serving fixtures on 12 October 2026.
These examples match the starter metrics without additional grouping or filters.
They are operator examples, not automatically installed approvals.

## Use a query in Studio

1. Open the source from Semantic Hub, then choose **Open Studio**.
2. Select the metric in Studio.
3. Paste the matching query into **Independent reference SQL**.
4. Check its business scope, filters, units, and output column name.
5. Choose **Save draft**, then run **Validate** under **Validation & review**.
6. Inspect the results and approve the objects you reviewed using **Approve selected**.
7. Open **Versions & releases**, enter the version details, and confirm your review.
8. Publish the reviewed version, then activate it if queries should use it.

```text
Metric definition + reference SQL → save → validation → item review → reviewed version
                                                                         |
                                                                         v
                                                             publish → activate
```

Every current metric requires reference SQL before whole-version approval.
The checker compares the compiled and reference results, including output columns.
Keep the output aliases below exactly as shown.
Update the reference query if you change a metric's grouping, filters, or meaning.

**Ready for review** means an individual item is eligible for human review.
It does not mean the item is approved or that the complete draft passed validation.
The version page lists failed checks and the count of objects still needing approval.

## Manufacturing

Metric: `planned_downtime_minutes`. Expected result: **312 minutes**.

```sql
SELECT SUM(downtime_minutes) AS planned_downtime_minutes
FROM work_orders;
```

The starter definition sums all work orders.
Its name does not add a filter for planned work automatically.
If the business definition requires such a filter, revise both definitions and review the available source fields first.

## Finance

Metric: `total_amount_sgd`. Expected result: **686572.96 SGD**.

```sql
SELECT SUM(amount_sgd) AS total_amount_sgd
FROM payments;
```

This sums the prepared SGD amounts in `payments`.
It does not recalculate exchange rates or sum the separate transaction and ledger tables.

## Pharma

Metric: `average_assay_percent`. Expected result: **98.275 percent**.

```sql
SELECT AVG(assay_percent) AS average_assay_percent
FROM lab_results;
```

This is the unweighted average across lab-result rows.
It does not imply batch release or apply an approval-status filter.

## Power

Metric: `measured_import_kwh`. Expected result: **8547.282 kWh**.

```sql
SELECT SUM(import_kwh) AS measured_import_kwh
FROM meter_readings
WHERE quality_status = 'VALID'
  AND is_estimated = 'false';
```

This excludes invalid and estimated readings.
It matches the starter metric's conditional aggregate through an equivalent WHERE clause.

## Evidence and limits

The examples come from the separate fixture evaluation references:

- [Manufacturing reference](../apps/helios-ds-generation/fixtures/sectors/v1/manufacturing/evaluation/reference.json).
- [Finance reference](../apps/helios-ds-generation/fixtures/sectors/v1/finance/evaluation/reference.json).
- [Pharma reference](../apps/helios-ds-generation/fixtures/sectors/v1/pharma/evaluation/reference.json).
- [Power reference](../apps/helios-ds-generation/fixtures/sectors/v1/power/evaluation/reference.json).

The original references use `AS value`; these examples use the metric name required for Studio reconciliation.
Verification executed the queries through [LocalPackEngine](../shared/helios_core/demo/local.py) against serving bytes.
It did not save drafts, approve objects, or publish versions.
Decimal display precision can differ while values remain equal.

The proposal generator does not read evaluation references or fill this field automatically.
These published examples are suitable for reproducing the starter demo, not for measuring held-out accuracy.
Matching results on a small synthetic fixture do not prove production business correctness.
Automatic reference-query suggestions and trusted expected-result alternatives remain proposed improvements.

See the [builder guide](context-builder.md) and [documentation alignment review](DOCS_ALIGNMENT.md).
