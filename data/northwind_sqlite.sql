-- Northwind demo database for SQLite
-- Same schema as northwind_postgres.sql with SQLite-compatible types.
--
-- Usage:
--   sqlite3 /path/to/northwind.db < data/northwind_sqlite.sql

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS order_details;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT    NOT NULL,
    description   TEXT
);

CREATE TABLE suppliers (
    supplier_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    contact_name TEXT,
    country      TEXT,
    city         TEXT
);

CREATE TABLE customers (
    customer_id  TEXT    PRIMARY KEY,
    company_name TEXT    NOT NULL,
    contact_name TEXT,
    country      TEXT,
    city         TEXT
);

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_name   TEXT    NOT NULL,
    first_name  TEXT    NOT NULL,
    title       TEXT,
    city        TEXT,
    country     TEXT,
    hire_date   TEXT
);

CREATE TABLE products (
    product_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name   TEXT    NOT NULL,
    supplier_id    INTEGER REFERENCES suppliers(supplier_id),
    category_id    INTEGER REFERENCES categories(category_id),
    unit_price     REAL    DEFAULT 0,
    units_in_stock INTEGER DEFAULT 0,
    discontinued   INTEGER DEFAULT 0
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  TEXT    REFERENCES customers(customer_id),
    employee_id  INTEGER REFERENCES employees(employee_id),
    order_date   TEXT,
    ship_country TEXT,
    freight      REAL    DEFAULT 0
);

CREATE TABLE order_details (
    order_id   INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    unit_price REAL    NOT NULL,
    quantity   INTEGER NOT NULL DEFAULT 1,
    discount   REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (order_id, product_id)
);

-- ----------------------------------------------------------------
-- Data
-- ----------------------------------------------------------------

INSERT INTO categories VALUES
(1, 'Beverages',      'Soft drinks, coffees, teas, beers, and ales'),
(2, 'Condiments',     'Sweet and savory sauces, relishes, spreads, and seasonings'),
(3, 'Confections',    'Desserts, candies, and sweet breads'),
(4, 'Dairy Products', 'Cheeses'),
(5, 'Grains/Cereals', 'Breads, crackers, pasta, and cereal'),
(6, 'Meat/Poultry',   'Prepared meats'),
(7, 'Produce',        'Dried fruit and bean curd'),
(8, 'Seafood',        'Seaweed and fish');

INSERT INTO suppliers VALUES
(1, 'Exotic Liquids',                    'Charlotte Cooper',           'UK',        'London'),
(2, 'New Orleans Cajun Delights',        'Shelley Burke',              'USA',       'New Orleans'),
(3, 'Grandma Kellys Homestead',          'Regina Murphy',              'USA',       'Ann Arbor'),
(4, 'Tokyo Traders',                     'Yoshi Nagase',               'Japan',     'Tokyo'),
(5, 'Cooperativa de Quesos Las Cabras',  'Antonio del Valle Saavedra', 'Spain',     'Oviedo'),
(6, 'Mayumis',                           'Mayumi Ohno',                'Japan',     'Osaka'),
(7, 'Pavlova Ltd.',                      'Ian Devling',                'Australia', 'Melbourne'),
(8, 'Specialty Biscuits Ltd.',           'Peter Wilson',               'UK',        'Manchester');

INSERT INTO customers VALUES
('ALFKI', 'Alfreds Futterkiste',                'Maria Anders',       'Germany',     'Berlin'),
('ANATR', 'Ana Trujillo Emparedados y helados', 'Ana Trujillo',       'Mexico',      'Mexico D.F.'),
('ANTON', 'Antonio Moreno Taqueria',            'Antonio Moreno',     'Mexico',      'Mexico D.F.'),
('AROUT', 'Around the Horn',                    'Thomas Hardy',       'UK',          'London'),
('BERGS', 'Berglunds snabbkop',                 'Christina Berglund', 'Sweden',      'Lulea'),
('BLAUS', 'Blauer See Delikatessen',            'Hanna Moos',         'Germany',     'Mannheim'),
('BLONP', 'Blondel pere et fils',               'Frederique Citeaux', 'France',      'Strasbourg'),
('BOLID', 'Bolido Comidas preparadas',          'Martin Sommer',      'Spain',       'Madrid'),
('BONAP', 'Bon app',                            'Laurence Lebihan',   'France',      'Marseille'),
('BOTTM', 'Bottom-Dollar Marketse',             'Elizabeth Lincoln',  'Canada',      'Tsawassen'),
('BSBEV', 'Bs Beverages',                       'Victoria Ashworth',  'UK',          'London'),
('CACTU', 'Cactus Comidas para llevar',         'Patricio Simpson',   'Argentina',   'Buenos Aires'),
('CENTC', 'Centro comercial Moctezuma',         'Francisco Chang',    'Mexico',      'Mexico D.F.'),
('CHOPS', 'Chop-suey Chinese',                  'Yang Wang',          'Switzerland', 'Bern'),
('COMMI', 'Comercio Mineiro',                   'Pedro Afonso',       'Brazil',      'Sao Paulo');

