# BIRD — california_schools — Results

**Conditions:** `keyword`  
**Queries:** 89  
**Last run:** 2026-08-25 09:35 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 29% |
| Hit@3 | 42% |
| Hit@5 | 49% |
| MRR | 37% |

```
Hit@5 (% of 89 queries)

  keyword         ███████░░░░░░░░   49%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.326 |
| P@3 | 0.416 |
| R@3 | 0.281 |
| F1@5 | 0.390 |
| P@5 | 0.483 |
| R@5 | 0.343 |
| F1@10 | 0.435 |
| P@10 | 0.438 |
| R@10 | 0.500 |
| F1@Ideal-K | 0.255 |
| P@Ideal-K | 0.326 |
| R@Ideal-K | 0.219 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 89 | 29% | 0.37 | 0.25 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_california_schools_001 | bird | What is the highest eligible free rate for K-12 stud… | ❌ | 0.00 | 0.00 |
| bird_california_schools_002 | bird | Please list the lowest three eligible free rates for… | ❌ | 0.00 | 0.00 |
| bird_california_schools_003 | bird | Please list the zip code of all the charter schools … | ❌ | 0.50 | 0.67 |
| bird_california_schools_004 | bird | What is the unabbreviated mailing street address of … | ❌ | 0.33 | 0.00 |
| bird_california_schools_005 | bird | Please list the phone numbers of the direct charter-… | ✅ | 1.00 | 0.67 |
| bird_california_schools_006 | bird | How many schools with an average score in Math great… | ✅ | 1.00 | 0.67 |
| bird_california_schools_007 | bird | Among the schools with the SAT test takers of over 5… | ✅ | 1.00 | 0.67 |
| bird_california_schools_008 | bird | What is the phone number of the school that has the … | ❌ | 0.00 | 0.00 |
| bird_california_schools_009 | bird | What is the number of SAT test takers of the schools… | ❌ | 0.25 | 0.00 |
| bird_california_schools_010 | bird | Among the schools with the average score in Math ove… | ❌ | 0.20 | 0.00 |
| bird_california_schools_011 | bird | For the school with the highest average score in Rea… | ❌ | 0.33 | 0.00 |
| bird_california_schools_012 | bird | Please list the codes of the schools with a total en… | ✅ | 1.00 | 0.67 |
| bird_california_schools_013 | bird | Among the schools with an SAT excellence rate of ove… | ❌ | 0.00 | 0.00 |
| bird_california_schools_014 | bird | Please list the phone numbers of the schools with th… | ✅ | 1.00 | 0.67 |
| bird_california_schools_015 | bird | List the top five schools, by descending order, from… | ❌ | 0.00 | 0.00 |
| bird_california_schools_016 | bird | Which active district has the highest average score … | ❌ | 0.12 | 0.00 |
| bird_california_schools_017 | bird | How many schools in merged Alameda have number of te… | ✅ | 1.00 | 0.67 |
| bird_california_schools_018 | bird | Rank schools by their average score in Writing where… | ✅ | 1.00 | 0.67 |
| bird_california_schools_019 | bird | How many schools in Fresno (directly funded) have nu… | ❌ | 0.17 | 0.00 |
| bird_california_schools_020 | bird | What is the phone number of the school that has the … | ❌ | 0.00 | 0.00 |
| bird_california_schools_021 | bird | How many schools in Amador which the Low Grade is 9 … | ❌ | 0.33 | 0.00 |
| bird_california_schools_022 | bird | In Los Angeles how many schools have more than 500 f… | ❌ | 0.10 | 0.00 |
| bird_california_schools_023 | bird | Which school in Contra Costa has the highest number … | ❌ | 0.00 | 0.00 |
| bird_california_schools_024 | bird | List the names of schools with more than 30 differen… | ✅ | 1.00 | 0.67 |
| bird_california_schools_025 | bird | Give the names of the schools with the percent eligi… | ❌ | 0.00 | 0.00 |
| bird_california_schools_026 | bird | Name schools in Riverside which the average of avera… | ❌ | 0.00 | 0.00 |
| bird_california_schools_027 | bird | State the names and full communication address of hi… | ✅ | 1.00 | 0.67 |
| bird_california_schools_028 | bird | What is the average score in writing for the schools… | ❌ | 0.50 | 0.67 |
| bird_california_schools_029 | bird | Consider the average difference between K-12 enrollm… | ✅ | 1.00 | 0.67 |
| bird_california_schools_030 | bird | When did the first-through-twelfth-grade school with… | ❌ | 0.00 | 0.00 |
| bird_california_schools_031 | bird | Which cities have the top 5 lowest enrollment number… | ❌ | 0.12 | 0.00 |
| bird_california_schools_032 | bird | What is the eligible free rate of the 10th and 11th … | ❌ | 0.00 | 0.00 |
| bird_california_schools_033 | bird | What is the eligible free or reduced price meal rate… | ❌ | 0.20 | 0.00 |
| bird_california_schools_034 | bird | If there are any, what are the websites address of t… | ❌ | 0.33 | 0.00 |
| bird_california_schools_035 | bird | What is the free rate for students between the ages … | ❌ | 0.00 | 0.00 |
| bird_california_schools_036 | bird | What is the administrator's email address of the cha… | ❌ | 0.00 | 0.00 |
| bird_california_schools_037 | bird | Under whose administration is the school with the hi… | ❌ | 0.10 | 0.00 |
| bird_california_schools_038 | bird | What is the complete address of the school with the … | ❌ | 0.00 | 0.00 |
| bird_california_schools_039 | bird | What are the webpages for the Los Angeles County sch… | ❌ | 0.00 | 0.00 |
| bird_california_schools_040 | bird | What is the average number of test takers from Fresn… | ✅ | 1.00 | 0.67 |
| bird_california_schools_041 | bird | What is the telephone number for the school with the… | ❌ | 0.10 | 0.00 |
| bird_california_schools_042 | bird | List the names of virtual schools that are among the… | ✅ | 1.00 | 0.67 |
| bird_california_schools_043 | bird | What is the type of education offered in the school … | ❌ | 0.00 | 0.00 |
| bird_california_schools_044 | bird | What is the average math score of the school with th… | ❌ | 0.00 | 0.00 |
| bird_california_schools_045 | bird | What is the average writing score of the school who … | ❌ | 0.00 | 0.00 |
| bird_california_schools_046 | bird | What is the average writing score of each of the sch… | ✅ | 1.00 | 0.67 |
| bird_california_schools_047 | bird | Which state special schools have the highest number … | ✅ | 1.00 | 0.67 |
| bird_california_schools_048 | bird | What is the monthly average number of schools that o… | ❌ | 0.50 | 0.00 |
| bird_california_schools_049 | bird | What is the ratio of merged Unified School District … | ✅ | 1.00 | 1.00 |
| bird_california_schools_050 | bird | Which different county has the most number of closed… | ❌ | 0.00 | 0.00 |
| bird_california_schools_051 | bird | What is the postal street address for the school wit… | ❌ | 0.00 | 0.00 |
| bird_california_schools_052 | bird | In which mailing street address can you find the sch… | ❌ | 0.00 | 0.00 |
| bird_california_schools_053 | bird | What is the total number of schools whose total SAT … | ✅ | 1.00 | 0.67 |
| bird_california_schools_054 | bird | How many test takers are there at the school/s whose… | ❌ | 0.20 | 0.00 |
| bird_california_schools_055 | bird | Please specify all of the schools and their related … | ✅ | 1.00 | 1.00 |
| bird_california_schools_056 | bird | Of the schools with a mailing state address in Calif… | ✅ | 1.00 | 1.00 |
| bird_california_schools_057 | bird | Of all the schools with a mailing state address in C… | ✅ | 1.00 | 1.00 |
| bird_california_schools_058 | bird | What is the phone number and extension number for th… | ❌ | 0.00 | 0.00 |
| bird_california_schools_059 | bird | What is the phone number and extension number for th… | ❌ | 0.00 | 0.00 |
| bird_california_schools_060 | bird | What is the website for the schools under the admini… | ✅ | 1.00 | 1.00 |
| bird_california_schools_061 | bird | What are the websites for all the partially virtual … | ✅ | 1.00 | 1.00 |
| bird_california_schools_062 | bird | How many chartered schools located in the city of Hi… | ✅ | 1.00 | 1.00 |
| bird_california_schools_063 | bird | What is the total number of non-chartered schools in… | ❌ | 0.20 | 0.00 |
| bird_california_schools_064 | bird | In chartered schools with charter number 00D2, what … | ❌ | 0.25 | 0.00 |
| bird_california_schools_065 | bird | What is the total number of schools with a mailing c… | ❌ | 0.50 | 0.00 |
| bird_california_schools_066 | bird | What is the ratio in percentage of Santa Clara Count… | ❌ | 0.33 | 0.00 |
| bird_california_schools_067 | bird | Between 1/1/2000 to 12/31/2005, how many directly fu… | ✅ | 1.00 | 1.00 |
| bird_california_schools_068 | bird | What is the total amount of Community College Distri… | ❌ | 0.11 | 0.00 |
| bird_california_schools_069 | bird | Which county reported the most number of school clos… | ❌ | 0.00 | 0.00 |
| bird_california_schools_070 | bird | Please provide the National Center for Educational S… | ❌ | 0.25 | 0.00 |
| bird_california_schools_071 | bird | How many active and closed District Community Day Sc… | ✅ | 1.00 | 1.00 |
| bird_california_schools_072 | bird | What is the district code for the School that does n… | ❌ | 0.00 | 0.00 |
| bird_california_schools_073 | bird | How many students from the ages of 5 to 17 are enrol… | ❌ | 0.00 | 0.00 |
| bird_california_schools_074 | bird | What is the free or reduced price meal count for age… | ❌ | 0.00 | 0.00 |
| bird_california_schools_075 | bird | What is the lowest grade for the District Special Ed… | ❌ | 0.00 | 0.00 |
| bird_california_schools_076 | bird | What is the educational level name for the schools w… | ❌ | 0.33 | 0.00 |
| bird_california_schools_077 | bird | What is the city location of the high school level s… | ❌ | 0.00 | 0.00 |
| bird_california_schools_078 | bird | Which schools served a grade span of Kindergarten to… | ❌ | 0.17 | 0.00 |
| bird_california_schools_079 | bird | What is the most common type of grade span served in… | ❌ | 0.00 | 0.00 |
| bird_california_schools_080 | bird | Between San Diego and Santa Barbara, which county of… | ✅ | 1.00 | 1.00 |
| bird_california_schools_081 | bird | What is the school type of the school with the highe… | ❌ | 0.00 | 0.00 |
| bird_california_schools_082 | bird | In which city can you find the school in the state o… | ❌ | 0.00 | 0.00 |
| bird_california_schools_083 | bird | What is the grade span offered in the school with th… | ❌ | 0.00 | 0.00 |
| bird_california_schools_084 | bird | Of the schools that offers a magnet program serving … | ✅ | 1.00 | 0.67 |
| bird_california_schools_085 | bird | What are the two most common first names among the s… | ❌ | 0.00 | 0.00 |
| bird_california_schools_086 | bird | What is the Percent (%) Eligible Free (K-12) in the … | ❌ | 0.00 | 0.00 |
| bird_california_schools_087 | bird | What is the administrator's last name that oversees … | ❌ | 0.00 | 0.00 |
| bird_california_schools_088 | bird | What are the valid e-mail addresses of the administr… | ❌ | 0.50 | 0.67 |
| bird_california_schools_089 | bird | What is the administrator's email address for the sc… | ❌ | 0.00 | 0.00 |
