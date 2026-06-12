-- Northwind demo database for PostgreSQL
-- A classic sales/inventory schema with 7 tables and realistic foreign-key relations.
--
-- Usage:
--   psql -h localhost -U postgres -c "CREATE DATABASE northwind;"
--   psql -h localhost -U postgres -d northwind -f data/northwind_postgres.sql

-- ----------------------------------------------------------------
-- Schema
-- ----------------------------------------------------------------

DROP TABLE IF EXISTS order_details  CASCADE;
DROP TABLE IF EXISTS orders         CASCADE;
DROP TABLE IF EXISTS products       CASCADE;
DROP TABLE IF EXISTS employees      CASCADE;
DROP TABLE IF EXISTS suppliers      CASCADE;
DROP TABLE IF EXISTS customers      CASCADE;
DROP TABLE IF EXISTS categories     CASCADE;

CREATE TABLE categories (
    category_id   SERIAL       PRIMARY KEY,
    category_name VARCHAR(30)  NOT NULL,
    description   TEXT
);

CREATE TABLE suppliers (
    supplier_id  SERIAL      PRIMARY KEY,
    company_name VARCHAR(40) NOT NULL,
    contact_name VARCHAR(30),
    country      VARCHAR(20),
    city         VARCHAR(20)
);

CREATE TABLE customers (
    customer_id  CHAR(5)     PRIMARY KEY,
    company_name VARCHAR(40) NOT NULL,
    contact_name VARCHAR(30),
    country      VARCHAR(20),
    city         VARCHAR(20)
);

CREATE TABLE employees (
    employee_id SERIAL      PRIMARY KEY,
    last_name   VARCHAR(20) NOT NULL,
    first_name  VARCHAR(15) NOT NULL,
    title       VARCHAR(30),
    city        VARCHAR(20),
    country     VARCHAR(20),
    hire_date   DATE
);

CREATE TABLE products (
    product_id     SERIAL        PRIMARY KEY,
    product_name   VARCHAR(40)   NOT NULL,
    supplier_id    INTEGER       REFERENCES suppliers(supplier_id),
    category_id    INTEGER       REFERENCES categories(category_id),
    unit_price     NUMERIC(10,2) DEFAULT 0,
    units_in_stock INTEGER       DEFAULT 0,
    discontinued   BOOLEAN       DEFAULT FALSE
);

CREATE TABLE orders (
    order_id    SERIAL        PRIMARY KEY,
    customer_id CHAR(5)       REFERENCES customers(customer_id),
    employee_id INTEGER       REFERENCES employees(employee_id),
    order_date  DATE,
    ship_country VARCHAR(20),
    freight     NUMERIC(10,2) DEFAULT 0
);

CREATE TABLE order_details (
    order_id   INTEGER       NOT NULL REFERENCES orders(order_id),
    product_id INTEGER       NOT NULL REFERENCES products(product_id),
    unit_price NUMERIC(10,2) NOT NULL,
    quantity   SMALLINT      NOT NULL DEFAULT 1,
    discount   REAL          NOT NULL DEFAULT 0,
    PRIMARY KEY (order_id, product_id)
);

-- ----------------------------------------------------------------
-- Data
-- ----------------------------------------------------------------

INSERT INTO categories (category_id, category_name, description) VALUES
(1, 'Beverages',      'Soft drinks, coffees, teas, beers, and ales'),
(2, 'Condiments',     'Sweet and savory sauces, relishes, spreads, and seasonings'),
(3, 'Confections',    'Desserts, candies, and sweet breads'),
(4, 'Dairy Products', 'Cheeses'),
(5, 'Grains/Cereals', 'Breads, crackers, pasta, and cereal'),
(6, 'Meat/Poultry',   'Prepared meats'),
(7, 'Produce',        'Dried fruit and bean curd'),
(8, 'Seafood',        'Seaweed and fish');

