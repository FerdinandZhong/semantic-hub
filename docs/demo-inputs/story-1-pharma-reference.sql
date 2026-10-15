-- One query per matching metric. Do not paste all statements into one verification field.
SELECT COUNT(*) AS novel_approval_count FROM approval_events;

SELECT SUM(patient_count) AS evidence_patient_count FROM trial_cohorts;

SELECT value AS no_prior_adc_orr_percent
FROM trial_results WHERE result_id = 'beamion_no_prior_adc_orr';

SELECT value AS prior_adc_orr_percent
FROM trial_results WHERE result_id = 'beamion_prior_adc_orr';

SELECT value AS no_prior_adc_durable_response_percent
FROM trial_results WHERE result_id = 'beamion_no_prior_adc_dor_ge_6_months';

SELECT value AS us_new_medicine_sales_share_percent
FROM industry_observations WHERE geography = 'USA';
