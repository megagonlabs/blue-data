-- Czech banking dataset (finance) for SQLite
-- Derived from the BIRD benchmark financial database.
-- Intentionally preserves the original ambiguous column names (a2-a16 in district,
-- k_symbol/operation/type in trans) to demonstrate enrichment value.
--
-- Tables: district, client, account, loan, trans
--
-- Usage:
--   sqlite3 /path/to/finance.db < data/finance_sqlite.sql

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS trans;
DROP TABLE IF EXISTS loan;
DROP TABLE IF EXISTS account;
DROP TABLE IF EXISTS client;
DROP TABLE IF EXISTS district;

-- ----------------------------------------------------------------
-- district
-- Columns a2-a16 are deliberately opaque — enrichment resolves them.
--   a2  = district name
--   a3  = region
--   a4  = number of inhabitants
--   a5  = municipalities with < 499 inhabitants
--   a6  = municipalities with 500-1999 inhabitants
--   a7  = municipalities with 2000-9999 inhabitants
--   a8  = municipalities with > 10000 inhabitants
--   a9  = number of cities
--   a10 = ratio of urban inhabitants
--   a11 = average salary (CZK)
--   a12 = unemployment rate 1995 (%)
--   a13 = unemployment rate 1996 (%)
--   a14 = entrepreneurs per 1000 inhabitants
--   a15 = crimes committed 1995
--   a16 = crimes committed 1996
-- ----------------------------------------------------------------

CREATE TABLE district (
    district_id INTEGER PRIMARY KEY,
    a2          TEXT    NOT NULL,
    a3          TEXT    NOT NULL,
    a4          INTEGER NOT NULL,
    a5          INTEGER,
    a6          INTEGER,
    a7          INTEGER,
    a8          INTEGER,
    a9          INTEGER,
    a10         REAL,
    a11         INTEGER NOT NULL,
    a12         REAL,
    a13         REAL,
    a14         INTEGER,
    a15         INTEGER,
    a16         INTEGER
);

INSERT INTO district VALUES
( 1, 'Hl.m. Praha',      'Prague',             1204953, 0,   1,   0,  1, 1, 100.0, 12541, NULL, 0.29, 167, 85677, 99107),
( 2, 'Benesov',          'central Bohemia',      88884, 80,  26,   6,  2, 4,  46.7,  8507, 1.67, 1.85,  132,  2545,  2696),
( 3, 'Beroun',           'central Bohemia',      75232, 55,  17,   4,  1, 5,  41.7,  8980, 1.95, 2.21,  111,  2019,  2165),
( 4, 'Kladno',           'central Bohemia',     149893, 63,  15,   6,  4, 7,  67.4,  9753, 4.64, 5.05,  109,  4588,  4986),
( 5, 'Kolin',            'central Bohemia',      95616, 68,  23,   4,  2, 5,  51.4,  9307, 3.85, 4.43,  118,  2525,  2887),
( 6, 'Kutna Hora',       'central Bohemia',      77963, 61,  21,   4,  1, 5,  42.8,  8546, 3.79, 4.02,  126,  2242,  2553),
( 7, 'Melnik',           'central Bohemia',      97026, 67,  29,   7,  2, 5,  56.3,  9063, 2.52, 2.72,  138,  2691,  2889),
( 8, 'Mlada Boleslav',   'central Bohemia',     122960, 76,  24,   7,  2, 7,  66.5, 10521, 1.62, 1.91,  138,  3507,  3214),
( 9, 'Nymburk',          'central Bohemia',      85764, 79,  27,   4,  1, 5,  49.3,  8912, 3.29, 3.43,  126,  2168,  2337),
(10, 'Praha-vychod',     'central Bohemia',      93541, 97,  28,   4,  1, 5,  51.9,  9307, 1.95, 2.34,  133,  1940,  2049),
(11, 'Praha-zapad',      'central Bohemia',      72525, 77,  29,   3,  0, 5,  44.8,  9380, 1.62, 1.97,  137,  1765,  1879),
(12, 'Pribram',          'central Bohemia',     113694, 70,  21,   6,  3, 6,  53.1,  8745, 5.28, 5.59,  120,  3258,  3616),
(13, 'Rakovnik',         'central Bohemia',      55616, 63,  22,   2,  1, 4,  45.0,  8623, 4.31, 4.94,  133,  1590,  1714),
(14, 'Ceske Budejovice', 'south Bohemia',       174245, 68,  28,   8,  4, 8,  70.4,  9892, 2.49, 2.88,  130,  5249,  5643),
(15, 'Cesky Krumlov',    'south Bohemia',        59517, 55,  22,   2,  0, 4,  37.1,  8218, 5.65, 5.81,  118,  1839,  1947);