INSERT INTO suppliers (supplier_id, company_name, contact_name, country, city) VALUES
(1, 'Exotic Liquids',                      'Charlotte Cooper',           'UK',      'London'),
(2, 'New Orleans Cajun Delights',          'Shelley Burke',              'USA',     'New Orleans'),
(3, 'Grandma Kelly''s Homestead',          'Regina Murphy',              'USA',     'Ann Arbor'),
(4, 'Tokyo Traders',                       'Yoshi Nagase',               'Japan',   'Tokyo'),
(5, 'Cooperativa de Quesos Las Cabras',    'Antonio del Valle Saavedra', 'Spain',   'Oviedo'),
(6, 'Mayumi''s',                           'Mayumi Ohno',                'Japan',   'Osaka'),
(7, 'Pavlova Ltd.',                        'Ian Devling',                'Australia','Melbourne'),
(8, 'Specialty Biscuits Ltd.',             'Peter Wilson',               'UK',      'Manchester');

INSERT INTO customers (customer_id, company_name, contact_name, country, city) VALUES
('ALFKI', 'Alfreds Futterkiste',                  'Maria Anders',      'Germany', 'Berlin'),
('ANATR', 'Ana Trujillo Emparedados y helados',   'Ana Trujillo',      'Mexico',  'Mexico D.F.'),
('ANTON', 'Antonio Moreno Taquería',              'Antonio Moreno',    'Mexico',  'Mexico D.F.'),
('AROUT', 'Around the Horn',                       'Thomas Hardy',      'UK',      'London'),
('BERGS', 'Berglunds snabbköp',                   'Christina Berglund','Sweden',  'Luleå'),
('BLAUS', 'Blauer See Delikatessen',              'Hanna Moos',        'Germany', 'Mannheim'),
('BLONP', 'Blondel père et fils',                 'Frédérique Citeaux','France',  'Strasbourg'),
('BOLID', 'Bólido Comidas preparadas',            'Martín Sommer',     'Spain',   'Madrid'),
('BONAP', 'Bon app',                              'Laurence Lebihan',  'France',  'Marseille'),
('BOTTM', 'Bottom-Dollar Marketse',               'Elizabeth Lincoln', 'Canada',  'Tsawassen'),
('BSBEV', 'B''s Beverages',                       'Victoria Ashworth', 'UK',      'London'),
('CACTU', 'Cactus Comidas para llevar',           'Patricio Simpson',  'Argentina','Buenos Aires'),
('CENTC', 'Centro comercial Moctezuma',           'Francisco Chang',   'Mexico',  'Mexico D.F.'),
('CHOPS', 'Chop-suey Chinese',                    'Yang Wang',         'Switzerland','Bern'),
('COMMI', 'Comércio Mineiro',                     'Pedro Afonso',      'Brazil',  'Sao Paulo');

INSERT INTO employees (employee_id, last_name, first_name, title, city, country, hire_date) VALUES
(1, 'Davolio',   'Nancy',    'Sales Representative',   'Seattle', 'USA', '1992-05-01'),
(2, 'Fuller',    'Andrew',   'Vice President, Sales',  'Tacoma',  'USA', '1992-08-14'),
(3, 'Leverling', 'Janet',    'Sales Representative',   'Kirkland','USA', '1992-04-01'),
(4, 'Peacock',   'Margaret', 'Sales Representative',   'Redmond', 'USA', '1993-05-03'),
(5, 'Buchanan',  'Steven',   'Sales Manager',          'London',  'UK',  '1993-10-17'),
(6, 'Suyama',    'Michael',  'Sales Representative',   'London',  'UK',  '1993-10-17'),
(7, 'King',      'Robert',   'Sales Representative',   'London',  'UK',  '1994-01-02'),
(8, 'Callahan',  'Laura',    'Inside Sales Coordinator','Seattle', 'USA', '1994-03-05'),
(9, 'Dodsworth', 'Anne',     'Sales Representative',   'London',  'UK',  '1994-11-15');

