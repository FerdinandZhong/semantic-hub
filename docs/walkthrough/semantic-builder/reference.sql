SELECT SUM(import_kwh) AS measured_import_kwh
FROM meter_readings
WHERE quality_status = 'VALID'
  AND is_estimated = 'false';
