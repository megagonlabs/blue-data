# BIRD — formula_1 — Results

**Conditions:** `keyword`  
**Queries:** 174  
**Last run:** 2026-08-25 09:35 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 36% |
| Hit@3 | 37% |
| Hit@5 | 37% |
| MRR | 40% |

```
Hit@5 (% of 174 queries)

  keyword         ██████░░░░░░░░░   37%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.271 |
| P@3 | 0.374 |
| R@3 | 0.228 |
| F1@5 | 0.251 |
| P@5 | 0.310 |
| R@5 | 0.234 |
| F1@10 | 0.269 |
| P@10 | 0.239 |
| R@10 | 0.465 |
| F1@Ideal-K | 0.264 |
| P@Ideal-K | 0.362 |
| R@Ideal-K | 0.223 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 174 | 36% | 0.40 | 0.26 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_formula_1_001 | bird | Please list the reference names of the drivers who a… | ✅ | 1.00 | 0.67 |
| bird_formula_1_002 | bird | What is the surname of the driver with the best lap … | ✅ | 1.00 | 0.67 |
| bird_formula_1_003 | bird | Please list the year during which the race is held o… | ✅ | 1.00 | 0.67 |
| bird_formula_1_004 | bird | Where can the introduction of the races held on Circ… | ✅ | 1.00 | 0.67 |
| bird_formula_1_005 | bird | Please give the name of the race held on the circuit… | ✅ | 1.00 | 0.67 |
| bird_formula_1_006 | bird | Please list the positions of the circuits built by t… | ❌ | 0.00 | 0.00 |
| bird_formula_1_007 | bird | How many races in the year 2010 are held on grand pr… | ✅ | 1.00 | 0.67 |
| bird_formula_1_008 | bird | Please give the names of the races held on the circu… | ✅ | 1.00 | 1.00 |
| bird_formula_1_009 | bird | What is the coordinates location of the circuits for… | ✅ | 1.00 | 0.67 |
| bird_formula_1_010 | bird | Where can I find the information about the races hel… | ✅ | 1.00 | 0.67 |
| bird_formula_1_011 | bird | Please list the time of the races held on Sepang Int… | ✅ | 1.00 | 0.67 |
| bird_formula_1_012 | bird | Give the coordinate position for Abu Dhabi Grand Pri… | ❌ | 0.00 | 0.00 |
| bird_formula_1_013 | bird | Which country is the constructor which got 1 point i… | ❌ | 0.00 | 0.00 |
| bird_formula_1_014 | bird | What's Bruno Senna's Q1 result in the qualifying rac… | ✅ | 1.00 | 0.67 |
| bird_formula_1_015 | bird | For the driver who had the Q2 time as 0:01:40 in the… | ✅ | 1.00 | 0.67 |
| bird_formula_1_016 | bird | What is his number of the driver who finished 0:01:5… | ✅ | 1.00 | 0.67 |
| bird_formula_1_017 | bird | For the Bahrain Grand Prix in 2007, how many drivers… | ✅ | 1.00 | 0.50 |
| bird_formula_1_018 | bird | Show me the season page of year when the race No. 90… | ❌ | 0.11 | 0.00 |
| bird_formula_1_019 | bird | For the race happened on 2015/11/29, how many driver… | ❌ | 0.11 | 0.00 |
| bird_formula_1_020 | bird | For all the drivers who finished the game in race No… | ✅ | 1.00 | 0.67 |
| bird_formula_1_021 | bird | Who was the player that got the lap time of 0:01:27 … | ❌ | 0.10 | 0.00 |
| bird_formula_1_022 | bird | For the driver who set the fastest lap speed in race… | ❌ | 0.10 | 0.00 |
| bird_formula_1_023 | bird | Where is Malaysian Grand Prix held? Give the locatio… | ❌ | 0.00 | 0.00 |
| bird_formula_1_024 | bird | For the constructor which got the highest point in t… | ❌ | 0.00 | 0.00 |
| bird_formula_1_025 | bird | What's Lucas di Grassi's Q1 result in the race No. 3… | ❌ | 0.14 | 0.00 |
| bird_formula_1_026 | bird | For the driver who had the Q2 time as 0:01:15 in rac… | ❌ | 0.00 | 0.00 |
| bird_formula_1_027 | bird | In the race No. 45, for the driver who had the Q3 ti… | ❌ | 0.00 | 0.00 |
| bird_formula_1_028 | bird | What is the actual finish time for Bruce McLaren in … | ❌ | 0.00 | 0.00 |
| bird_formula_1_029 | bird | Who finished second in the San Marino Grand Prix in … | ❌ | 0.12 | 0.00 |
| bird_formula_1_030 | bird | Show me the season page of year when the race No. 90… | ❌ | 0.11 | 0.00 |
| bird_formula_1_031 | bird | For the race happened in 2015/11/29, how many driver… | ❌ | 0.11 | 0.00 |
| bird_formula_1_032 | bird | For all the drivers who finished the game in race No… | ✅ | 1.00 | 0.67 |
| bird_formula_1_033 | bird | Who was the driver that got the best lap time in the… | ❌ | 0.10 | 0.00 |
| bird_formula_1_034 | bird | For the driver who set the fastest lap speed, what i… | ❌ | 0.10 | 0.00 |
| bird_formula_1_035 | bird | Paul di Resta was in the No. 853 race, what percent … | ❌ | 0.10 | 0.00 |
| bird_formula_1_036 | bird | For the drivers who took part in the race in 1983/7/… | ❌ | 0.11 | 0.00 |
| bird_formula_1_037 | bird | Which year was the first Singapore Grand Prix? | ❌ | 0.00 | 0.00 |
| bird_formula_1_038 | bird | How many races were there in 2005? Name all the race… | ✅ | 1.00 | 1.00 |
| bird_formula_1_039 | bird | List the names of all races that occurred in the ear… | ✅ | 1.00 | 1.00 |
| bird_formula_1_040 | bird | State the name and date of the last round of race in… | ❌ | 0.00 | 0.00 |
| bird_formula_1_041 | bird | Which year has the most number of races? | ❌ | 0.00 | 0.00 |
| bird_formula_1_042 | bird | Name the races in year 2017 that are not hosted in y… | ✅ | 1.00 | 1.00 |
| bird_formula_1_043 | bird | In which country was the first European Grand Prix h… | ❌ | 0.00 | 0.00 |
| bird_formula_1_044 | bird | When was the last f1 season whereby Brands Hatch hos… | ❌ | 0.10 | 0.00 |
| bird_formula_1_045 | bird | How many seasons has Silverstone Circuit hosted the … | ❌ | 0.10 | 0.00 |
| bird_formula_1_046 | bird | Name all drivers in the 2010 Singapore Grand Prix or… | ✅ | 1.00 | 0.50 |
| bird_formula_1_047 | bird | State the driver with the most points scored. Find h… | ❌ | 0.00 | 0.00 |
| bird_formula_1_048 | bird | Name the top 3 drivers and the points they scored in… | ✅ | 1.00 | 0.50 |
| bird_formula_1_049 | bird | What is the best lap time recorded? List the driver … | ❌ | 0.10 | 0.00 |
| bird_formula_1_050 | bird | What is the average lap time for Lewis Hamilton in t… | ❌ | 0.10 | 0.00 |
| bird_formula_1_051 | bird | Calculate the percentage whereby Hamilton was not at… | ❌ | 0.12 | 0.00 |
| bird_formula_1_052 | bird | Name the driver with the most winning. Mention his n… | ❌ | 0.00 | 0.00 |
| bird_formula_1_053 | bird | How old is the youngest Japanese driver? What is his… | ❌ | 0.12 | 0.00 |
| bird_formula_1_054 | bird | List circuits which host 4 f1 races from year 1990 t… | ✅ | 1.00 | 1.00 |
| bird_formula_1_055 | bird | List circuits in USA which hosted f1 races in 2006. … | ✅ | 1.00 | 1.00 |
| bird_formula_1_056 | bird | Name the races along with its circuit name and locat… | ✅ | 1.00 | 0.67 |
| bird_formula_1_057 | bird | Which race was Alex Yoong in when he was in track nu… | ❌ | 0.00 | 0.00 |
| bird_formula_1_058 | bird | How many times did Michael Schumacher won from races… | ✅ | 1.00 | 0.40 |
| bird_formula_1_059 | bird | State the race and year of race in which Michael Sch… | ❌ | 0.17 | 0.00 |
| bird_formula_1_060 | bird | What is Eddie Irvine's average points scored in year… | ❌ | 0.00 | 0.00 |
| bird_formula_1_061 | bird | Which was Lewis Hamilton first race? What was his po… | ❌ | 0.10 | 0.00 |
| bird_formula_1_062 | bird | List all races in 2017 and the hosting country order… | ✅ | 1.00 | 0.67 |
| bird_formula_1_063 | bird | What is the most laps f1 races had? Name the race, y… | ✅ | 1.00 | 0.50 |
| bird_formula_1_064 | bird | Among all European Grand Prix races, what is the per… | ✅ | 1.00 | 0.67 |
| bird_formula_1_065 | bird | What's the location coordinates of Silverstone Circu… | ❌ | 0.00 | 0.00 |
| bird_formula_1_066 | bird | Which of these circuits is located at a higher latit… | ✅ | 1.00 | 1.00 |
| bird_formula_1_067 | bird | What's the reference name of Marina Bay Street Circu… | ❌ | 0.00 | 0.00 |
| bird_formula_1_068 | bird | In which country can I find the circuit with the hig… | ❌ | 0.00 | 0.00 |
| bird_formula_1_069 | bird | How many drivers don't have a code? | ✅ | 1.00 | 1.00 |
| bird_formula_1_070 | bird | Which country is the oldest driver from? | ❌ | 0.11 | 0.00 |
| bird_formula_1_071 | bird | Please list the surnames of all the Italian drivers. | ❌ | 0.12 | 0.00 |
| bird_formula_1_072 | bird | Which website should I go to if I want to know more … | ❌ | 0.12 | 0.00 |
| bird_formula_1_073 | bird | What's Lewis Hamilton's reference name? | ❌ | 0.12 | 0.00 |
| bird_formula_1_074 | bird | Which circuit did the 2009 Spanish Grand Prix use? | ❌ | 0.10 | 0.00 |
| bird_formula_1_075 | bird | Please list all the years that Silverstone Circuit w… | ❌ | 0.10 | 0.00 |
| bird_formula_1_076 | bird | Please give more information about the Formula_1 rac… | ❌ | 0.33 | 0.00 |
| bird_formula_1_077 | bird | What time did the the 2010's Formula_1 race took pla… | ❌ | 0.00 | 0.00 |
| bird_formula_1_078 | bird | How many Formula_1 races took place on the circuits … | ❌ | 0.33 | 0.00 |
| bird_formula_1_079 | bird | Please list the exact dates on which a Formula_1 rac… | ❌ | 0.10 | 0.00 |
| bird_formula_1_080 | bird | Please give the link of the website that shows more … | ✅ | 1.00 | 0.67 |
| bird_formula_1_081 | bird | What's the fastest lap time ever in a race for Lewis… | ❌ | 0.00 | 0.00 |
| bird_formula_1_082 | bird | Which driver created the fastest lap speed in a Form… | ❌ | 0.00 | 0.00 |
| bird_formula_1_083 | bird | Which driver ranked the first in the Canadian Grand … | ❌ | 0.12 | 0.00 |
| bird_formula_1_084 | bird | Please list the Formula_1 races that Lewis Hamilton … | ❌ | 0.33 | 0.50 |
| bird_formula_1_085 | bird | In which Formula_1 race did Lewis Hamilton rank the … | ❌ | 0.11 | 0.00 |
| bird_formula_1_086 | bird | What was the fastest lap speed among all drivers in … | ❌ | 0.00 | 0.00 |
| bird_formula_1_087 | bird | In which years did Lewis Hamilton participate in a F… | ❌ | 0.12 | 0.00 |
| bird_formula_1_088 | bird | What was Lewis Hamilton's final rank in the 2008 Chi… | ❌ | 0.11 | 0.00 |
| bird_formula_1_089 | bird | Which driver was in the no. 4 grid formation when st… | ❌ | 0.10 | 0.00 |
| bird_formula_1_090 | bird | How many drivers managed to finish the race in the 2… | ❌ | 0.11 | 0.00 |
| bird_formula_1_091 | bird | Which was the fastest lap for Lewis Hamilton in the … | ❌ | 0.10 | 0.00 |
| bird_formula_1_092 | bird | What's the finish time for the driver who ranked sec… | ❌ | 0.00 | 0.00 |
| bird_formula_1_093 | bird | Who was the champion of 2008's Australian Grand Prix… | ❌ | 0.12 | 0.00 |
| bird_formula_1_094 | bird | How many drivers from the UN participated in the 200… | ✅ | 1.00 | 0.50 |
| bird_formula_1_095 | bird | Among the drivers that finished the race in the 2008… | ❌ | 0.11 | 0.00 |
| bird_formula_1_096 | bird | How many points did Lewis Hamilton get in total in a… | ❌ | 0.00 | 0.00 |
| bird_formula_1_097 | bird | What is the average fastest lap time in seconds for … | ❌ | 0.00 | 0.00 |
| bird_formula_1_098 | bird | What is the rate of drivers completing all the laps … | ❌ | 0.10 | 0.00 |
| bird_formula_1_099 | bird | How much faster in percentage is the champion than t… | ❌ | 0.11 | 0.00 |
| bird_formula_1_100 | bird | How many circuits are there in Adelaide, Australia? | ✅ | 1.00 | 1.00 |
| bird_formula_1_101 | bird | Please list the location coordinates of the US circu… | ❌ | 0.00 | 0.00 |
| bird_formula_1_102 | bird | How many British drivers were born after 1980? | ✅ | 1.00 | 1.00 |
| bird_formula_1_103 | bird | What are the maximum points of British constructors? | ❌ | 0.00 | 0.00 |
| bird_formula_1_104 | bird | Which constructor has the highest point? | ❌ | 0.00 | 0.00 |
| bird_formula_1_105 | bird | Please list the constructor names with 0 points at r… | ❌ | 0.00 | 0.00 |
| bird_formula_1_106 | bird | How many Japanese constructors have 0 points in 2 ra… | ✅ | 1.00 | 0.67 |
| bird_formula_1_107 | bird | Which constructors have been ranked 1? | ✅ | 1.00 | 0.67 |
| bird_formula_1_108 | bird | How many French constructors have a lap number of ov… | ✅ | 1.00 | 0.67 |
| bird_formula_1_109 | bird | Please calculate the race completion percentage of J… | ✅ | 1.00 | 0.50 |
| bird_formula_1_110 | bird | What is the average time in seconds of champion for … | ❌ | 0.00 | 0.00 |
| bird_formula_1_111 | bird | Which drivers born after 1975 have been ranked 2? Pl… | ✅ | 1.00 | 0.67 |
| bird_formula_1_112 | bird | How many Italian drivers haven't finished the race? | ✅ | 1.00 | 0.67 |
| bird_formula_1_113 | bird | Which driver has the fastest lap time? Please give t… | ❌ | 0.10 | 0.00 |
| bird_formula_1_114 | bird | What is the fastest lap number of the champion in 20… | ❌ | 0.00 | 0.00 |
| bird_formula_1_115 | bird | What is the average of fastest lap speed in the 2009… | ❌ | 0.00 | 0.00 |
| bird_formula_1_116 | bird | Which race has the shortest actual finishing time? P… | ❌ | 0.00 | 0.00 |
| bird_formula_1_117 | bird | From 2000 to 2005, what percentage of drivers who we… | ✅ | 1.00 | 0.50 |
| bird_formula_1_118 | bird | How many French drivers who obtain the laptime less … | ✅ | 1.00 | 0.67 |
| bird_formula_1_119 | bird | List out the code for drivers who have nationality i… | ✅ | 1.00 | 1.00 |
| bird_formula_1_120 | bird | List out the Id number of races which were hold in 2… | ✅ | 1.00 | 1.00 |
| bird_formula_1_121 | bird | How many driver participated in race ID number 18? | ❌ | 0.00 | 0.00 |
| bird_formula_1_122 | bird | State code numbers of top 3 yougest drivers. How man… | ✅ | 1.00 | 1.00 |
| bird_formula_1_123 | bird | What is reference name of Robert Kubica? | ❌ | 0.00 | 0.00 |
| bird_formula_1_124 | bird | How many British drivers who were born in 1980? | ✅ | 1.00 | 1.00 |
| bird_formula_1_125 | bird | List out top 3 German drivers who were born from 198… | ✅ | 1.00 | 0.67 |
| bird_formula_1_126 | bird | Please state the reference name of the oldest German… | ❌ | 0.00 | 0.00 |
| bird_formula_1_127 | bird | Which drivers who were born in 1971 and has the fast… | ✅ | 1.00 | 0.67 |
| bird_formula_1_128 | bird | List out top 10 Spanish drivers who were born before… | ✅ | 1.00 | 0.67 |
| bird_formula_1_129 | bird | State the racing year which has the fastest lap time… | ❌ | 0.00 | 0.00 |
| bird_formula_1_130 | bird | Which year has the lowest speed of lap time? | ❌ | 0.12 | 0.00 |
| bird_formula_1_131 | bird | List the driver's ID of the top five driver, by desc… | ❌ | 0.10 | 0.00 |
| bird_formula_1_132 | bird | From race no. 50 to 100, how many finishers have bee… | ❌ | 0.11 | 0.00 |
| bird_formula_1_133 | bird | How many times the circuits were held in Austria? Pl… | ✅ | 1.00 | 1.00 |
| bird_formula_1_134 | bird | What race number has the most finishers? | ❌ | 0.00 | 0.00 |
| bird_formula_1_135 | bird | List the reference name of the drivers who passed th… | ✅ | 1.00 | 1.00 |
| bird_formula_1_136 | bird | On what year did the youngest driver had his first q… | ✅ | 1.00 | 0.50 |
| bird_formula_1_137 | bird | How many American drivers have puncture status. | ✅ | 1.00 | 0.50 |
| bird_formula_1_138 | bird | Which of the Italian constructor got the highest poi… | ❌ | 0.00 | 0.00 |
| bird_formula_1_139 | bird | What is the website of the constructor who tallied t… | ❌ | 0.00 | 0.00 |
| bird_formula_1_140 | bird | Among the drivers who participated in the French Gra… | ❌ | 0.11 | 0.00 |
| bird_formula_1_141 | bird | In which race did the fastest 1st lap time was recor… | ❌ | 0.10 | 0.00 |
| bird_formula_1_142 | bird | What is the average fastest lap time of the top 10 d… | ❌ | 0.00 | 0.00 |
| bird_formula_1_143 | bird | List down top 3 German drivers who has the shortest … | ✅ | 1.00 | 0.67 |
| bird_formula_1_144 | bird | Who is the champion of the Canadian Grand Prix in 20… | ❌ | 0.11 | 0.00 |
| bird_formula_1_145 | bird | What is the constructor reference name of the champi… | ❌ | 0.00 | 0.00 |
| bird_formula_1_146 | bird | What is the full name and date of birth of Austrian … | ✅ | 1.00 | 1.00 |
| bird_formula_1_147 | bird | Find the full name, Wiki Pedia page link, and date o… | ✅ | 1.00 | 1.00 |
| bird_formula_1_148 | bird | In which location does the Hungaroring circuit locat… | ❌ | 0.00 | 0.00 |
| bird_formula_1_149 | bird | Which constructor scored most points from Monaco Gra… | ❌ | 0.00 | 0.00 |
| bird_formula_1_150 | bird | What is the average score of Lewis Hamilton among al… | ❌ | 0.12 | 0.00 |
| bird_formula_1_151 | bird | What is the annual average number of races held duri… | ✅ | 1.00 | 1.00 |
| bird_formula_1_152 | bird | Which citizenship do the vast majority of the driver… | ✅ | 1.00 | 1.00 |
| bird_formula_1_153 | bird | In terms of number of points acquired, how many vict… | ❌ | 0.00 | 0.00 |
| bird_formula_1_154 | bird | In terms of the fastest lap time, what is the name o… | ❌ | 0.00 | 0.00 |
| bird_formula_1_155 | bird | Which racetrack hosted the most recent race? Indicat… | ❌ | 0.10 | 0.00 |
| bird_formula_1_156 | bird | What is full name of the racer who ranked 1st in the… | ✅ | 1.00 | 0.40 |
| bird_formula_1_157 | bird | As of the present, what is the full name of the youn… | ❌ | 0.00 | 0.00 |
| bird_formula_1_158 | bird | How many accidents did the driver who had the highes… | ❌ | 0.00 | 0.00 |
| bird_formula_1_159 | bird | How many wins was achieved by the oldest racer? Indi… | ❌ | 0.11 | 0.00 |
| bird_formula_1_160 | bird | What was the longest time a driver had ever spent at… | ❌ | 0.11 | 0.00 |
| bird_formula_1_161 | bird | Among all the lap records set on various circuits, w… | ❌ | 0.10 | 0.00 |
| bird_formula_1_162 | bird | What was the longest time that Lewis Hamilton had sp… | ❌ | 0.11 | 0.00 |
| bird_formula_1_163 | bird | During which lap did Lewis Hamilton take a pit stop … | ❌ | 0.12 | 0.00 |
| bird_formula_1_164 | bird | Please list the time each driver spent at the pit st… | ❌ | 0.10 | 0.00 |
| bird_formula_1_165 | bird | What is the lap record set by Lewis Hamilton in a Fo… | ❌ | 0.17 | 0.00 |
| bird_formula_1_166 | bird | Which top 20 driver created the shortest lap time ev… | ❌ | 0.10 | 0.00 |
| bird_formula_1_167 | bird | What was the position of the circuits during Lewis H… | ❌ | 0.00 | 0.00 |
| bird_formula_1_168 | bird | What is the lap record for the Austrian Grand Prix C… | ❌ | 0.00 | 0.00 |
| bird_formula_1_169 | bird | Please list the lap records for the circuits in Ital… | ✅ | 1.00 | 0.40 |
| bird_formula_1_170 | bird | In which Formula_1 race was the lap record for the A… | ❌ | 0.00 | 0.00 |
| bird_formula_1_171 | bird | In the race a driver set the lap record for the Aust… | ❌ | 0.12 | 0.00 |
| bird_formula_1_172 | bird | Please list the location coordinates of the circuits… | ✅ | 1.00 | 0.50 |
| bird_formula_1_173 | bird | What was the average time in milliseconds Lewis Hami… | ❌ | 0.00 | 0.00 |
| bird_formula_1_174 | bird | What is the average lap time in milliseconds of all … | ✅ | 1.00 | 0.50 |