-- ----------------------------------------------------------------
-- client
-- gender: M / F
-- birth_date: YYYYMMDD integer format (original dataset encoding)
-- ----------------------------------------------------------------

CREATE TABLE client (
    client_id   INTEGER PRIMARY KEY,
    gender      TEXT    NOT NULL CHECK (gender IN ('M','F')),
    birth_date  INTEGER NOT NULL,
    district_id INTEGER NOT NULL REFERENCES district(district_id)
);

INSERT INTO client VALUES
( 1, 'F', 19701013,  1),
( 2, 'M', 19450204,  1),
( 3, 'F', 19550320,  2),
( 4, 'M', 19620815,  2),
( 5, 'F', 19740601,  3),
( 6, 'M', 19380912,  3),
( 7, 'F', 19801122,  4),
( 8, 'M', 19561009,  4),
( 9, 'F', 19920317,  5),
(10, 'M', 19671204,  5),
(11, 'F', 19490718,  6),
(12, 'M', 19751130,  6),
(13, 'F', 19830425,  7),
(14, 'M', 19590807,  7),
(15, 'F', 19680214,  8),
(16, 'M', 19421101,  8),
(17, 'F', 19770930,  9),
(18, 'M', 19880516,  9),
(19, 'F', 19530628, 10),
(20, 'M', 19710303, 10);

-- ----------------------------------------------------------------
-- account
-- frequency: statement issuance frequency
--   POPLATEK MESICNE  = monthly fee (monthly statement)
--   POPLATEK TYDNE    = weekly fee (weekly statement)
--   POPLATEK PO OBRATU = fee per transaction
-- ----------------------------------------------------------------

CREATE TABLE account (
    account_id  INTEGER PRIMARY KEY,
    district_id INTEGER NOT NULL REFERENCES district(district_id),
    frequency   TEXT    NOT NULL,
    date        TEXT    NOT NULL
);

INSERT INTO account VALUES
( 1,  1, 'POPLATEK MESICNE',   '1995-03-24'),
( 2,  1, 'POPLATEK MESICNE',   '1993-02-26'),
( 3,  2, 'POPLATEK TYDNE',     '1997-07-04'),
( 4,  2, 'POPLATEK MESICNE',   '1996-02-21'),
( 5,  3, 'POPLATEK PO OBRATU', '1997-04-13'),
( 6,  3, 'POPLATEK MESICNE',   '1994-09-10'),
( 7,  4, 'POPLATEK MESICNE',   '1996-06-12'),
( 8,  4, 'POPLATEK TYDNE',     '1995-11-30'),
( 9,  5, 'POPLATEK MESICNE',   '1998-01-08'),
(10,  5, 'POPLATEK PO OBRATU', '1993-07-13'),
(11,  6, 'POPLATEK MESICNE',   '1997-12-01'),
(12,  6, 'POPLATEK MESICNE',   '1996-04-29'),
(13,  7, 'POPLATEK TYDNE',     '1995-08-18'),
(14,  7, 'POPLATEK MESICNE',   '1998-03-22'),
(15,  8, 'POPLATEK MESICNE',   '1994-05-06');

-- ----------------------------------------------------------------
-- loan
-- status codes:
--   A = finished, no problems
--   B = finished, loan not paid off
--   C = running, no problems
--   D = running, client in debt
-- amount and payments are in CZK
-- duration is in months
-- ----------------------------------------------------------------

CREATE TABLE loan (
    loan_id    INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES account(account_id),
    date       TEXT    NOT NULL,
    amount     INTEGER NOT NULL,
    duration   INTEGER NOT NULL,
    payments   REAL    NOT NULL,
    status     TEXT    NOT NULL CHECK (status IN ('A','B','C','D'))
);

