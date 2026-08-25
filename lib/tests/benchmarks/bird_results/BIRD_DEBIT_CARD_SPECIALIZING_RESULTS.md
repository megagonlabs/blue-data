# BIRD — debit_card_specializing — Results

**Conditions:** `keyword`  
**Queries:** 64  
**Last run:** 2026-08-25 09:56 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 23% |
| Hit@3 | 23% |
| Hit@5 | 36% |
| MRR | 34% |

```
Hit@5 (% of 64 queries)

  keyword         █████░░░░░░░░░░   36%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.159 |
| P@3 | 0.234 |
| R@3 | 0.125 |
| F1@5 | 0.204 |
| P@5 | 0.258 |
| R@5 | 0.193 |
| F1@10 | 0.480 |
| P@10 | 0.327 |
| R@10 | 0.984 |
| F1@Ideal-K | 0.159 |
| P@Ideal-K | 0.234 |
| R@Ideal-K | 0.125 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 64 | 23% | 0.34 | 0.16 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_debit_card_specializing_001 | bird | How many gas stations in CZE has Premium gas? | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_002 | bird | What is the ratio of customers who pay in EUR agains… | ✅ | 1.00 | 1.00 |
| bird_debit_card_specializing_003 | bird | In 2012, who had the least consumption in LAM? | ❌ | 0.17 | 0.00 |
| bird_debit_card_specializing_004 | bird | What was the average monthly consumption of customer… | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_005 | bird | Which customers, paying in CZK, consumed the most ga… | ❌ | 0.20 | 0.00 |
| bird_debit_card_specializing_006 | bird | How many customers in KAM had a consumption of less … | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_007 | bird | What was the difference in gas consumption between C… | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_008 | bird | Which year recorded the most gas use paid in EUR? | ❌ | 0.20 | 0.00 |
| bird_debit_card_specializing_009 | bird | Which segment had the least consumption? | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_010 | bird | Which year recorded the most consumption of gas paid… | ❌ | 0.17 | 0.00 |
| bird_debit_card_specializing_011 | bird | What was the gas consumption peak month for SME cust… | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_012 | bird | What is the difference in the annual average consump… | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_013 | bird | Which of the three segments—SME, LAM and KAM—has the… | ❌ | 0.17 | 0.00 |
| bird_debit_card_specializing_014 | bird | How much did customer 6 consume in total between Aug… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_015 | bird | How many more "discount" gas stations does the Czech… | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_016 | bird | How much more was customer 7 consuming in April 2013… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_017 | bird | Is it true that more SMEs pay in Czech koruna than i… | ❌ | 0.20 | 0.00 |
| bird_debit_card_specializing_018 | bird | Which LAM customer used the Euro as their currency a… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_019 | bird | Who among KAM's customers consumed the most? How muc… | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_020 | bird | How much did the KAM customers consume in total in M… | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_021 | bird | How many percent of LAM customer consumed more than … | ❌ | 0.20 | 0.00 |
| bird_debit_card_specializing_022 | bird | Which country has more "value for money" gas station… | ❌ | 0.10 | 0.00 |
| bird_debit_card_specializing_023 | bird | What percentage of KAM customers pay in euros? | ✅ | 1.00 | 1.00 |
| bird_debit_card_specializing_024 | bird | In February 2012, what percentage of customers consu… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_025 | bird | What percentage of Slovakian gas stations are premiu… | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_026 | bird | Which client ID consumed the most in September 2013? | ❌ | 0.20 | 0.00 |
| bird_debit_card_specializing_027 | bird | Which client segment consumed the least in September… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_028 | bird | Which SME customer consumed the least in June 2012? | ❌ | 0.20 | 0.00 |
| bird_debit_card_specializing_029 | bird | What is the highest monthly consumption in the year … | ❌ | 0.12 | 0.00 |
| bird_debit_card_specializing_030 | bird | What is the biggest monthly consumption of the custo… | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_031 | bird | Please list the product description of the products … | ✅ | 1.00 | 0.50 |
| bird_debit_card_specializing_032 | bird | Please list the countries of the gas stations with t… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_033 | bird | Please list the chains of the gas stations with tran… | ❌ | 0.20 | 0.00 |
| bird_debit_card_specializing_034 | bird | Please list the product description of the products … | ✅ | 1.00 | 0.50 |
| bird_debit_card_specializing_035 | bird | What is the average total price of the transactions … | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_036 | bird | Among the customers who paid in euro, how many of th… | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_037 | bird | Please list the product descriptions of the transact… | ❌ | 0.17 | 0.00 |
| bird_debit_card_specializing_038 | bird | Please list the disparate time of the transactions t… | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_039 | bird | How many transactions taken place in the gas station… | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_040 | bird | Among the transactions made in the gas stations in t… | ❌ | 0.12 | 0.00 |
| bird_debit_card_specializing_041 | bird | What is the average total price of the transactions … | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_042 | bird | For the customers who paid in the euro, what is thei… | ✅ | 1.00 | 0.50 |
| bird_debit_card_specializing_043 | bird | Which customer paid the most in 2012/8/25? | ❌ | 0.12 | 0.00 |
| bird_debit_card_specializing_044 | bird | Which country's gas station had the first paid cusom… | ❌ | 0.12 | 0.00 |
| bird_debit_card_specializing_045 | bird | What kind of currency did the customer paid at 16:25… | ❌ | 0.17 | 0.00 |
| bird_debit_card_specializing_046 | bird | What segment did the customer have at 2012/8/23 21:2… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_047 | bird | How many transactions were paid in CZK in the mornin… | ❌ | 0.20 | 0.00 |
| bird_debit_card_specializing_048 | bird | For the earliest customer, what segment did he/she h… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_049 | bird | For the deal happened at 2012/8/24 12:42:00, which c… | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_050 | bird | What was the product id of the transaction happened … | ❌ | 0.12 | 0.00 |
| bird_debit_card_specializing_051 | bird | For the customer who paid 124.05 in 2012/8/24, how m… | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_052 | bird | For all the transactions happened during 8:00-9:00 i… | ❌ | 0.12 | 0.00 |
| bird_debit_card_specializing_053 | bird | There's one customer spent 214582.17 in the June of … | ❌ | 0.17 | 0.00 |
| bird_debit_card_specializing_054 | bird | Which country was the card owner of No.667467 in? | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_055 | bird | What's the nationality of the customer who spent 548… | ❌ | 0.12 | 0.00 |
| bird_debit_card_specializing_056 | bird | What is the percentage of the customers who used EUR… | ✅ | 1.00 | 0.67 |
| bird_debit_card_specializing_057 | bird | For the customer who paid 634.8 in 2012/8/25, what w… | ❌ | 0.12 | 0.00 |
| bird_debit_card_specializing_058 | bird | Which gas station has the highest amount of revenue? | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_059 | bird | What is the percentage of "premium" against the over… | ❌ | 0.00 | 0.00 |
| bird_debit_card_specializing_060 | bird | What is the amount spent by customer "38508" at the … | ❌ | 0.12 | 0.00 |
| bird_debit_card_specializing_061 | bird | Which are the top five best selling products? Please… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_062 | bird | Who is the top spending customer and how much is the… | ❌ | 0.14 | 0.00 |
| bird_debit_card_specializing_063 | bird | Which country had the gas station that sold the most… | ❌ | 0.11 | 0.00 |
| bird_debit_card_specializing_064 | bird | For all the people who paid more than 29.00 per unit… | ❌ | 0.12 | 0.00 |
