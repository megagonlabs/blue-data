# BIRD — thrombosis_prediction — Results

**Conditions:** `keyword`  
**Queries:** 163  
**Last run:** 2026-08-25 09:56 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 35% |
| Hit@3 | 37% |
| Hit@5 | 80% |
| MRR | 48% |

```
Hit@5 (% of 163 queries)

  keyword         ████████████░░░   80%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.268 |
| P@3 | 0.367 |
| R@3 | 0.223 |
| F1@5 | 0.503 |
| P@5 | 0.566 |
| R@5 | 0.487 |
| F1@10 | 0.773 |
| P@10 | 0.650 |
| R@10 | 0.994 |
| F1@Ideal-K | 0.265 |
| P@Ideal-K | 0.365 |
| R@Ideal-K | 0.217 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 163 | 35% | 0.48 | 0.26 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_thrombosis_prediction_001 | bird | Are there more in-patient or outpatient who were mal… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_002 | bird | What is the percentage of female patient were born a… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_003 | bird | For patient born between Year 1930 to 1940, how many… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_004 | bird | What is the ratio of outpatient to inpatient followe… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_005 | bird | What is the disease patient '30609' diagnosed with. … | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_006 | bird | State the sex and birthday of patient ID '163109'. W… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_007 | bird | List the patient ID, sex and birthday of patient wit… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_008 | bird | State the ID and age of patient with positive degree… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_009 | bird | For patients with severe degree of thrombosis, list … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_010 | bird | List all patients who were born in 1937 whose total … | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_011 | bird | For patient with albumin level lower than 3.5, list … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_012 | bird | What is the percentage of female patient had total p… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_013 | bird | For in-patient age 50 and above, what is their avera… | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_014 | bird | How many female patients who came at the hospital in… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_015 | bird | What was the age of the youngest patient when they i… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_016 | bird | How many of the patients with the most serious throm… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_017 | bird | What is the age gap between the youngest and oldest … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_018 | bird | What are the symptoms observed by the youngest patie… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_019 | bird | For the year that concluded on December 31, 1998, ho… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_020 | bird | The oldest SJS patient's medical laboratory work was… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_021 | bird | What is the ratio of male to female patients among a… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_022 | bird | How many patients hadn't undergone a medical examina… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_023 | bird | How many underage patients were examined during the … | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_024 | bird | How many male patients have elevated total bilirubin… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_025 | bird | What is the most common illness that doctors identif… | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_026 | bird | What is the average age of patients as of year 1999 … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_027 | bird | How old was the patient who had the highest hemoglob… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_028 | bird | What was the anti-nucleus antibody concentration lev… | ❌ | 0.12 | 0.00 |
| bird_thrombosis_prediction_029 | bird | Was the total cholesterol status for the patient id … | ❌ | 0.11 | 0.00 |
| bird_thrombosis_prediction_030 | bird | What was the gender of the first AORTITIS diagnosed … | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_031 | bird | For the patient who was diagnosed with SLE on 1994/2… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_032 | bird | Was the patient a man or a women whose ALT glutamic … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_033 | bird | For the patient who got the laboratory test of uric … | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_034 | bird | For the patient who first came to the hospital on 19… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_035 | bird | For the patient who was diagnosed SLE on 1997/1/27, … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_036 | bird | For the patient whose birthday was 1959/3/1, what sy… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_037 | bird | For the patient who was born on 1959/2/18, what is t… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_038 | bird | Lists all patients by ID who were diagnosed with Beh… | ❌ | 0.14 | 0.00 |
| bird_thrombosis_prediction_039 | bird | How many patients who were examined between 1987/7/6… | ❌ | 0.12 | 0.00 |
| bird_thrombosis_prediction_040 | bird | How many female patients born in 1964 were admitted … | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_041 | bird | What number of patients with a degree of thrombosis … | ❌ | 0.14 | 0.00 |
| bird_thrombosis_prediction_042 | bird | What percentage of patients with a proteinuria level… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_043 | bird | What percentage of male patients who first presented… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_044 | bird | List all patients who were followed up at the outpat… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_045 | bird | Excluding all P only ANA Pattern patients, how many … | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_046 | bird | What sex is the patient who in a medical examination… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_047 | bird | What is the average blood albumin level for female p… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_048 | bird | What is the most common sign of patients with SLE di… | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_049 | bird | When was the medical information on patient number 4… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_050 | bird | How many female patients were given an APS diagnosis… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_051 | bird | How many patients who underwent testing in 1997 had … | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_052 | bird | What proportion of patients who had signs of thrombo… | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_053 | bird | What percentage of patients who were born in 1980 an… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_054 | bird | How many male patients who underwent testing between… | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_055 | bird | How many patients who were female got white blood ce… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_056 | bird | How long did it take after patient number 821298 arr… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_057 | bird | Was the patient with the number 57266's uric acid wi… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_058 | bird | When is the laboratory examination of patient '48473… | ❌ | 0.33 | 0.00 |
| bird_thrombosis_prediction_059 | bird | List all patients with their sex and date of birthda… | ❌ | 0.11 | 0.00 |
| bird_thrombosis_prediction_060 | bird | Provide IDs for male patients with ALT glutamic pylv… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_061 | bird | Please provide the diagnosis of patients with ALT gl… | ❌ | 0.10 | 0.00 |
| bird_thrombosis_prediction_062 | bird | What is the average index of the lactate dehydrogena… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_063 | bird | Provide the ID and age of patient with lactate dehyd… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_064 | bird | For patients with alkaliphophatase (ALP) within norm… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_065 | bird | Name the ID of the patient who is born on the April … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_066 | bird | List ID, sex and date of birth of patient whose tota… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_067 | bird | For all female patient with total protein (TP) beyon… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_068 | bird | Sort in descending order all patients by birthday fo… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_069 | bird | For all patient born in 1982, state if their albumin… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_070 | bird | What is the percentage of the female patient whose u… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_071 | bird | For all patients with normal uric acid (UA), what is… | ❌ | 0.50 | 0.50 |
| bird_thrombosis_prediction_072 | bird | Provide all ID, sex and birthday of patients whose u… | ❌ | 0.14 | 0.00 |
| bird_thrombosis_prediction_073 | bird | Provide the ID, sex, birthday of all patients diagno… | ❌ | 0.14 | 0.00 |
| bird_thrombosis_prediction_074 | bird | How many male patients are are with creatinine index… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_075 | bird | Are there more male patients with creatinine not wit… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_076 | bird | What is the highest total bilirubin level recorded? … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_077 | bird | List and group all patients by sex for total bilirub… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_078 | bird | Who is the oldest patient with the highest total cho… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_079 | bird | What is the average age of the male patient with hig… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_080 | bird | Provide list of patients and their diagnosis with tr… | ❌ | 0.14 | 0.00 |
| bird_thrombosis_prediction_081 | bird | For all patients with triglyceride (TG) level beyond… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_082 | bird | List all outpatient within normal range of creatinin… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_083 | bird | For patient born between 1936-1956, how many male pa… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_084 | bird | Provide ID, sex and age of patient who has blood glu… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_085 | bird | List each patient's ID and blood glucose (GLU) index… | ❌ | 0.11 | 0.00 |
| bird_thrombosis_prediction_086 | bird | List the patient ID, sex and birthday who has abnorm… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_087 | bird | What are the patient's diagnosis for those who has l… | ❌ | 0.10 | 0.00 |
| bird_thrombosis_prediction_088 | bird | For all the female patient age 50 and above, who has… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_089 | bird | Among all outpatients, list out those have low hemog… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_090 | bird | Among the patients who were diagnosed with SLE, who … | ❌ | 0.12 | 0.00 |
| bird_thrombosis_prediction_091 | bird | Name the ID and age of patient with two or more labo… | ✅ | 1.00 | 1.00 |
| bird_thrombosis_prediction_092 | bird | From laboratory examinations in 1991, what is the av… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_093 | bird | For patients with abnormal platelet level, state the… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_094 | bird | For laboratory examinations take in 1984, list all p… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_095 | bird | For all patients who are older than 55 years old, wh… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_096 | bird | List all patients who first came to the hospital aft… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_097 | bird | For the examinations done after 1997/1/1, how many o… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_098 | bird | For the patients with an abnormal activated partial … | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_099 | bird | Among the male patients who have a normal level of w… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_100 | bird | How many patients born after 1980/1/1 have an abnorm… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_101 | bird | Please list the disease names of the patients that h… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_102 | bird | Which patient has a normal proteinuria level and is … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_103 | bird | How many patients with an Ig G higher than normal? | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_104 | bird | Among the patients with a normal Ig G level, how man… | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_105 | bird | For the patient who has the highest Ig A within the … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_106 | bird | How many patients with a normal Ig A level came to t… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_107 | bird | For the patients with an abnormal Ig M level, what i… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_108 | bird | How many patients with a abnormal C-reactive protein… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_109 | bird | Among the patients whose creatinine level is abnorma… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_110 | bird | How many patients with a normal Rhuematoid Factor ha… | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_111 | bird | Please list the diseases of the patients born after … | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_112 | bird | Please list the ID of the patient whose RF is normal… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_113 | bird | How many patients with a normal RF don't have thromb… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_114 | bird | How many patients with a normal level of complement … | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_115 | bird | Among the patients whose level of Hematoclit isn't n… | ✅ | 1.00 | 0.50 |
| bird_thrombosis_prediction_116 | bird | Among the patients have blood clots in veins, how ma… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_117 | bird | How many patients have a normal level of anti-ribonu… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_118 | bird | Which is the youngest patient with an abnormal anti-… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_119 | bird | Among the patients with normal anti-SM, how many of … | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_120 | bird | For the patients with an abnormal anti-SM, please li… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_121 | bird | Please list the IDs of the patients who had the exam… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_122 | bird | Among the patients who has a normal anti-scl70, how … | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_123 | bird | How many patients with a normal anti-SSA came to the… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_124 | bird | Which patient is the first patient with an abnormal … | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_125 | bird | How many patients have a normal anti-SSB and are dia… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_126 | bird | For the patients whose anti-SSB are normal, how many… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_127 | bird | Among the patients who has a normal level of anti-ce… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_128 | bird | For the patients who have an abnormal level of anti-… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_129 | bird | How many patients have a normal anti-DNA level, yet … | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_130 | bird | Of the patients with an normal level of IGG, how man… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_131 | bird | What is the percentage of patient who has a abnormal… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_132 | bird | How many male patients have their glutamic oxaloacet… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_133 | bird | Among the patients who have an abnormal level of glu… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_134 | bird | Please list the top three patients' birthdays with t… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_135 | bird | For the patients with the normal glutamic pylvic tra… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_136 | bird | For the patient with the highest lactate dehydrogena… | ❌ | 0.50 | 0.67 |
| bird_thrombosis_prediction_137 | bird | When is the latest patient's medical data recorded? … | ❌ | 0.50 | 0.67 |
| bird_thrombosis_prediction_138 | bird | For the patient with an abnormal alkaliphophatase le… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_139 | bird | Among the patients followed at the outpatient clinic… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_140 | bird | Please list the diagnosis of the patients whose tota… | ❌ | 0.14 | 0.00 |
| bird_thrombosis_prediction_141 | bird | For the patients who are diagnosed with SJS, how man… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_142 | bird | What is the examination date of the patient whose al… | ❌ | 0.11 | 0.00 |
| bird_thrombosis_prediction_143 | bird | How many male patients have a normal level of both a… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_144 | bird | What is the anti Cardiolipin antibody concentration … | ✅ | 1.00 | 0.50 |
| bird_thrombosis_prediction_145 | bird | What is the highest anti-nucleus antibody concentrat… | ✅ | 1.00 | 0.50 |
| bird_thrombosis_prediction_146 | bird | Please list the patient's ID whose creatinine level … | ❌ | 0.14 | 0.00 |
| bird_thrombosis_prediction_147 | bird | Among the patients whose total bilirubin is over the… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_148 | bird | What is the anti-nucleus antibody concentration of t… | ✅ | 1.00 | 0.50 |
| bird_thrombosis_prediction_149 | bird | For the patients whose total cholesterol is higher t… | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_150 | bird | Among the patients whose total cholesterol is within… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_151 | bird | Among the patients with the normal level of triglyce… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_152 | bird | What is the disease name of the patient who has the … | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_153 | bird | Please list the IDs of the patients with no thrombos… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_154 | bird | For the patients with a normal range of creatinine p… | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_155 | bird | When is the birthday of the oldest patient whose blo… | ✅ | 1.00 | 0.67 |
| bird_thrombosis_prediction_156 | bird | Among the patients with a normal blood glucose, how … | ❌ | 0.25 | 0.00 |
| bird_thrombosis_prediction_157 | bird | How many patients accepted to the hospital have a no… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_158 | bird | How many patients diagnosed with SLE have a normal w… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_159 | bird | Please list the patient's ID if he or she has an abn… | ❌ | 0.12 | 0.00 |
| bird_thrombosis_prediction_160 | bird | Among the patients who have a normal platelet level,… | ❌ | 0.17 | 0.00 |
| bird_thrombosis_prediction_161 | bird | Please list a patient's platelet level if it is with… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_162 | bird | For the male patients that have a normal prothrombin… | ❌ | 0.20 | 0.00 |
| bird_thrombosis_prediction_163 | bird | How many patients with severe thrombosis have a norm… | ❌ | 0.20 | 0.00 |
