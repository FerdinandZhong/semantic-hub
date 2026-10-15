-- Copy one statement into each named metric verification field.
-- Rename generated per-row metrics to the names below; keep each original expression.
-- Normalize reviewed row labels using efpia-pages-4-5-row-guide.csv BEFORE creating the source.
-- These queries read stored data; expected values belong in the presenter checklist.

-- Metric: reviewed_observation_count; expected 9
SELECT COUNT(*) AS reviewed_observation_count FROM document_observations;

-- Metric: us_new_medicine_sales_share_percent; expected 74.1 %
SELECT value AS us_new_medicine_sales_share_percent
FROM document_observations
WHERE source_page = 4
  AND entity = 'USA'
  AND metric = 'New medicine sales share'
  AND unit = '%'
  AND period = 'Launches 2020–2024; sales 2025';

-- Metric: europe_top5_new_medicine_sales_share_percent; expected 15.6 %
SELECT value AS europe_top5_new_medicine_sales_share_percent
FROM document_observations
WHERE source_page = 4
  AND entity = 'Europe Top 5'
  AND metric = 'New medicine sales share'
  AND unit = '%'
  AND period = 'Launches 2020–2024; sales 2025';

-- Metric: japan_new_medicine_sales_share_percent; expected 3.6 %
SELECT value AS japan_new_medicine_sales_share_percent
FROM document_observations
WHERE source_page = 4
  AND entity = 'Japan'
  AND metric = 'New medicine sales share'
  AND unit = '%'
  AND period = 'Launches 2020–2024; sales 2025';

-- Metric: pharmerging_new_medicine_sales_share_percent; expected 2.9 %
SELECT value AS pharmerging_new_medicine_sales_share_percent
FROM document_observations
WHERE source_page = 4
  AND entity = 'Pharmerging'
  AND metric = 'New medicine sales share'
  AND unit = '%'
  AND period = 'Launches 2020–2024; sales 2025';

-- Metric: rest_world_new_medicine_sales_share_percent; expected 3.8 %
SELECT value AS rest_world_new_medicine_sales_share_percent
FROM document_observations
WHERE source_page = 4
  AND entity = 'Rest of the World'
  AND metric = 'New medicine sales share'
  AND unit = '%'
  AND period = 'Launches 2020–2024; sales 2025';

-- Metric: europe_rd_2024_eur_million; expected 56344 EUR million
SELECT value AS europe_rd_2024_eur_million
FROM document_observations
WHERE source_page = 5
  AND entity = 'Europe'
  AND metric = 'Pharmaceutical R&D expenditure'
  AND unit = 'EUR million'
  AND period = '2024';

-- Metric: us_rd_2024_usd_million; expected 75895 USD million
SELECT value AS us_rd_2024_usd_million
FROM document_observations
WHERE source_page = 5
  AND entity = 'USA'
  AND metric = 'Pharmaceutical R&D expenditure'
  AND unit = 'USD million'
  AND period = '2024';

-- Metric: japan_rd_2024_jpy_100million; expected 16607 JPY million x 100
SELECT value AS japan_rd_2024_jpy_100million
FROM document_observations
WHERE source_page = 5
  AND entity = 'Japan'
  AND metric = 'Pharmaceutical R&D expenditure'
  AND unit = 'JPY million x 100'
  AND period = '2024';

-- Metric: china_rd_2024_cny_million; expected 114557 CNY million
SELECT value AS china_rd_2024_cny_million
FROM document_observations
WHERE source_page = 5
  AND entity = 'China'
  AND metric = 'Pharmaceutical R&D expenditure'
  AND unit = 'CNY million'
  AND period = '2024';
