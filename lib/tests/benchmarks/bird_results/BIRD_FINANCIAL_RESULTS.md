# BIRD — financial — Results

**Conditions:** `keyword`  
**Queries:** 106  
**Last run:** 2026-08-25 09:35 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 57% |
| Hit@3 | 58% |
| Hit@5 | 66% |
| MRR | 63% |

```
Hit@5 (% of 106 queries)

  keyword         ██████████░░░░░   66%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.383 |
| P@3 | 0.546 |
| R@3 | 0.322 |
| F1@5 | 0.406 |
| P@5 | 0.527 |
| R@5 | 0.358 |
| F1@10 | 0.498 |
| P@10 | 0.384 |
| R@10 | 0.845 |
| F1@Ideal-K | 0.385 |
| P@Ideal-K | 0.549 |
| R@Ideal-K | 0.322 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 106 | 57% | 0.63 | 0.38 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_financial_001 | bird | How many accounts who choose issuance after transact… | ❌ | 0.14 | 0.00 |
| bird_financial_002 | bird | How many accounts who have region in Prague are elig… | ❌ | 0.17 | 0.00 |
| bird_financial_003 | bird | The average unemployment ratio of 1995 and 1996, whi… | ❌ | 0.11 | 0.00 |
| bird_financial_004 | bird | List out the no. of districts that have female avera… | ❌ | 0.11 | 0.00 |
| bird_financial_005 | bird | How many male customers who are living in North Bohe… | ❌ | 0.11 | 0.00 |
| bird_financial_006 | bird | List out the account numbers of female clients who a… | ✅ | 1.00 | 0.40 |
| bird_financial_007 | bird | List out the account numbers of clients who are youn… | ✅ | 1.00 | 0.40 |
| bird_financial_008 | bird | How many customers who choose statement of weekly is… | ❌ | 0.20 | 0.00 |
| bird_financial_009 | bird | List out the id number of client who choose statemen… | ❌ | 0.17 | 0.00 |
| bird_financial_010 | bird | Among the accounts who have approved loan date in 19… | ✅ | 1.00 | 0.67 |
| bird_financial_011 | bird | Among the accounts who have loan validity more than … | ✅ | 1.00 | 1.00 |
| bird_financial_012 | bird | Among the account opened, how many female customers … | ❌ | 0.10 | 0.00 |
| bird_financial_013 | bird | List out the accounts who have the earliest trading … | ❌ | 0.00 | 0.00 |
| bird_financial_014 | bird | State different accounts who have account opening da… | ✅ | 1.00 | 0.67 |
| bird_financial_015 | bird | Which client issued his/her card in 1994/3/3, give h… | ✅ | 1.00 | 0.80 |
| bird_financial_016 | bird | The transaction of 840 USD happened in 1998/10/14, w… | ✅ | 1.00 | 0.67 |
| bird_financial_017 | bird | There was a loan approved in 1994/8/25, where was th… | ✅ | 1.00 | 1.00 |
| bird_financial_018 | bird | What is the biggest amount of transaction that the c… | ✅ | 1.00 | 0.33 |
| bird_financial_019 | bird | What is the gender of the oldest client who opened h… | ❌ | 0.50 | 0.50 |
| bird_financial_020 | bird | For the client who applied the biggest loan, what wa… | ❌ | 0.10 | 0.00 |
| bird_financial_021 | bird | How many clients opened their accounts in Jesenik br… | ❌ | 0.11 | 0.00 |
| bird_financial_022 | bird | What is the disposition id of the client who made 51… | ❌ | 0.17 | 0.00 |
| bird_financial_023 | bird | How many accounts were opened in Litomerice in 1996? | ❌ | 0.14 | 0.00 |
| bird_financial_024 | bird | For the female client who was born in 1976/1/29, whi… | ✅ | 1.00 | 1.00 |
| bird_financial_025 | bird | For the client who applied 98832 USD loan in 1996/1/… | ✅ | 1.00 | 0.67 |
| bird_financial_026 | bird | For the first client who opened his/her account in P… | ✅ | 1.00 | 0.50 |
| bird_financial_027 | bird | For the branch which located in the south Bohemia wi… | ❌ | 0.11 | 0.00 |
| bird_financial_028 | bird | For the client whose loan was approved first in 1993… | ✅ | 1.00 | 0.67 |
| bird_financial_029 | bird | What is the percentage of loan amount that has been … | ✅ | 1.00 | 1.00 |
| bird_financial_030 | bird | For loan amount less than USD100,000, what is the pe… | ✅ | 1.00 | 1.00 |
| bird_financial_031 | bird | For accounts in 1993 with statement issued after tra… | ✅ | 1.00 | 1.00 |
| bird_financial_032 | bird | From Year 1995 to 2000, who are the accounts holders… | ✅ | 1.00 | 0.67 |
| bird_financial_033 | bird | List account ID and account opening date for account… | ✅ | 1.00 | 0.67 |
| bird_financial_034 | bird | State the district and region for loan ID '4990'. | ✅ | 1.00 | 0.80 |
| bird_financial_035 | bird | Provide the account ID, district and region for loan… | ✅ | 1.00 | 1.00 |
| bird_financial_036 | bird | List the loan ID, district and average salary for lo… | ✅ | 1.00 | 0.80 |
| bird_financial_037 | bird | For loans contracts which are still running where cl… | ✅ | 1.00 | 0.40 |
| bird_financial_038 | bird | Calculate the percentage of account from 'Decin' dis… | ✅ | 1.00 | 1.00 |
| bird_financial_039 | bird | List the account IDs with monthly issuance of statem… | ✅ | 1.00 | 1.00 |
| bird_financial_040 | bird | List the top nine districts, by descending order, fr… | ❌ | 0.10 | 0.00 |
| bird_financial_041 | bird | Which are the top ten withdrawals (non-credit card) … | ✅ | 1.00 | 0.50 |
| bird_financial_042 | bird | How many of the account holders in South Bohemia sti… | ❌ | 0.14 | 0.00 |
| bird_financial_043 | bird | Which district has highest active loan? | ✅ | 1.00 | 0.50 |
| bird_financial_044 | bird | What is the average loan amount by male borrowers? | ✅ | 1.00 | 0.40 |
| bird_financial_045 | bird | In 1996, which districts have the highest unemployme… | ✅ | 1.00 | 1.00 |
| bird_financial_046 | bird | In the branch where the largest number of crimes wer… | ❌ | 0.14 | 0.00 |
| bird_financial_047 | bird | After making a credit card withdrawal, how many acco… | ❌ | 0.12 | 0.00 |
| bird_financial_048 | bird | Between 1/1/1995 and 12/31/1997, how many loans in t… | ✅ | 1.00 | 0.67 |
| bird_financial_049 | bird | How many accounts have running contracts in Branch l… | ❌ | 0.17 | 0.00 |
| bird_financial_050 | bird | In the branch where the second-highest number of cri… | ❌ | 0.11 | 0.00 |
| bird_financial_051 | bird | How many high-level credit cards have "OWNER" type o… | ❌ | 0.12 | 0.00 |
| bird_financial_052 | bird | How many accounts are there in the district of "Pise… | ✅ | 1.00 | 0.67 |
| bird_financial_053 | bird | Which districts have transactions greater than USS$1… | ❌ | 0.14 | 0.00 |
| bird_financial_054 | bird | Which accounts placed orders for household payment i… | ❌ | 0.14 | 0.00 |
| bird_financial_055 | bird | What are the accounts that have gold credit cards? | ❌ | 0.20 | 0.00 |
| bird_financial_056 | bird | How much is the average amount in credit card made b… | ✅ | 1.00 | 0.67 |
| bird_financial_057 | bird | Who are the account holder identification numbers wh… | ✅ | 1.00 | 0.50 |
| bird_financial_058 | bird | Who are the female account holders who own credit ca… | ✅ | 1.00 | 0.33 |
| bird_financial_059 | bird | How many female clients' accounts are in the region … | ❌ | 0.11 | 0.00 |
| bird_financial_060 | bird | Please list the accounts whose district is Tabor tha… | ✅ | 1.00 | 0.50 |
| bird_financial_061 | bird | Please list the account types that are not eligible … | ✅ | 1.00 | 0.80 |
| bird_financial_062 | bird | How many accounts in North Bohemia has made a transa… | ❌ | 0.12 | 0.00 |
| bird_financial_063 | bird | Please list the name of the districts with accounts … | ❌ | 0.14 | 0.00 |
| bird_financial_064 | bird | What is the average number of crimes committed in 19… | ❌ | 0.14 | 0.00 |
| bird_financial_065 | bird | How many 'classic' cards are eligible for loan? | ❌ | 0.20 | 0.00 |
| bird_financial_066 | bird | How many male clients in 'Hl.m. Praha' district? | ❌ | 0.11 | 0.00 |
| bird_financial_067 | bird | How many percent of 'Gold' cards were issued prior t… | ❌ | 0.11 | 0.00 |
| bird_financial_068 | bird | Who is the owner of the account with the largest loa… | ✅ | 1.00 | 0.80 |
| bird_financial_069 | bird | What is the number of committed crimes in 1995 in th… | ✅ | 1.00 | 1.00 |
| bird_financial_070 | bird | What is the district Id of the account that placed t… | ✅ | 1.00 | 1.00 |
| bird_financial_071 | bird | List all the withdrawals in cash transactions that t… | ✅ | 1.00 | 0.40 |
| bird_financial_072 | bird | Among the weekly issuance accounts, how many have a … | ✅ | 1.00 | 0.67 |
| bird_financial_073 | bird | What type of credit card does the client with the id… | ✅ | 1.00 | 0.80 |
| bird_financial_074 | bird | What is the region of the client with the id 3541 fr… | ✅ | 1.00 | 0.67 |
| bird_financial_075 | bird | Which district has the most accounts with loan contr… | ✅ | 1.00 | 0.80 |
| bird_financial_076 | bird | Who placed the order with the id 32423? | ✅ | 1.00 | 0.40 |
| bird_financial_077 | bird | Please list all the transactions made by accounts fr… | ✅ | 1.00 | 0.50 |
| bird_financial_078 | bird | How many of the accounts are from Jesenik district? | ❌ | 0.14 | 0.00 |
| bird_financial_079 | bird | List all the clients' IDs whose junior credit cards … | ❌ | 0.17 | 0.00 |
| bird_financial_080 | bird | What percentage of clients who opened their accounts… | ✅ | 1.00 | 0.67 |
| bird_financial_081 | bird | What was the growth rate of the total amount of loan… | ✅ | 1.00 | 0.40 |
| bird_financial_082 | bird | How many credit card withdrawals were recorded after… | ❌ | 0.00 | 0.00 |
| bird_financial_083 | bird | What was the difference in the number of crimes comm… | ❌ | 0.11 | 0.00 |
| bird_financial_084 | bird | How many owner and disponent dispositions are there … | ❌ | 0.14 | 0.00 |
| bird_financial_085 | bird | How often does account number 3 request an account s… | ✅ | 1.00 | 0.67 |
| bird_financial_086 | bird | What year was account owner number 130 born? | ✅ | 1.00 | 0.50 |
| bird_financial_087 | bird | How many accounts have an owner disposition and requ… | ❌ | 0.20 | 0.00 |
| bird_financial_088 | bird | What is the amount of debt that client number 992 ha… | ✅ | 1.00 | 0.40 |
| bird_financial_089 | bird | What is the sum that client number 4's account has f… | ✅ | 1.00 | 0.67 |
| bird_financial_090 | bird | Which kind of credit card does client number 9 posse… | ✅ | 1.00 | 0.80 |
| bird_financial_091 | bird | How much, in total, did client number 617 pay for al… | ✅ | 1.00 | 0.40 |
| bird_financial_092 | bird | Please provide a list of clients who were born betwe… | ✅ | 1.00 | 0.40 |
| bird_financial_093 | bird | Please provide the IDs of the 3 female clients with … | ❌ | 0.20 | 0.00 |
| bird_financial_094 | bird | How many male customers who were born between 1974 a… | ❌ | 0.20 | 0.00 |
| bird_financial_095 | bird | How many accounts in Beroun were opened after 1996? | ❌ | 0.14 | 0.00 |
| bird_financial_096 | bird | How many female customers have a junior credit card? | ❌ | 0.20 | 0.00 |
| bird_financial_097 | bird | What proportion of customers who have accounts at th… | ❌ | 0.11 | 0.00 |
| bird_financial_098 | bird | What percentage of male clients request for weekly s… | ❌ | 0.20 | 0.00 |
| bird_financial_099 | bird | How many clients who choose statement of weekly issu… | ❌ | 0.20 | 0.00 |
| bird_financial_100 | bird | Among the accounts who have loan validity more than … | ✅ | 1.00 | 1.00 |
| bird_financial_101 | bird | Name the account numbers of female clients who are o… | ✅ | 1.00 | 0.40 |
| bird_financial_102 | bird | How many clients who were born in 1920 stay in east … | ❌ | 0.11 | 0.00 |
| bird_financial_103 | bird | How many loan accounts are for pre-payment of durati… | ✅ | 1.00 | 0.67 |
| bird_financial_104 | bird | What is the average amount of loan which are still o… | ✅ | 1.00 | 0.67 |
| bird_financial_105 | bird | List all ID and district for clients that can only h… | ✅ | 1.00 | 0.50 |
| bird_financial_106 | bird | Provide the IDs and age of the client with high leve… | ✅ | 1.00 | 0.50 |
