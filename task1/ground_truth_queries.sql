-- Q1: List all customers
SELECT * FROM customers;

-- Q2: Get all product names and lines
SELECT "productName", "productLine" FROM products;

-- Q3: Total number of orders
SELECT COUNT(*) AS total_orders FROM orders;

-- Q4: Total revenue
SELECT SUM(amount) FROM payments;