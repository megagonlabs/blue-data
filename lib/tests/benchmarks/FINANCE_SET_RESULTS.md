# Finance Set Retrieval Benchmark — Results

**Conditions:** `keyword`  
**Queries:** 80  
**Last run:** 2026-08-25 08:47 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 28% |
| Hit@3 | 34% |
| Hit@5 | 59% |
| MRR | 41% |

```
Hit@5 (% of 80 queries)

  keyword         █████████░░░░░░   59%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff — directly comparable to MEW.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.175 |
| P@3 | 0.219 |
| R@3 | 0.159 |
| F1@5 | 0.319 |
| P@5 | 0.331 |
| R@5 | 0.364 |
| F1@10 | 0.387 |
| P@10 | 0.270 |
| R@10 | 0.847 |
| F1@Ideal-K | 0.166 |
| P@Ideal-K | 0.212 |
| R@Ideal-K | 0.149 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| aggregation | 12 | 25% | 0.43 | 0.25 |
| attribute | 10 | 40% | 0.47 | 0.20 |
| concept | 13 | 31% | 0.42 | 0.14 |
| filter | 12 | 8% | 0.23 | 0.00 |
| join | 13 | 54% | 0.66 | 0.33 |
| schema | 10 | 20% | 0.37 | 0.23 |
| temporal | 10 | 10% | 0.25 | 0.00 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| fin_disc_01 | filter | How many clients defaulted on their loans? | ❌ | 0.17 | 0.00 |
| fin_disc_02 | aggregation | What is the average monthly payment amount for activ… | ❌ | 0.12 | 0.00 |
| fin_disc_03 | join | Which district has the highest average loan amount? | ✅ | 1.00 | 0.67 |
| fin_disc_04 | filter | How many transactions were cash withdrawals? | ❌ | 0.25 | 0.00 |
| fin_disc_05 | concept | What is the current account balance for each client? | ❌ | 0.33 | 0.00 |
| fin_disc_06 | aggregation | Which accounts have more than one hundred transactio… | ❌ | 0.25 | 0.00 |
| fin_disc_07 | concept | What is the total amount paid as pension income acro… | ✅ | 1.00 | 0.00 |
| fin_disc_08 | concept | How old is the youngest client at the bank? | ✅ | 1.00 | 1.00 |
| fin_disc_09 | join | Which accounts belong to clients living in the Pragu… | ❌ | 0.20 | 0.00 |
| fin_disc_10 | filter | What percentage of loans are fully repaid with no is… | ❌ | 0.17 | 0.00 |
| fin_disc_11 | join | What is the average loan duration in months grouped … | ✅ | 1.00 | 0.50 |
| fin_disc_12 | aggregation | How many distinct external banks received wire trans… | ❌ | 0.25 | 0.00 |
| fin_disc_13 | temporal | How many loans were issued in each calendar year? | ❌ | 0.17 | 0.00 |
| fin_disc_14 | concept | What is the maximum outstanding debt amount currentl… | ✅ | 1.00 | 0.00 |
| fin_disc_15 | filter | Which accounts receive their statements on a monthly… | ❌ | 0.12 | 0.00 |
| fin_disc_16 | aggregation | How many male versus female clients does the bank ha… | ❌ | 0.12 | 0.00 |
| fin_disc_17 | temporal | What is the average transaction amount per calendar … | ✅ | 1.00 | 0.00 |
| fin_disc_18 | concept | What is the total amount paid for insurance across a… | ✅ | 1.00 | 0.00 |
| fin_disc_19 | join | Which clients have an account in one district but li… | ❌ | 0.50 | 0.50 |
| fin_disc_20 | join | What is the total loan amount taken out by clients i… | ✅ | 1.00 | 0.50 |
| fin_disc_21 | aggregation | What is the total number of transaction records in t… | ❌ | 0.25 | 0.00 |
| fin_disc_22 | aggregation | How many distinct accounts have taken out at least o… | ❌ | 0.17 | 0.00 |
| fin_disc_23 | filter | Which transactions are debits — money leaving the ac… | ❌ | 0.25 | 0.00 |
| fin_disc_24 | filter | Which loans are currently active with no repayment p… | ❌ | 0.17 | 0.00 |
| fin_disc_25 | temporal | How many bank accounts were opened each year? | ❌ | 0.11 | 0.00 |
| fin_disc_26 | temporal | Which loans were issued most recently? | ❌ | 0.17 | 0.00 |
| fin_disc_27 | temporal | How many transactions occurred each calendar month? | ❌ | 0.25 | 0.00 |
| fin_disc_28 | concept | Which field in the transaction table indicates money… | ❌ | 0.25 | 0.00 |
| fin_disc_29 | concept | What column stores a client's geographic region? | ❌ | 0.20 | 0.00 |
| fin_disc_30 | join | What is the average loan amount for male versus fema… | ✅ | 1.00 | 0.50 |
| fin_disc_31 | join | Which district has the most bank accounts opened? | ✅ | 1.00 | 0.67 |
| fin_disc_32 | join | How many loans are held by female clients? | ❌ | 0.17 | 0.00 |
| fin_disc_33 | join | What is the total inflow transaction volume per acco… | ❌ | 0.25 | 0.00 |
| fin_disc_34 | schema | What data do we store about each bank client? | ❌ | 0.12 | 0.00 |
| fin_disc_35 | schema | Which entities in the database represent financial t… | ❌ | 0.25 | 0.00 |
| fin_disc_36 | schema | What information does a loan record contain? | ✅ | 1.00 | 1.00 |
| fin_disc_37 | attribute | Which column stores the monthly repayment amount for… | ❌ | 0.12 | 0.00 |
| fin_disc_38 | attribute | Where is the type of a bank transaction stored? | ✅ | 1.00 | 0.00 |
| fin_disc_39 | attribute | Which field encodes a client's date of birth? | ❌ | 0.10 | 0.00 |
| fin_disc_40 | attribute | What attribute stores the purpose code for a bank tr… | ❌ | 0.20 | 0.00 |
| fin_disc_41 | concept | What records the credit card type issued to a bank c… | ❌ | 0.50 | 0.00 |
| fin_disc_42 | concept | Which entity represents a recurring payment order se… | ❌ | 0.00 | 0.00 |
| fin_disc_43 | concept | What entity links a client to a bank account — recor… | ❌ | 0.00 | 0.80 |
| fin_disc_44 | concept | Which attribute stores the coded purpose of a standi… | ❌ | 0.00 | 0.00 |
| fin_disc_45 | concept | What field encodes both a client's birthdate and gen… | ❌ | 0.12 | 0.00 |
| fin_disc_46 | concept | Which field stores the destination account number fo… | ❌ | 0.00 | 0.00 |
| fin_disc_47 | filter | Which accounts are configured to receive bank statem… | ❌ | 0.11 | 0.00 |
| fin_disc_48 | filter | Which loans have a repayment term longer than 60 mon… | ❌ | 0.17 | 0.00 |
| fin_disc_49 | filter | Which credit cards were issued to junior tier client… | ❌ | 0.11 | 0.00 |
| fin_disc_50 | filter | Which transactions have a purpose code indicating a … | ❌ | 0.20 | 0.00 |
| fin_disc_51 | filter | Which transactions have no recorded operation type? | ✅ | 1.00 | 0.00 |
| fin_disc_52 | filter | Which standing payment orders involve transfers to a… | ❌ | 0.00 | 0.00 |
| fin_disc_53 | aggregation | What is the total number of transactions recorded fo… | ❌ | 0.25 | 0.00 |
| fin_disc_54 | aggregation | What is the average loan amount across all issued lo… | ✅ | 1.00 | 1.00 |
| fin_disc_55 | aggregation | Which district has the highest average salary? | ✅ | 1.00 | 1.00 |
| fin_disc_56 | aggregation | How many clients are registered in each district? | ❌ | 0.20 | 0.00 |
| fin_disc_57 | aggregation | How many transactions of each operation type exist i… | ❌ | 0.50 | 0.00 |
| fin_disc_58 | aggregation | What is the total loan amount outstanding for loans … | ✅ | 1.00 | 1.00 |
| fin_disc_59 | temporal | Which credit cards were issued most recently? | ❌ | 0.00 | 0.00 |
| fin_disc_60 | temporal | How many loans were issued in each calendar month? | ❌ | 0.17 | 0.00 |
| fin_disc_61 | temporal | How many clients were born in each decade? | ❌ | 0.14 | 0.00 |
| fin_disc_62 | temporal | Which calendar month had the highest total transacti… | ❌ | 0.25 | 0.00 |
| fin_disc_63 | temporal | When was the most recent transaction recorded for ea… | ❌ | 0.25 | 0.00 |
| fin_disc_64 | schema | What is the purpose of the disposition table — how d… | ❌ | 0.14 | 0.00 |
| fin_disc_65 | schema | Which tables are involved in tracking credit card is… | ❌ | 0.14 | 0.00 |
| fin_disc_66 | schema | How is the many-to-many relationship between clients… | ❌ | 0.12 | 0.00 |
| fin_disc_67 | schema | What is the structure of a standing payment order an… | ❌ | 0.12 | 0.00 |
| fin_disc_68 | schema | What demographic and economic data does the district… | ❌ | 0.50 | 0.00 |
| fin_disc_69 | schema | Which tables would you need to reconstruct the full … | ❌ | 0.25 | 0.29 |
| fin_disc_70 | schema | What tables and fields are needed to determine wheth… | ✅ | 1.00 | 1.00 |
| fin_disc_71 | attribute | Which column in the disposition table indicates whet… | ❌ | 0.10 | 0.00 |
| fin_disc_72 | attribute | Which field records when a credit card was issued to… | ❌ | 0.00 | 0.00 |
| fin_disc_73 | attribute | Which attribute in the account table stores the date… | ✅ | 1.00 | 1.00 |
| fin_disc_74 | attribute | Which column in the district table holds the unemplo… | ✅ | 1.00 | 1.00 |
| fin_disc_75 | attribute | Which field in the transaction table records the ext… | ✅ | 1.00 | 0.00 |
| fin_disc_76 | attribute | What column stores the average salary for residents … | ❌ | 0.20 | 0.00 |
| fin_disc_77 | join | Which clients have both a credit card and an active … | ❌ | 0.17 | 0.00 |
| fin_disc_78 | join | What is the total transaction volume for accounts wh… | ❌ | 0.25 | 0.00 |
| fin_disc_79 | join | Which district has the most credit cards issued to i… | ✅ | 1.00 | 0.40 |
| fin_disc_80 | join | What is the average account balance per geographic r… | ✅ | 1.00 | 0.50 |
