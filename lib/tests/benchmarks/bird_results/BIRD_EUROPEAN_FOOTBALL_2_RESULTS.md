# BIRD — european_football_2 — Results

**Conditions:** `keyword`  
**Queries:** 129  
**Last run:** 2026-08-25 09:35 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 33% |
| Hit@3 | 34% |
| Hit@5 | 44% |
| MRR | 44% |

```
Hit@5 (% of 129 queries)

  keyword         ███████░░░░░░░░   44%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.248 |
| P@3 | 0.335 |
| R@3 | 0.209 |
| F1@5 | 0.277 |
| P@5 | 0.319 |
| R@5 | 0.266 |
| F1@10 | 0.397 |
| P@10 | 0.259 |
| R@10 | 0.904 |
| F1@Ideal-K | 0.246 |
| P@Ideal-K | 0.333 |
| R@Ideal-K | 0.205 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 129 | 33% | 0.44 | 0.25 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_european_football_2_001 | bird | Which player has the highest overall rating? Indicat… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_002 | bird | What is the height of the tallest player? Indicate h… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_003 | bird | What is the preferred foot when attacking of the pla… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_004 | bird | Among the players with an overall rating between 60 … | ❌ | 0.14 | 0.00 |
| bird_european_football_2_005 | bird | Who are the top 5 players who perform better in cros… | ❌ | 0.12 | 0.00 |
| bird_european_football_2_006 | bird | Give the name of the league had the most goals in th… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_007 | bird | Which home team had lost the fewest matches in the 2… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_008 | bird | Indicate the full names of the top 10 players with t… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_009 | bird | In Scotland Premier League, which away team won the … | ✅ | 1.00 | 0.50 |
| bird_european_football_2_010 | bird | What are the speed in which attacks are put together… | ❌ | 0.20 | 0.00 |
| bird_european_football_2_011 | bird | Give the name of the league had the most matches end… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_012 | bird | At present, calculate for the player's age who have … | ❌ | 0.17 | 0.00 |
| bird_european_football_2_013 | bird | Give the name of the league with the highest matches… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_014 | bird | What is the average height of players born between 1… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_015 | bird | List the players' api id who had the highest above a… | ❌ | 0.00 | 0.00 |
| bird_european_football_2_016 | bird | Give the team_fifa_api_id of teams with more than 50… | ❌ | 0.00 | 0.00 |
| bird_european_football_2_017 | bird | List the long name of teams with above-average build… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_018 | bird | Calculate the percentage of players who prefer left … | ❌ | 0.17 | 0.00 |
| bird_european_football_2_019 | bird | List the top 5 leagues in ascending order of the num… | ❌ | 0.25 | 0.00 |
| bird_european_football_2_020 | bird | Find the average number of long-shot done by Ahmed S… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_021 | bird | List the top 10 players' names whose heights are abo… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_022 | bird | For the teams with normal build-up play dribbling cl… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_023 | bird | List the name of leagues in which the average goals … | ❌ | 0.17 | 0.00 |
| bird_european_football_2_024 | bird | What is the short name of the football team Queens P… | ✅ | 1.00 | 1.00 |
| bird_european_football_2_025 | bird | List the football players with a birthyear of 1970 a… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_026 | bird | What is the attacking work rate of the football play… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_027 | bird | What is the ADO Den Haag team freedom of movement in… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_028 | bird | What is the football player Francois Affolter header… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_029 | bird | What is the overall rating of the football player Ga… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_030 | bird | How many matches in the 2015/2016 season were held i… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_031 | bird | What is the preferred foot when attacking of the you… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_032 | bird | List all the football player with the highest potent… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_033 | bird | Among all the players whose weight is under 130, how… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_034 | bird | List the football teams that has a chance creation p… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_035 | bird | What is the defensive work rate of the football play… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_036 | bird | When is the birthday of the football player who has … | ✅ | 1.00 | 0.67 |
| bird_european_football_2_037 | bird | What is the name of the football league in the count… | ✅ | 1.00 | 1.00 |
| bird_european_football_2_038 | bird | Calculate the average home team goal in the 2010/201… | ❌ | 0.50 | 0.50 |
| bird_european_football_2_039 | bird | Who has the highest average finishing rate between t… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_040 | bird | Please list player names which are higher than 180. | ✅ | 1.00 | 1.00 |
| bird_european_football_2_041 | bird | How many players were born after 1990? | ❌ | 0.17 | 0.00 |
| bird_european_football_2_042 | bird | How many players whose first names are Adam and weig… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_043 | bird | Which players had an overall rating of over 80 from … | ✅ | 1.00 | 0.67 |
| bird_european_football_2_044 | bird | What is Aaron Doran's potential score? | ❌ | 0.14 | 0.00 |
| bird_european_football_2_045 | bird | List out of players whose preferred foot is left. | ❌ | 0.17 | 0.00 |
| bird_european_football_2_046 | bird | Please list all team names which the speed class is … | ✅ | 1.00 | 0.67 |
| bird_european_football_2_047 | bird | What is the passing class of CLB team? | ❌ | 0.20 | 0.00 |
| bird_european_football_2_048 | bird | Which teams have build up play passing more than 70?… | ❌ | 0.20 | 0.00 |
| bird_european_football_2_049 | bird | From 2010 to 2015, what was the average overall rati… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_050 | bird | Which football player has the shortest height? | ✅ | 1.00 | 1.00 |
| bird_european_football_2_051 | bird | Which country is the league Italy Serie A from? | ✅ | 1.00 | 1.00 |
| bird_european_football_2_052 | bird | List the football team that has a build up play spee… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_053 | bird | What is the average overall rating of the football p… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_054 | bird | How many matches were held in the league Germany 1. … | ✅ | 1.00 | 0.67 |
| bird_european_football_2_055 | bird | List all the short name of the football team that ha… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_056 | bird | List all the football player with the highest balanc… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_057 | bird | What is the difference of the average ball control s… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_058 | bird | What's the long name for the team GEN? | ✅ | 1.00 | 1.00 |
| bird_european_football_2_059 | bird | Which player is older, Aaron Lennon or Abdelaziz Bar… | ✅ | 1.00 | 1.00 |
| bird_european_football_2_060 | bird | Which player is the tallest? | ✅ | 1.00 | 1.00 |
| bird_european_football_2_061 | bird | Among the players whose preferred foot was the left … | ❌ | 0.14 | 0.00 |
| bird_european_football_2_062 | bird | Which country is the Belgium Jupiler League from? | ✅ | 1.00 | 1.00 |
| bird_european_football_2_063 | bird | Please list the leagues from Germany. | ❌ | 0.25 | 0.00 |
| bird_european_football_2_064 | bird | Which player has the strongest overall strength? | ✅ | 1.00 | 0.67 |
| bird_european_football_2_065 | bird | Among the players born before the year 1986, how man… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_066 | bird | Which of these players performs the best in crossing… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_067 | bird | What's the heading accuracy of Ariel Borysiuk? | ❌ | 0.17 | 0.00 |
| bird_european_football_2_068 | bird | Among the players whose height is over 180, how many… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_069 | bird | Please list the names of the players whose volley sc… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_070 | bird | How many matches in the 2008/2009 season were held i… | ❌ | 0.12 | 0.00 |
| bird_european_football_2_071 | bird | What is the long passing score of the oldest player? | ❌ | 0.17 | 0.00 |
| bird_european_football_2_072 | bird | How many matches were held in the Belgium Jupiler Le… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_073 | bird | Give the name of the league had the most matches in … | ✅ | 1.00 | 0.67 |
| bird_european_football_2_074 | bird | What is the average overall rating of the players bo… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_075 | bird | How much higher in percentage is Ariel Borysiuk's ov… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_076 | bird | How much is the average build up play speed of the H… | ❌ | 0.20 | 0.00 |
| bird_european_football_2_077 | bird | Calculate the average overall rating of Pietro Marin… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_078 | bird | What is Aaron Lennox's total crossing score? | ❌ | 0.14 | 0.00 |
| bird_european_football_2_079 | bird | What is Ajax's highest chance creation passing score… | ❌ | 0.20 | 0.00 |
| bird_european_football_2_080 | bird | Which foot is preferred by Abdou Diallo? | ❌ | 0.17 | 0.00 |
| bird_european_football_2_081 | bird | What is the highest overall rating received by Dorla… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_082 | bird | What is the average number of goals made by Parma as… | ✅ | 1.00 | 0.50 |
| bird_european_football_2_083 | bird | For the players who had a 77 points overall rating o… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_084 | bird | What was the overall rating for Aaron Mooy on 2016/2… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_085 | bird | What was the potiential for Francesco Parravicini on… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_086 | bird | How was Francesco Migliore's attacking work rate on … | ❌ | 0.17 | 0.00 |
| bird_european_football_2_087 | bird | Tell the defensive work rate for Kevin Berigaud on 2… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_088 | bird | When was the first time did Kevin Constant have his … | ❌ | 0.14 | 0.00 |
| bird_european_football_2_089 | bird | What was the build up play speed class for "Willem I… | ❌ | 0.20 | 0.00 |
| bird_european_football_2_090 | bird | How was the build up play dribbling class for "LEI" … | ❌ | 0.17 | 0.00 |
| bird_european_football_2_091 | bird | Tell the build Up play passing class for "FC Lorient… | ❌ | 0.20 | 0.00 |
| bird_european_football_2_092 | bird | State the chance creation passing class for "PEC Zwo… | ❌ | 0.20 | 0.00 |
| bird_european_football_2_093 | bird | What was the chance creation crossing class for "Hul… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_094 | bird | For the team "Hannover 96", what was its defence agg… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_095 | bird | What was the average overall rating for Marko Arnaut… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_096 | bird | What percentage is Landon Donovan's overall rating h… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_097 | bird | List down most tallest players' name. | ❌ | 0.17 | 0.00 |
| bird_european_football_2_098 | bird | What are the player api id of 10 heaviest players? | ✅ | 1.00 | 1.00 |
| bird_european_football_2_099 | bird | List down the name of players who are 35 years old a… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_100 | bird | How many home team goal have been scored by Aaron Le… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_101 | bird | Sum up the away team goal scored by both Daan Smith … | ❌ | 0.14 | 0.00 |
| bird_european_football_2_102 | bird | Calculate the total home team goal scored by players… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_103 | bird | State the name of the most strongest player. | ❌ | 0.14 | 0.00 |
| bird_european_football_2_104 | bird | What is the name of players with the highest potenti… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_105 | bird | Who are the players that tend to be attacking when t… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_106 | bird | Among the players with finishing rate of 1, pick the… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_107 | bird | State the name of players who came from Belgium. | ❌ | 0.14 | 0.00 |
| bird_european_football_2_108 | bird | Locate players with vision scores of 90 and above, s… | ✅ | 1.00 | 0.40 |
| bird_european_football_2_109 | bird | Which country's players have the heaviest average we… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_110 | bird | List down the long name for slow speed class team. | ❌ | 0.17 | 0.00 |
| bird_european_football_2_111 | bird | What are the short name of team who played safe whil… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_112 | bird | What is the average heights of Italy players? | ❌ | 0.17 | 0.00 |
| bird_european_football_2_113 | bird | Please provide the names of top three football playe… | ❌ | 0.17 | 0.00 |
| bird_european_football_2_114 | bird | How many football players born after the 1990s have … | ❌ | 0.14 | 0.00 |
| bird_european_football_2_115 | bird | What is the difference between players 6 and 23's ju… | ❌ | 0.12 | 0.00 |
| bird_european_football_2_116 | bird | Please provide top five football players' IDs who ar… | ❌ | 0.12 | 0.00 |
| bird_european_football_2_117 | bird | How many players had the highest potential score for… | ❌ | 0.11 | 0.00 |
| bird_european_football_2_118 | bird | What percentage of players have a strength and stami… | ❌ | 0.11 | 0.00 |
| bird_european_football_2_119 | bird | In what country did the Poland Ekstraklasa take plac… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_120 | bird | What was the final score for the match on September … | ✅ | 1.00 | 0.50 |
| bird_european_football_2_121 | bird | What are Alexis Blin's sprint speed, agility, and ac… | ❌ | 0.14 | 0.00 |
| bird_european_football_2_122 | bird | Does the KSV Cercle Brugge team have a slow, balance… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_123 | bird | In the 2015–2016 season, how many games were played … | ❌ | 0.25 | 0.00 |
| bird_european_football_2_124 | bird | What was the highest score of the home team in the N… | ❌ | 0.20 | 0.00 |
| bird_european_football_2_125 | bird | Please state the finishing rate and curve score of t… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_126 | bird | Which top 4 leagues had the most games in the 2015-2… | ❌ | 0.25 | 0.00 |
| bird_european_football_2_127 | bird | Please provide the full name of the away team that s… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_128 | bird | Please name one player whose overall strength is the… | ✅ | 1.00 | 0.67 |
| bird_european_football_2_129 | bird | What is the percentage of players that are under 180… | ❌ | 0.14 | 0.00 |
