SELECT customer_id,
       customer_name,
       customer_email,
       loyalty_tier
FROM customer
WHERE customer_id = ?
  AND account_status = 'ACTIVE';