INSERT INTO products (product_id, product_name, supplier_id, category_id, unit_price, units_in_stock, discontinued) VALUES
( 1, 'Chai',                           1, 1, 18.00,  39, FALSE),
( 2, 'Chang',                          1, 1, 19.00,  17, FALSE),
( 3, 'Aniseed Syrup',                  1, 2, 10.00,  13, FALSE),
( 4, 'Chef Anton''s Cajun Seasoning',  2, 2, 22.00,  53, FALSE),
( 5, 'Chef Anton''s Gumbo Mix',        2, 2, 21.35,   0, TRUE),
( 6, 'Grandma''s Boysenberry Spread',  3, 2, 25.00, 120, FALSE),
( 7, 'Uncle Bob''s Organic Dried Pears',3,7, 30.00,  15, FALSE),
( 8, 'Northwoods Cranberry Sauce',     3, 2, 40.00,   6, FALSE),
( 9, 'Mishi Kobe Niku',                4, 6, 97.00,  29, TRUE),
(10, 'Ikura',                          4, 8, 31.00,  31, FALSE),
(11, 'Queso Cabrales',                 5, 4, 21.00,  22, FALSE),
(12, 'Queso Manchego La Pastora',      5, 4, 38.00,  86, FALSE),
(13, 'Konbu',                          6, 8,  6.00,  24, FALSE),
(14, 'Tofu',                           6, 7, 23.25,  35, FALSE),
(15, 'Genen Shouyu',                   6, 2, 15.50,  39, FALSE),
(16, 'Pavlova',                        7, 3, 17.45,  29, FALSE),
(17, 'Alice Mutton',                   7, 6, 39.00,   0, TRUE),
(18, 'Carnarvon Tigers',               7, 8, 62.50,  42, FALSE),
(19, 'Teatime Chocolate Biscuits',     8, 3,  9.20,  25, FALSE),
(20, 'Sir Rodney''s Marmalade',        8, 3, 81.00,  40, FALSE);

INSERT INTO orders (order_id, customer_id, employee_id, order_date, ship_country, freight) VALUES
(10248, 'ALFKI', 5, '1996-07-04', 'Germany',     32.38),
(10249, 'ANATR', 6, '1996-07-05', 'Mexico',      11.61),
(10250, 'ANTON', 4, '1996-07-08', 'Mexico',      65.83),
(10251, 'AROUT', 3, '1996-07-08', 'UK',          41.34),
(10252, 'BERGS', 4, '1996-07-09', 'Sweden',      51.30),
(10253, 'BLAUS', 3, '1996-07-10', 'Germany',     58.17),
(10254, 'BLONP', 5, '1996-07-11', 'France',      22.98),
(10255, 'BOLID', 9, '1996-07-12', 'Spain',      148.33),
(10256, 'BONAP', 3, '1996-07-15', 'France',      13.97),
(10257, 'BOTTM', 4, '1996-07-16', 'Canada',      81.91),
(10258, 'BSBEV', 1, '1996-07-17', 'UK',          140.51),
(10259, 'CACTU', 4, '1996-07-18', 'Argentina',    3.25),
(10260, 'CENTC', 4, '1996-07-19', 'Mexico',      55.09),
(10261, 'CHOPS', 4, '1996-07-19', 'Switzerland',  3.05),
(10262, 'COMMI', 8, '1996-07-22', 'Brazil',      48.29);

INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount) VALUES
(10248, 11, 14.00, 12, 0.00),
(10248, 12,  9.80, 10, 0.00),
(10248, 13, 34.80,  5, 0.00),
(10249, 14, 18.60,  9, 0.00),
(10249, 15, 42.40, 40, 0.00),
(10250, 16,  7.70, 10, 0.00),
(10250, 17, 42.40, 35, 0.15),
(10250, 18, 16.80, 15, 0.15),
(10251,  1, 16.80,  6, 0.05),
(10251,  5, 15.60, 15, 0.05),
(10252,  2, 15.20, 25, 0.05),
(10252, 20, 64.80, 40, 0.05),
(10252,  6, 27.20, 40, 0.00),
(10253,  3, 10.00, 20, 0.00),
(10253,  9, 14.40, 42, 0.00),
(10253,  4, 16.00, 40, 0.00),
(10254,  7,  3.60, 15, 0.15),
(10254, 19, 19.20, 21, 0.15),
(10254,  8,  8.00, 21, 0.00),
(10255, 10, 15.20, 20, 0.00);

-- Sync sequences after explicit ID inserts
SELECT setval('categories_category_id_seq',  (SELECT MAX(category_id) FROM categories));
SELECT setval('suppliers_supplier_id_seq',   (SELECT MAX(supplier_id) FROM suppliers));
SELECT setval('employees_employee_id_seq',   (SELECT MAX(employee_id) FROM employees));
SELECT setval('products_product_id_seq',     (SELECT MAX(product_id)  FROM products));
SELECT setval('orders_order_id_seq',         (SELECT MAX(order_id)    FROM orders));
