INSERT INTO orders (
    order_id,
    customer_id,
    final_amount,
    discount_amount,
    order_status
)
VALUES (?, ?, ?, ?, ?);