INSERT INTO loan VALUES
(4959,  2, '1994-01-05',  80952, 24,  3373.0, 'A'),
(4961,  2, '1996-04-29', 305904, 36,  8497.3, 'D'),
(4962,  3, '1997-12-08', 225020, 60,  3750.3, 'C'),
(4963,  7, '1998-07-02', 174744, 24,  7281.0, 'A'),
(4964,  8, '1998-07-08', 268704, 48,  5598.0, 'C'),
(4965,  9, '1998-04-19', 540864, 60,  9014.4, 'C'),
(4967, 10, '1996-10-08', 188928, 36,  5248.0, 'A'),
(4968, 11, '1997-09-09', 392400, 60,  6540.0, 'C'),
(4969, 12, '1998-10-14',  85320, 12,  7110.0, 'D'),
(4972, 13, '1995-11-08', 116400, 24,  4850.0, 'B'),
(4973, 14, '1997-06-29', 299880, 48,  6247.5, 'C'),
(4975,  1, '1997-03-01', 117720, 36,  3270.0, 'A'),
(4976,  4, '1996-05-15', 230400, 48,  4800.0, 'B'),
(4977,  5, '1998-02-11', 172800, 24,  7200.0, 'D'),
(4978,  6, '1997-08-27', 348000, 60,  5800.0, 'C');

-- ----------------------------------------------------------------
-- trans
-- type:
--   PRIJEM  = credit (incoming)
--   VYDAJ   = debit  (outgoing)
-- operation:
--   VYBER KARTOU      = credit card withdrawal
--   VKLAD             = cash deposit
--   PREVOD Z UCTU     = transfer in from another bank
--   VYBER             = cash withdrawal
--   PREVOD NA UCET    = transfer out to another bank
-- k_symbol (payment category):
--   POJISTNE          = insurance payment
--   SLUZBY            = payment for services
--   UROK              = interest credited
--   SANKC. UROK       = sanction interest (penalty)
--   SIPO              = household payment
--   DUCHOD            = old-age pension
--   UVER              = loan payment
--   NULL              = no category (cash deposits and uncategorised transfers)
-- amount and balance are in CZK
-- ----------------------------------------------------------------

CREATE TABLE trans (
    trans_id   INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES account(account_id),
    date       TEXT    NOT NULL,
    type       TEXT    NOT NULL,
    operation  TEXT,
    amount     INTEGER NOT NULL,
    balance    INTEGER NOT NULL,
    k_symbol   TEXT,
    bank       TEXT,
    account    REAL
);

