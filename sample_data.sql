-- Sample Data for SQL Query Script
-- This file contains the sample data used in the SQL query script

-- Users Table Data
INSERT INTO users (name, email) VALUES
('Alice Johnson', 'alice@example.com'),
('Bob Smith', 'bob@example.com'),
('Charlie Brown', 'charlie@example.com'),
('Diana Prince', 'diana@example.com');

-- Products Table Data
INSERT INTO products (name, price, category) VALUES
('Laptop', 999.99, 'Electronics'),
('Smartphone', 699.99, 'Electronics'),
('Book', 29.99, 'Education'),
('Coffee Mug', 12.99, 'Home'),
('Headphones', 149.99, 'Electronics');

-- Orders Table Data
INSERT INTO orders (user_id, product_id, quantity) VALUES
(1, 1, 1),  -- Alice buys Laptop
(1, 3, 2),  -- Alice buys 2 Books
(2, 2, 1),  -- Bob buys Smartphone
(3, 4, 3),  -- Charlie buys 3 Coffee Mugs
(4, 5, 1),  -- Diana buys Headphones
(2, 1, 1);  -- Bob buys Laptop

-- Example Queries for Reference

-- Count total users
SELECT COUNT(*) as user_count FROM users;

-- List all users
SELECT id, name, email, created_at FROM users ORDER BY name;

-- User order summary with total spending
SELECT 
    u.name as user_name,
    COUNT(o.id) as order_count,
    SUM(o.quantity * p.price) as total_spent
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
LEFT JOIN products p ON o.product_id = p.id
GROUP BY u.id, u.name
ORDER BY total_spent DESC;

-- Top products by revenue
SELECT 
    p.name as product_name,
    p.category,
    SUM(o.quantity) as total_quantity,
    SUM(o.quantity * p.price) as total_revenue
FROM products p
JOIN orders o ON p.id = o.product_id
GROUP BY p.id, p.name, p.category
ORDER BY total_revenue DESC;

-- Revenue by product category
SELECT 
    category,
    COUNT(DISTINCT p.id) as product_count,
    SUM(o.quantity * p.price) as total_revenue
FROM products p
JOIN products p ON p.id = o.product_id
GROUP BY category
ORDER BY total_revenue DESC;

-- Most recent orders
SELECT 
    u.name as user_name,
    p.name as product_name,
    o.quantity,
    o.order_date
FROM orders o
JOIN users u ON o.user_id = u.id
JOIN products p ON o.product_id = p.id
ORDER BY o.order_date DESC
LIMIT 5;