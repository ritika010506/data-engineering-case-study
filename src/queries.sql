-- ============================================================
-- Query 1: Total transaction amount per category
-- for the current calendar month.
--
-- Note: This total combines currencies. It is provided to
-- match the requested query, but is not a true monetary total
-- unless all amounts are converted to a common currency.
-- ============================================================

SELECT
    f.category,
    SUM(f.transaction_amount) AS total_transaction_amount,
    COUNT(*) AS transaction_count
FROM fact_transactions AS f
JOIN dim_date AS d
    ON f.date_key = d.date_key
WHERE d.year = YEAR(CURRENT_DATE)
  AND d.month = MONTH(CURRENT_DATE)
GROUP BY f.category
ORDER BY total_transaction_amount DESC;


-- ============================================================
-- Query 1B: Additional analysis by category and currency.
-- This avoids combining amounts in different currencies.
-- ============================================================

SELECT
    f.category,
    f.currency,
    SUM(f.transaction_amount) AS total_transaction_amount,
    COUNT(*) AS transaction_count
FROM fact_transactions AS f
JOIN dim_date AS d
    ON f.date_key = d.date_key
WHERE d.year = YEAR(CURRENT_DATE)
  AND d.month = MONTH(CURRENT_DATE)
GROUP BY
    f.category,
    f.currency
ORDER BY
    f.category,
    total_transaction_amount DESC;


-- ============================================================
-- Query 2: Top five regions by average transaction amount
-- per entity.
--
-- Step 1: Calculate each entity's average transaction amount.
-- Step 2: Average those entity-level averages by region.
-- Step 3: Return the top five regions.
-- ============================================================

WITH entity_averages AS (
    SELECT
        e.entity_key,
        e.region,
        AVG(f.transaction_amount) AS average_transaction_amount
    FROM fact_transactions AS f
    JOIN dim_entity AS e
        ON f.entity_key = e.entity_key
    GROUP BY
        e.entity_key,
        e.region
)
SELECT
    region,
    AVG(average_transaction_amount)
        AS average_transaction_amount_per_entity
FROM entity_averages
GROUP BY region
ORDER BY average_transaction_amount_per_entity DESC
LIMIT 5;