INSERT INTO trans VALUES
(  1,  1, '1995-03-24', 'PRIJEM', 'VKLAD',          10000, 10000, NULL,          NULL,    NULL),
(  2,  1, '1995-04-13', 'VYDAJ',  'VYBER',            2000,  8000, 'SLUZBY',      NULL,    NULL),
(  3,  1, '1995-05-02', 'PRIJEM', 'PREVOD Z UCTU',    5000, 13000, 'DUCHOD',      'AB',  52314),
(  4,  1, '1995-06-15', 'VYDAJ',  'PREVOD NA UCET',   3500,  9500, 'SIPO',        'CD',  67890),
(  5,  1, '1995-07-01', 'PRIJEM', 'VKLAD',            8000, 17500, NULL,          NULL,    NULL),
(  6,  1, '1995-08-20', 'VYDAJ',  'VYBER KARTOU',     1200, 16300, 'POJISTNE',    NULL,    NULL),
(  7,  1, '1995-09-30', 'PRIJEM', 'VKLAD',             500, 16800, 'UROK',        NULL,    NULL),
(  8,  2, '1993-03-22', 'PRIJEM', 'VKLAD',           25000, 25000, NULL,          NULL,    NULL),
(  9,  2, '1993-05-14', 'VYDAJ',  'VYBER',            4000, 21000, 'SLUZBY',      NULL,    NULL),
( 10,  2, '1993-07-18', 'VYDAJ',  'PREVOD NA UCET',   6000, 15000, 'UVER',        'EF',  11111),
( 11,  2, '1993-09-01', 'PRIJEM', 'PREVOD Z UCTU',   10000, 25000, '',            'GH',  22222),
( 12,  2, '1993-11-15', 'VYDAJ',  'VYBER KARTOU',     2500, 22500, 'SIPO',        NULL,    NULL),
( 13,  2, '1994-01-05', 'VYDAJ',  'PREVOD NA UCET',   3373, 19127, 'UVER',        'AB',  33333),
( 14,  2, '1994-02-05', 'VYDAJ',  'PREVOD NA UCET',   3373, 15754, 'UVER',        'AB',  33333),
( 15,  2, '1994-03-05', 'VYDAJ',  'PREVOD NA UCET',   3373, 12381, 'UVER',        'AB',  33333),
( 16,  3, '1997-07-10', 'PRIJEM', 'VKLAD',           15000, 15000, NULL,          NULL,    NULL),
( 17,  3, '1997-08-03', 'VYDAJ',  'VYBER',            3000, 12000, 'SLUZBY',      NULL,    NULL),
( 18,  3, '1997-09-22', 'PRIJEM', 'PREVOD Z UCTU',    7500, 19500, '',            'IJ',  44444),
( 19,  3, '1997-10-11', 'VYDAJ',  'VYBER KARTOU',     1800, 17700, 'POJISTNE',    NULL,    NULL),
( 20,  3, '1997-11-28', 'PRIJEM', 'VKLAD',             340, 18040, 'UROK',        NULL,    NULL),
( 21,  4, '1996-03-01', 'PRIJEM', 'VKLAD',           20000, 20000, NULL,          NULL,    NULL),
( 22,  4, '1996-04-15', 'VYDAJ',  'VYBER',            5000, 15000, 'SIPO',        NULL,    NULL),
( 23,  4, '1996-05-20', 'VYDAJ',  'PREVOD NA UCET',   4800, 10200, 'UVER',        'KL',  55555),
( 24,  4, '1996-06-30', 'PRIJEM', 'PREVOD Z UCTU',    8000, 18200, 'DUCHOD',      'MN',  66666),
( 25,  4, '1996-07-10', 'VYDAJ',  'VYBER KARTOU',      950, 17250, 'SLUZBY',      NULL,    NULL),
( 26,  5, '1997-04-20', 'PRIJEM', 'VKLAD',           12000, 12000, NULL,          NULL,    NULL),
( 27,  5, '1997-05-09', 'VYDAJ',  'VYBER',            2200, 9800,  'POJISTNE',    NULL,    NULL),
( 28,  5, '1997-06-18', 'VYDAJ',  'PREVOD NA UCET',   7200, 2600,  'UVER',        'OP',  77777),
( 29,  5, '1997-07-25', 'VYDAJ',  'VYBER KARTOU',      500, 2100,  'SANKC. UROK', NULL,    NULL),
( 30,  5, '1997-08-01', 'PRIJEM', 'PREVOD Z UCTU',   10000, 12100, '',            'QR',  88888),
( 31,  6, '1994-09-15', 'PRIJEM', 'VKLAD',           30000, 30000, NULL,          NULL,    NULL),
( 32,  6, '1994-10-01', 'VYDAJ',  'PREVOD NA UCET',   5800, 24200, 'UVER',        'ST',  99999),
( 33,  6, '1994-11-14', 'VYDAJ',  'VYBER',            4000, 20200, 'SLUZBY',      NULL,    NULL),
( 34,  6, '1994-12-30', 'PRIJEM', 'VKLAD',             600, 20800, 'UROK',        NULL,    NULL),
( 35,  7, '1996-06-18', 'PRIJEM', 'VKLAD',           18000, 18000, NULL,          NULL,    NULL),
( 36,  7, '1996-07-10', 'VYDAJ',  'VYBER KARTOU',     3200, 14800, 'SIPO',        NULL,    NULL),
( 37,  7, '1996-08-22', 'VYDAJ',  'PREVOD NA UCET',   4800, 10000, 'UVER',        'UV',  10101),
( 38,  7, '1996-09-05', 'PRIJEM', 'PREVOD Z UCTU',    6000, 16000, '',            'WX',  20202),
( 39,  8, '1995-12-05', 'PRIJEM', 'VKLAD',           22000, 22000, NULL,          NULL,    NULL),
( 40,  8, '1996-01-15', 'VYDAJ',  'VYBER',            3500, 18500, 'SLUZBY',      NULL,    NULL),
( 41,  8, '1996-02-28', 'VYDAJ',  'PREVOD NA UCET',   5598, 12902, 'UVER',        'YZ',  30303),
( 42,  8, '1996-03-31', 'VYDAJ',  'PREVOD NA UCET',   5598,  7304, 'UVER',        'YZ',  30303),
( 43,  9, '1998-01-15', 'PRIJEM', 'VKLAD',           40000, 40000, NULL,          NULL,    NULL),
( 44,  9, '1998-02-01', 'VYDAJ',  'PREVOD NA UCET',   9014, 30986, 'UVER',        'AB',  41414),
( 45,  9, '1998-03-01', 'VYDAJ',  'PREVOD NA UCET',   9014, 21972, 'UVER',        'AB',  41414),
( 46,  9, '1998-04-01', 'VYDAJ',  'PREVOD NA UCET',   9014, 12958, 'UVER',        'AB',  41414),
( 47,  9, '1998-04-15', 'VYDAJ',  'VYBER KARTOU',     1500, 11458, 'POJISTNE',    NULL,    NULL),
( 48, 10, '1993-08-01', 'PRIJEM', 'VKLAD',           35000, 35000, NULL,          NULL,    NULL),
( 49, 10, '1993-09-20', 'VYDAJ',  'PREVOD NA UCET',   5248, 29752, 'UVER',        'CD',  52525),
( 50, 10, '1993-10-20', 'VYDAJ',  'PREVOD NA UCET',   5248, 24504, 'UVER',        'CD',  52525),
( 51, 10, '1993-11-18', 'VYDAJ',  'VYBER',            2000, 22504, 'SLUZBY',      NULL,    NULL),
( 52, 10, '1993-12-30', 'PRIJEM', 'PREVOD Z UCTU',    5000, 27504, 'DUCHOD',      'EF',  63636),
( 53, 11, '1997-12-10', 'PRIJEM', 'VKLAD',           28000, 28000, NULL,          NULL,    NULL),
( 54, 11, '1998-01-09', 'VYDAJ',  'PREVOD NA UCET',   6540, 21460, 'UVER',        'GH',  74747),
( 55, 11, '1998-02-09', 'VYDAJ',  'PREVOD NA UCET',   6540, 14920, 'UVER',        'GH',  74747),
( 56, 11, '1998-03-01', 'VYDAJ',  'VYBER KARTOU',     2200, 12720, 'SIPO',        NULL,    NULL),
( 57, 12, '1996-05-10', 'PRIJEM', 'VKLAD',           17000, 17000, NULL,          NULL,    NULL),
( 58, 12, '1996-06-15', 'VYDAJ',  'VYBER',            4500, 12500, 'SLUZBY',      NULL,    NULL),
( 59, 12, '1996-07-29', 'PRIJEM', 'PREVOD Z UCTU',    9000, 21500, '',            'IJ',  85858),
( 60, 12, '1996-08-20', 'VYDAJ',  'PREVOD NA UCET',   7110, 14390, 'UVER',        'KL',  96969),
( 61, 13, '1995-09-01', 'PRIJEM', 'VKLAD',           11000, 11000, NULL,          NULL,    NULL),
( 62, 13, '1995-10-14', 'VYDAJ',  'VYBER KARTOU',     1500,  9500, 'SIPO',        NULL,    NULL),
( 63, 13, '1995-11-08', 'VYDAJ',  'PREVOD NA UCET',   4850,  4650, 'UVER',        'MN',  10741),
( 64, 13, '1995-12-01', 'VYDAJ',  'PREVOD NA UCET',   4850,  -200, 'UVER',        'MN',  10741),
( 65, 13, '1995-12-15', 'VYDAJ',  'VYBER',             500,  -700, 'SANKC. UROK', NULL,    NULL),
( 66, 14, '1998-04-01', 'PRIJEM', 'VKLAD',           32000, 32000, NULL,          NULL,    NULL),
( 67, 14, '1998-05-15', 'VYDAJ',  'PREVOD NA UCET',   6248, 25752, 'UVER',        'OP',  20852),
( 68, 14, '1998-06-22', 'VYDAJ',  'VYBER KARTOU',     3100, 22652, 'POJISTNE',    NULL,    NULL),
( 69, 14, '1998-07-10', 'PRIJEM', 'PREVOD Z UCTU',    5000, 27652, '',            'QR',  31963),
( 70, 15, '1994-05-20', 'PRIJEM', 'VKLAD',           50000, 50000, NULL,          NULL,    NULL),
( 71, 15, '1994-06-10', 'VYDAJ',  'PREVOD NA UCET',   3270, 46730, 'UVER',        'ST',  43074),
( 72, 15, '1994-07-10', 'VYDAJ',  'PREVOD NA UCET',   3270, 43460, 'UVER',        'ST',  43074),
( 73, 15, '1994-08-05', 'VYDAJ',  'VYBER',            8000, 35460, 'SLUZBY',      NULL,    NULL),
( 74, 15, '1994-09-30', 'PRIJEM', 'PREVOD Z UCTU',    1200, 36660, 'UROK',        NULL,    NULL),
( 75, 15, '1994-10-10', 'VYDAJ',  'VYBER KARTOU',     4500, 32160, 'SIPO',        NULL,    NULL);
