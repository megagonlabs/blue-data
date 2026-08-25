# BIRD — superhero — Results

**Conditions:** `keyword`  
**Queries:** 129  
**Last run:** 2026-08-25 09:56 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 91% |
| Hit@3 | 94% |
| Hit@5 | 96% |
| MRR | 93% |

```
Hit@5 (% of 129 queries)

  keyword         ██████████████░   96%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.202 |
| P@3 | 0.322 |
| R@3 | 0.153 |
| F1@5 | 0.292 |
| P@5 | 0.354 |
| R@5 | 0.262 |
| F1@10 | 0.307 |
| P@10 | 0.230 |
| R@10 | 0.532 |
| F1@Ideal-K | 0.137 |
| P@Ideal-K | 0.229 |
| R@Ideal-K | 0.101 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 129 | 91% | 0.93 | 0.14 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_superhero_001 | bird | Please list all the superpowers of 3-D Man. | ✅ | 1.00 | 0.00 |
| bird_superhero_002 | bird | How many superheroes have the super power of "Super … | ❌ | 0.20 | 0.00 |
| bird_superhero_003 | bird | Among the superheroes with the super power of "Super… | ✅ | 1.00 | 0.00 |
| bird_superhero_004 | bird | Please list the full names of all the superheroes wi… | ✅ | 1.00 | 0.00 |
| bird_superhero_005 | bird | How many superheroes have blue eyes? | ✅ | 1.00 | 0.00 |
| bird_superhero_006 | bird | What is the colour of Apocalypse's skin? | ✅ | 1.00 | 0.67 |
| bird_superhero_007 | bird | Among the superheroes with blue eyes, how many of th… | ✅ | 1.00 | 0.00 |
| bird_superhero_008 | bird | Please list the superhero names of all the superhero… | ✅ | 1.00 | 0.00 |
| bird_superhero_009 | bird | How many superheroes are published by Marvel Comics? | ✅ | 1.00 | 0.00 |
| bird_superhero_010 | bird | Rank heroes published by Marvel Comics by their heig… | ✅ | 1.00 | 0.00 |
| bird_superhero_011 | bird | Who is the publisher of Sauron? | ✅ | 1.00 | 0.67 |
| bird_superhero_012 | bird | Rank superheroes from Marvel Comics by their eye col… | ✅ | 1.00 | 0.00 |
| bird_superhero_013 | bird | What is the average height of the superheroes from M… | ✅ | 1.00 | 0.00 |
| bird_superhero_014 | bird | List the superheroes from Marvel Comics who have the… | ✅ | 1.00 | 0.00 |
| bird_superhero_015 | bird | How many superheroes did DC Comics publish? | ✅ | 1.00 | 0.00 |
| bird_superhero_016 | bird | Which publisher published the slowest superhero? | ✅ | 1.00 | 0.40 |
| bird_superhero_017 | bird | How many gold-eyed superheroes did Marvel Comics pub… | ✅ | 1.00 | 0.00 |
| bird_superhero_018 | bird | What is the publisher's name of Blue Beetle II? | ✅ | 1.00 | 0.00 |
| bird_superhero_019 | bird | How many superheroes with blonde hair are there? | ✅ | 1.00 | 0.00 |
| bird_superhero_020 | bird | Who is the dumbest superhero? | ✅ | 1.00 | 0.00 |
| bird_superhero_021 | bird | What is Copycat's race? | ✅ | 1.00 | 0.00 |
| bird_superhero_022 | bird | Which superheroes have a durability attribute value … | ✅ | 1.00 | 0.50 |
| bird_superhero_023 | bird | What are the names of the superheroes with the power… | ✅ | 1.00 | 0.00 |
| bird_superhero_024 | bird | How many female superheroes have a strength value of… | ✅ | 1.00 | 0.40 |
| bird_superhero_025 | bird | What is the name of the superhero that has the most … | ✅ | 1.00 | 0.00 |
| bird_superhero_026 | bird | How many vampire superheroes are there? | ✅ | 1.00 | 0.00 |
| bird_superhero_027 | bird | What is the percentage of superheroes who act in the… | ✅ | 1.00 | 0.00 |
| bird_superhero_028 | bird | Between DC and Marvel Comics, which publisher has pu… | ✅ | 1.00 | 0.67 |
| bird_superhero_029 | bird | Give the publisher ID of Star Trek. | ✅ | 1.00 | 1.00 |
| bird_superhero_030 | bird | Calculate the average attribute value of all superhe… | ❌ | 0.00 | 0.00 |
| bird_superhero_031 | bird | What is the total number of superheroes without full… | ✅ | 1.00 | 0.00 |
| bird_superhero_032 | bird | What is the eye colour of superhero with superhero I… | ✅ | 1.00 | 0.00 |
| bird_superhero_033 | bird | Provide the superpowers of the superhero called Deat… | ✅ | 1.00 | 0.50 |
| bird_superhero_034 | bird | What is the average weight of all female superheroes… | ✅ | 1.00 | 0.00 |
| bird_superhero_035 | bird | List down at least five superpowers of male superher… | ✅ | 1.00 | 0.00 |
| bird_superhero_036 | bird | Give the name of the alien superheroes. | ✅ | 1.00 | 0.00 |
| bird_superhero_037 | bird | Among the superheroes with height from 170 to 190, l… | ✅ | 1.00 | 0.00 |
| bird_superhero_038 | bird | What is the superpower of hero ID 56? | ✅ | 1.00 | 0.67 |
| bird_superhero_039 | bird | List down at least five full name of Demi-God superh… | ✅ | 1.00 | 0.00 |
| bird_superhero_040 | bird | How many bad superheroes are there? | ✅ | 1.00 | 0.00 |
| bird_superhero_041 | bird | Identify the race of the superhero who weighed 169 k… | ✅ | 1.00 | 0.00 |
| bird_superhero_042 | bird | Provide the hair colour of the human superhero who i… | ✅ | 1.00 | 0.50 |
| bird_superhero_043 | bird | What is the eye clolour of the heaviest superhero? | ✅ | 1.00 | 0.00 |
| bird_superhero_044 | bird | In superheroes with height between 150 to 180, what … | ✅ | 1.00 | 0.00 |
| bird_superhero_045 | bird | Among the male superheroes, list the super hero name… | ✅ | 1.00 | 0.00 |
| bird_superhero_046 | bird | Which power do superheroes have the most of? | ❌ | 0.20 | 0.00 |
| bird_superhero_047 | bird | Indicate the attribute value of superhero Abominatio… | ✅ | 1.00 | 0.00 |
| bird_superhero_048 | bird | What are the superpowers of heroes with ID 1? | ❌ | 0.00 | 0.00 |
| bird_superhero_049 | bird | How many heroes have stealth power? | ❌ | 0.20 | 0.00 |
| bird_superhero_050 | bird | What is the hero's full name with the highest attrib… | ✅ | 1.00 | 0.50 |
| bird_superhero_051 | bird | What is the average of superheroes with no skin colo… | ✅ | 1.00 | 0.00 |
| bird_superhero_052 | bird | How many superheroes were published by Dark Horse Co… | ✅ | 1.00 | 0.00 |
| bird_superhero_053 | bird | Which superhero has the most durability published by… | ✅ | 1.00 | 0.40 |
| bird_superhero_054 | bird | What is the eyes colour of Abraham Sapien? | ✅ | 1.00 | 0.67 |
| bird_superhero_055 | bird | List the name of superheroes with flight power. | ✅ | 1.00 | 0.00 |
| bird_superhero_056 | bird | List the eyes, hair and skin colour of all female su… | ❌ | 0.33 | 0.00 |
| bird_superhero_057 | bird | Which superhero has the same eyes, hair and skin col… | ✅ | 1.00 | 0.00 |
| bird_superhero_058 | bird | Which group does superhero A-Bomb belong to? | ✅ | 1.00 | 0.00 |
| bird_superhero_059 | bird | What is the percentage of blue female superheroes am… | ✅ | 1.00 | 0.00 |
| bird_superhero_060 | bird | Provide the hero name and race of Charles Chandler. | ✅ | 1.00 | 0.67 |
| bird_superhero_061 | bird | What is the gender of Agent 13 hero? | ✅ | 1.00 | 0.67 |
| bird_superhero_062 | bird | Provide superheroes' names who have the adaptation p… | ✅ | 1.00 | 0.00 |
| bird_superhero_063 | bird | How many powers does Amazo hero have? | ✅ | 1.00 | 0.00 |
| bird_superhero_064 | bird | List the powers of Hunter Zolomon. | ✅ | 1.00 | 0.00 |
| bird_superhero_065 | bird | Provide the heights of the heroes whose eye colours … | ✅ | 1.00 | 0.00 |
| bird_superhero_066 | bird | List the heroes' names whose eyes and hair colours a… | ✅ | 1.00 | 0.00 |
| bird_superhero_067 | bird | Provide the eye colours of the heroes whose skin col… | ✅ | 1.00 | 0.00 |
| bird_superhero_068 | bird | Provide the full names of vampire heroes. | ✅ | 1.00 | 0.00 |
| bird_superhero_069 | bird | Describe the names of neutral alignment superheroes. | ✅ | 1.00 | 0.67 |
| bird_superhero_070 | bird | How many heroes have the highest attribute value in … | ✅ | 1.00 | 0.67 |
| bird_superhero_071 | bird | What are the race and alignment of Cameron Hicks? | ✅ | 1.00 | 0.80 |
| bird_superhero_072 | bird | How many percent of female heroes were published by … | ✅ | 1.00 | 0.00 |
| bird_superhero_073 | bird | Find the average weight of the heroes who are aliens… | ✅ | 1.00 | 0.00 |
| bird_superhero_074 | bird | Calculate the difference between Emil Blonsky's weig… | ✅ | 1.00 | 0.00 |
| bird_superhero_075 | bird | Calculate the average height for each superhero. | ✅ | 1.00 | 0.00 |
| bird_superhero_076 | bird | What is Abomination's superpower? | ✅ | 1.00 | 0.00 |
| bird_superhero_077 | bird | Among the superheroes with the race of god/eternal, … | ✅ | 1.00 | 0.50 |
| bird_superhero_078 | bird | Which hero was the fastest? | ✅ | 1.00 | 0.00 |
| bird_superhero_079 | bird | How many superheroes have a neutral alignment? | ✅ | 1.00 | 0.00 |
| bird_superhero_080 | bird | State all of 3-D Man's attributes along with their v… | ✅ | 1.00 | 0.00 |
| bird_superhero_081 | bird | Which superheroes have blue eyes with brown hair? | ✅ | 1.00 | 0.00 |
| bird_superhero_082 | bird | What is the publisher for Hawkman, Karate Kid and Sp… | ✅ | 1.00 | 0.67 |
| bird_superhero_083 | bird | How many superheroes didn't have any publisher? | ✅ | 1.00 | 0.00 |
| bird_superhero_084 | bird | Calculate the percentage of superheroes with blue ey… | ✅ | 1.00 | 0.00 |
| bird_superhero_085 | bird | Find the ratio between male superheroes and female s… | ✅ | 1.00 | 0.00 |
| bird_superhero_086 | bird | Who is the tallest superhero? | ✅ | 1.00 | 0.00 |
| bird_superhero_087 | bird | What is the power ID of cryokinesis? | ❌ | 0.00 | 0.00 |
| bird_superhero_088 | bird | Provide the name of superhero with superhero ID 294. | ✅ | 1.00 | 0.00 |
| bird_superhero_089 | bird | List the full names of superheroes with missing weig… | ✅ | 1.00 | 0.00 |
| bird_superhero_090 | bird | Provide the eye colour of the superhero who has Kare… | ✅ | 1.00 | 0.00 |
| bird_superhero_091 | bird | What is the superpowers of the superhero has Helen P… | ✅ | 1.00 | 0.50 |
| bird_superhero_092 | bird | Find the race of the superhero who weighs 108kg and … | ✅ | 1.00 | 0.00 |
| bird_superhero_093 | bird | What is the publisher name of the superhero ID 38? | ✅ | 1.00 | 0.00 |
| bird_superhero_094 | bird | What is the race of the superhero with maximum attri… | ✅ | 1.00 | 0.00 |
| bird_superhero_095 | bird | Give the alignment and superpowers of the superhero … | ✅ | 1.00 | 0.67 |
| bird_superhero_096 | bird | List down at least five full names of superheroes wi… | ✅ | 1.00 | 0.00 |
| bird_superhero_097 | bird | Calculate the average attribute value of all neutral… | ❌ | 0.50 | 0.00 |
| bird_superhero_098 | bird | List the skin colour of the superheroes with 100 att… | ❌ | 0.50 | 0.40 |
| bird_superhero_099 | bird | Count the good female superheroes. | ✅ | 1.00 | 0.00 |
| bird_superhero_100 | bird | Provide the names of superheroes with attribute valu… | ❌ | 0.50 | 0.00 |
| bird_superhero_101 | bird | Give the race of the blue-haired male superhero. | ✅ | 1.00 | 0.40 |
| bird_superhero_102 | bird | Among the bad superheroes, what is the percentage of… | ✅ | 1.00 | 0.00 |
| bird_superhero_103 | bird | In superheroes with missing weight data, calculate t… | ✅ | 1.00 | 0.00 |
| bird_superhero_104 | bird | How strong is the Hulk? | ✅ | 1.00 | 0.00 |
| bird_superhero_105 | bird | List down Ajax's superpowers. | ✅ | 1.00 | 0.00 |
| bird_superhero_106 | bird | How many green-skinned villains are there in the sup… | ✅ | 1.00 | 0.50 |
| bird_superhero_107 | bird | How many female superheroes are in Marvel Comics? | ✅ | 1.00 | 0.00 |
| bird_superhero_108 | bird | Identify superheroes who can control wind and list t… | ✅ | 1.00 | 0.00 |
| bird_superhero_109 | bird | Identify the gender of the superhero who has the abi… | ✅ | 1.00 | 0.67 |
| bird_superhero_110 | bird | Identify the heaviest superhero in DC Comics. | ✅ | 1.00 | 0.00 |
| bird_superhero_111 | bird | What is the average height of a non-human superhero … | ✅ | 1.00 | 0.50 |
| bird_superhero_112 | bird | Count the fastest superheroes. | ✅ | 1.00 | 0.00 |
| bird_superhero_113 | bird | Which publisher created more superheroes: DC or Marv… | ✅ | 1.00 | 0.67 |
| bird_superhero_114 | bird | Identify the weakest attribute of the Black Panther. | ✅ | 1.00 | 0.50 |
| bird_superhero_115 | bird | What is Abomination's eye colour? | ✅ | 1.00 | 0.00 |
| bird_superhero_116 | bird | Name the tallest superhero. | ✅ | 1.00 | 0.00 |
| bird_superhero_117 | bird | Name the superhero, otherwise known as Charles Chand… | ✅ | 1.00 | 0.00 |
| bird_superhero_118 | bird | Among all superheroes created by George Lucas, ident… | ✅ | 1.00 | 0.00 |
| bird_superhero_119 | bird | Among all superheroes in Marvel Comics, identify the… | ✅ | 1.00 | 0.00 |
| bird_superhero_120 | bird | What is the total number of superheroes that have Jo… | ✅ | 1.00 | 0.00 |
| bird_superhero_121 | bird | Give the hero ID of superhero with the lowest attrib… | ❌ | 0.00 | 0.00 |
| bird_superhero_122 | bird | Provide the full name of the superhero named Alien. | ✅ | 1.00 | 0.00 |
| bird_superhero_123 | bird | In superheroes with weight less than 100, list the f… | ✅ | 1.00 | 0.00 |
| bird_superhero_124 | bird | List the attribute value of the superhero named Aqua… | ✅ | 1.00 | 0.00 |
| bird_superhero_125 | bird | Provide the weight and race of the superhero with su… | ✅ | 1.00 | 0.00 |
| bird_superhero_126 | bird | Calculate the average height of all neutral superher… | ✅ | 1.00 | 0.00 |
| bird_superhero_127 | bird | List the hero ID of superheroes have intellegence as… | ❌ | 0.00 | 0.00 |
| bird_superhero_128 | bird | Give the eye colour of Blackwulf. | ✅ | 1.00 | 0.67 |
| bird_superhero_129 | bird | List the power of superheroes with height greater th… | ✅ | 1.00 | 0.00 |