INSERT INTO employees VALUES
(1, 'Davolio',   'Nancy',    'Sales Representative',    'Seattle', 'USA', '1992-05-01'),
(2, 'Fuller',    'Andrew',   'Vice President, Sales',   'Tacoma',  'USA', '1992-08-14'),
(3, 'Leverling', 'Janet',    'Sales Representative',    'Kirkland','USA', '1992-04-01'),
(4, 'Peacock',   'Margaret', 'Sales Representative',    'Redmond', 'USA', '1993-05-03'),
(5, 'Buchanan',  'Steven',   'Sales Manager',           'London',  'UK',  '1993-10-17'),
(6, 'Suyama',    'Michael',  'Sales Representative',    'London',  'UK',  '1993-10-17'),
(7, 'King',      'Robert',   'Sales Representative',    'London',  'UK',  '1994-01-02'),
(8, 'Callahan',  'Laura',    'Inside Sales Coordinator','Seattle', 'USA', '1994-03-05'),
(9, 'Dodsworth', 'Anne',     'Sales Representative',    'London',  'UK',  '1994-11-15');

INSERT INTO products VALUES
( 1, 'Chai',                          1, 1, 18.00,  39, 0),
( 2, 'Chang',                         1, 1, 19.00,  17, 0),
( 3, 'Aniseed Syrup',                 1, 2, 10.00,  13, 0),
( 4, 'Chef Antons Cajun Seasoning',   2, 2, 22.00,  53, 0),
( 5, 'Chef Antons Gumbo Mix',         2, 2, 21.35,   0, 1),
( 6, 'Grandmas Boysenberry Spread',   3, 2, 25.00, 120, 0),
( 7, 'Uncle Bobs Organic Dried Pears',3, 7, 30.00,  15, 0),
( 8, 'Northwoods Cranberry Sauce',    3, 2, 40.00,   6, 0),
( 9, 'Mishi Kobe Niku',               4, 6, 97.00,  29, 1),
(10, 'Ikura',                         4, 8, 31.00,  31, 0),
(11, 'Queso Cabrales',                5, 4, 21.00,  22, 0),
(12, 'Queso Manchego La Pastora',     5, 4, 38.00,  86, 0),
(13, 'Konbu',                         6, 8,  6.00,  24, 0),
(14, 'Tofu',                          6, 7, 23.25,  35, 0),
(15, 'Genen Shouyu',                  6, 2, 15.50,  39, 0),
(16, 'Pavlova',                       7, 3, 17.45,  29, 0),
(17, 'Alice Mutton',                  7, 6, 39.00,   0, 1),
(18, 'Carnarvon Tigers',              7, 8, 62.50,  42, 0),
(19, 'Teatime Chocolate Biscuits',    8, 3,  9.20,  25, 0),
(20, 'Sir Rodneys Marmalade',         8, 3, 81.00,  40, 0);

INSERT INTO orders VALUES
(10248, 'ALFKI', 5, '1996-07-04', 'Germany',      32.38),
(10249, 'ANATR', 6, '1996-07-05', 'Mexico',       11.61),
(10250, 'ANTON', 4, '1996-07-08', 'Mexico',       65.83),
(10251, 'AROUT', 3, '1996-07-08', 'UK',           41.34),
(10252, 'BERGS', 4, '1996-07-09', 'Sweden',       51.30),
(10253, 'BLAUS', 3, '1996-07-10', 'Germany',      58.17),
(10254, 'BLONP', 5, '1996-07-11', 'France',       22.98),
(10255, 'BOLID', 9, '1996-07-12', 'Spain',       148.33),
(10256, 'BONAP', 3, '1996-07-15', 'France',       13.97),
(10257, 'BOTTM', 4, '1996-07-16', 'Canada',       81.91),
(10258, 'BSBEV', 1, '1996-07-17', 'UK',          140.51),
(10259, 'CACTU', 4, '1996-07-18', 'Argentina',     3.25),
(10260, 'CENTC', 4, '1996-07-19', 'Mexico',       55.09),
(10261, 'CHOPS', 4, '1996-07-19', 'Switzerland',   3.05),
(10262, 'COMMI', 8, '1996-07-22', 'Brazil',       48.29);

INSERT INTO order_details VALUES
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
