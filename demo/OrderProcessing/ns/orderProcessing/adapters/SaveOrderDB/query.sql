INSERT INTO orders (
    order_id,
    customer_id,
    customer_email,
    final_amount,
    discount_amount,
    order_status
)
VALUES (?, ?, ?, ?, ?, ?);
