# BIRD — card_games — Results

**Conditions:** `keyword`  
**Queries:** 191  
**Last run:** 2026-08-25 09:35 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 57% |
| Hit@3 | 57% |
| Hit@5 | 61% |
| MRR | 61% |

```
Hit@5 (% of 191 queries)

  keyword         █████████░░░░░░   61%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.449 |
| P@3 | 0.560 |
| R@3 | 0.398 |
| F1@5 | 0.411 |
| P@5 | 0.450 |
| R@5 | 0.428 |
| F1@10 | 0.358 |
| P@10 | 0.258 |
| R@10 | 0.791 |
| F1@Ideal-K | 0.451 |
| P@Ideal-K | 0.563 |
| R@Ideal-K | 0.398 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 191 | 57% | 0.61 | 0.45 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_card_games_001 | bird | Which are the cards that have incredibly powerful fo… | ✅ | 1.00 | 1.00 |
| bird_card_games_002 | bird | What are the borderless cards available without powe… | ✅ | 1.00 | 1.00 |
| bird_card_games_003 | bird | List the card names with value that cost more conver… | ❌ | 0.10 | 0.00 |
| bird_card_games_004 | bird | Name all cards with 2015 frame style ranking below 1… | ✅ | 1.00 | 1.00 |
| bird_card_games_005 | bird | List all the mythic rarity print cards banned in gla… | ✅ | 1.00 | 0.67 |
| bird_card_games_006 | bird | For artifact type of cards that do not have multiple… | ✅ | 1.00 | 1.00 |
| bird_card_games_007 | bird | List all the card id and artist with unknown power w… | ❌ | 0.10 | 0.00 |
| bird_card_games_008 | bird | Find all cards illustrated by Stephen Daniel and des… | ✅ | 1.00 | 0.67 |
| bird_card_games_009 | bird | Describe the information about rulings for card name… | ✅ | 1.00 | 0.67 |
| bird_card_games_010 | bird | Name the card and artist with the most ruling inform… | ❌ | 0.00 | 0.00 |
| bird_card_games_011 | bird | State the alternative languages available for card n… | ❌ | 0.20 | 0.00 |
| bird_card_games_012 | bird | Name all the cards which have alternative language i… | ✅ | 1.00 | 0.67 |
| bird_card_games_013 | bird | Calculate the percentage of the cards availabe in Ch… | ✅ | 1.00 | 0.67 |
| bird_card_games_014 | bird | List all the sets available in Italian translation. … | ✅ | 1.00 | 0.50 |
| bird_card_games_015 | bird | How many types of cards does the artist Aaron Boyd i… | ✅ | 1.00 | 1.00 |
| bird_card_games_016 | bird | What is the keyword found on card 'Angel of Mercy'? | ❌ | 0.10 | 0.00 |
| bird_card_games_017 | bird | How many cards have infinite power? | ✅ | 1.00 | 1.00 |
| bird_card_games_018 | bird | What type of promotion is of card 'Duress'? | ❌ | 0.00 | 0.00 |
| bird_card_games_019 | bird | What is the border color of card "Ancestor's Chosen"… | ❌ | 0.10 | 0.00 |
| bird_card_games_020 | bird | What is the type of the card "Ancestor's Chosen" as … | ❌ | 0.00 | 0.00 |
| bird_card_games_021 | bird | cards are not directly linked to language but throug… | ✅ | 1.00 | 0.67 |
| bird_card_games_022 | bird | How many cards of legalities whose status is restric… | ✅ | 1.00 | 1.00 |
| bird_card_games_023 | bird | What is the description about the ruling of card "Co… | ❌ | 0.17 | 0.00 |
| bird_card_games_024 | bird | How many cards of legalities whose status is restric… | ✅ | 1.00 | 1.00 |
| bird_card_games_025 | bird | What is the status of card "Cloudchaser Eagle"? | ❌ | 0.20 | 0.00 |
| bird_card_games_026 | bird | What is the type of card "Benalish Knight"? | ❌ | 0.12 | 0.00 |
| bird_card_games_027 | bird | What is the rule of playing card "Benalish Knight"? | ❌ | 0.25 | 0.00 |
| bird_card_games_028 | bird | Please provide the names of the artists who illustra… | ❌ | 0.20 | 0.00 |
| bird_card_games_029 | bird | What is the percentage of borderless cards? | ❌ | 0.10 | 0.00 |
| bird_card_games_030 | bird | How many cards that illusrtated in German have been … | ✅ | 1.00 | 0.67 |
| bird_card_games_031 | bird | How many borderless cards are illustrated in Russian… | ✅ | 1.00 | 0.67 |
| bird_card_games_032 | bird | What is the percentage of cards whose language is Fr… | ✅ | 1.00 | 0.67 |
| bird_card_games_033 | bird | How many cards are there with toughness of 99? | ✅ | 1.00 | 1.00 |
| bird_card_games_034 | bird | Name the cards that were illustrated by Aaron Boyd. | ✅ | 1.00 | 1.00 |
| bird_card_games_035 | bird | How many black border cards are only available on mt… | ✅ | 1.00 | 1.00 |
| bird_card_games_036 | bird | List down all the card IDs with converted mana cost … | ❌ | 0.10 | 0.00 |
| bird_card_games_037 | bird | What are the card layout of cards with keyword of fl… | ✅ | 1.00 | 1.00 |
| bird_card_games_038 | bird | How many cards with original type of "Summon - Angel… | ✅ | 1.00 | 1.00 |
| bird_card_games_039 | bird | What are the foiled cards that are incredibly powerf… | ✅ | 1.00 | 1.00 |
| bird_card_games_040 | bird | What are the cards belong to duel deck a? List the I… | ✅ | 1.00 | 1.00 |
| bird_card_games_041 | bird | List the edhrecRank for cards with frame version 201… | ✅ | 1.00 | 1.00 |
| bird_card_games_042 | bird | List down the name of artists for cards in Chinese S… | ✅ | 1.00 | 0.67 |
| bird_card_games_043 | bird | What are the cards that only available in paper and … | ✅ | 1.00 | 0.67 |
| bird_card_games_044 | bird | How many of the banned cards are white border? | ✅ | 1.00 | 0.67 |
| bird_card_games_045 | bird | List down the uuid for legacy cards and the foreign … | ✅ | 1.00 | 0.50 |
| bird_card_games_046 | bird | Write down the ruling of Beacon of Immortality. | ❌ | 0.17 | 0.00 |
| bird_card_games_047 | bird | How many cards are having future frame version and w… | ✅ | 1.00 | 0.67 |
| bird_card_games_048 | bird | What are the cards for set OGW? State the colour for… | ✅ | 1.00 | 0.67 |
| bird_card_games_049 | bird | What are the cards in set 10E with converted mana of… | ✅ | 1.00 | 0.67 |
| bird_card_games_050 | bird | List down the name of cards with original types of C… | ✅ | 1.00 | 1.00 |
| bird_card_games_051 | bird | What are the colors of cards from ID 1-20? What are … | ✅ | 1.00 | 0.67 |
| bird_card_games_052 | bird | Among the Artifact cards, which are black color and … | ❌ | 0.20 | 0.00 |
| bird_card_games_053 | bird | Pick 3 cards with rarity of uncommon, list down name… | ✅ | 1.00 | 0.67 |
| bird_card_games_054 | bird | On how many cards designed by John Avon is its foil … | ✅ | 1.00 | 1.00 |
| bird_card_games_055 | bird | How many white bordered cards are powerful? | ✅ | 1.00 | 1.00 |
| bird_card_games_056 | bird | How many cards designed by UDON and available in mtg… | ✅ | 1.00 | 1.00 |
| bird_card_games_057 | bird | How many cards with a 1993 frame version and availab… | ✅ | 1.00 | 1.00 |
| bird_card_games_058 | bird | What is the mana cost of cards with a normal layout,… | ✅ | 1.00 | 1.00 |
| bird_card_games_059 | bird | What is the  unconverted mana do all the cards creat… | ✅ | 1.00 | 1.00 |
| bird_card_games_060 | bird | Lists all types of cards available in arena. | ✅ | 1.00 | 1.00 |
| bird_card_games_061 | bird | Lists the set code of all cards translated into Span… | ❌ | 0.00 | 0.00 |
| bird_card_games_062 | bird | What percentage of legendary frame effect cards that… | ✅ | 1.00 | 1.00 |
| bird_card_games_063 | bird | What is the percentage of Story Spotlight cards that… | ✅ | 1.00 | 1.00 |
| bird_card_games_064 | bird | Calculate the percentage of cards in Spanish. List t… | ❌ | 0.17 | 0.00 |
| bird_card_games_065 | bird | Indicates the name of all the languages into which t… | ❌ | 0.00 | 0.00 |
| bird_card_games_066 | bird | How many Brazilian Portuguese translated sets are in… | ✅ | 1.00 | 0.67 |
| bird_card_games_067 | bird | Lists by ID all Creature-type cards with legal statu… | ✅ | 1.00 | 0.50 |
| bird_card_games_068 | bird | Lists all types of cards in German. | ✅ | 1.00 | 0.67 |
| bird_card_games_069 | bird | How many unknown power cards contain info about the … | ✅ | 1.00 | 0.67 |
| bird_card_games_070 | bird | Indicates the number of cards with pre-modern format… | ✅ | 1.00 | 0.50 |
| bird_card_games_071 | bird | Is there any card from Erica Yang artist in pauper f… | ❌ | 0.17 | 0.00 |
| bird_card_games_072 | bird | To which artist does the card with the text "Das per… | ❌ | 0.11 | 0.00 |
| bird_card_games_073 | bird | What is the foreign name of the card in French of ty… | ❌ | 0.00 | 0.00 |
| bird_card_games_074 | bird | How many cards with print rarity have ruling text pr… | ✅ | 1.00 | 0.67 |
| bird_card_games_075 | bird | What language is the set of 180 cards that belongs t… | ❌ | 0.00 | 0.00 |
| bird_card_games_076 | bird | What percentage of cards with format commander and l… | ✅ | 1.00 | 0.67 |
| bird_card_games_077 | bird | What percentage of cards without power are in French… | ✅ | 1.00 | 0.67 |
| bird_card_games_078 | bird | What percentage of Japanese translated sets are expa… | ✅ | 1.00 | 0.67 |
| bird_card_games_079 | bird | What kind of printing is on the card that Daren Bade… | ❌ | 0.10 | 0.00 |
| bird_card_games_080 | bird | How many color cards with no borders have been ranke… | ✅ | 1.00 | 1.00 |
| bird_card_games_081 | bird | How many cards are oversized, reprinted, and printed… | ✅ | 1.00 | 1.00 |
| bird_card_games_082 | bird | Please list top three unknown power cards that have … | ✅ | 1.00 | 1.00 |
| bird_card_games_083 | bird | What is the language of the card with the multiverse… | ❌ | 0.14 | 0.00 |
| bird_card_games_084 | bird | Please provide the ids of top three powerful pairs o… | ✅ | 1.00 | 1.00 |
| bird_card_games_085 | bird | What proportion of cards do not have a text box with… | ✅ | 1.00 | 1.00 |
| bird_card_games_086 | bird | What are the card numbers that don't have multiple f… | ❌ | 0.10 | 0.00 |
| bird_card_games_087 | bird | Please provide top three sets that don't appear in M… | ✅ | 1.00 | 1.00 |
| bird_card_games_088 | bird | What languages are available in the set known as Arc… | ❌ | 0.12 | 0.00 |
| bird_card_games_089 | bird | What is the name of set number 5 and its translation… | ❌ | 0.00 | 0.00 |
| bird_card_games_090 | bird | What is the language and expansion type of set numbe… | ❌ | 0.00 | 0.00 |
| bird_card_games_091 | bird | Please list top two sets of cards with their IDs tha… | ✅ | 1.00 | 0.50 |
| bird_card_games_092 | bird | Which set is not available outside of the United Sta… | ❌ | 0.00 | 0.00 |
| bird_card_games_093 | bird | Which Russian set of cards contains the most cards o… | ❌ | 0.12 | 0.00 |
| bird_card_games_094 | bird | What is the percentage of the set of cards that have… | ❌ | 0.10 | 0.00 |
| bird_card_games_095 | bird | How many sets are available just in Japanese and not… | ✅ | 1.00 | 0.67 |
| bird_card_games_096 | bird | How many card border with black color ? List out the… | ❌ | 0.10 | 0.00 |
| bird_card_games_097 | bird | How many cards have frame effect as extendedart? Lis… | ✅ | 1.00 | 1.00 |
| bird_card_games_098 | bird | Among black card borders, which card has full artwor… | ❌ | 0.10 | 0.00 |
| bird_card_games_099 | bird | Point out the language of set id "174"? | ❌ | 0.00 | 0.00 |
| bird_card_games_100 | bird | List out the set name of the set code "ALL". | ❌ | 0.00 | 0.00 |
| bird_card_games_101 | bird | Which foreign language used by "A Pedra Fellwar"? | ❌ | 0.14 | 0.00 |
| bird_card_games_102 | bird | State the set code of the set with release date of 0… | ❌ | 0.11 | 0.00 |
| bird_card_games_103 | bird | Mention the base set size and set code of the set th… | ❌ | 0.11 | 0.00 |
| bird_card_games_104 | bird | Give the code of sets have expansion type of 'expans… | ✅ | 1.00 | 0.67 |
| bird_card_games_105 | bird | Name the foreign name of the card that has boros wat… | ❌ | 0.00 | 0.00 |
| bird_card_games_106 | bird | What is the language and flavor text of the card tha… | ❌ | 0.00 | 0.00 |
| bird_card_games_107 | bird | What is percentage of the cards with a converted Man… | ✅ | 1.00 | 0.67 |
| bird_card_games_108 | bird | Give the code of sets have expansion commander type? | ✅ | 1.00 | 0.67 |
| bird_card_games_109 | bird | Name the foreign name of the card that has abzan wat… | ❌ | 0.00 | 0.00 |
| bird_card_games_110 | bird | What is the language of the card that has azorius wa… | ❌ | 0.10 | 0.00 |
| bird_card_games_111 | bird | Of all the cards that are designed by Aaron Miller, … | ✅ | 1.00 | 1.00 |
| bird_card_games_112 | bird | How many cards available in paper have a positive st… | ✅ | 1.00 | 1.00 |
| bird_card_games_113 | bird | Please list the names of the cards that have a text … | ✅ | 1.00 | 1.00 |
| bird_card_games_114 | bird | What's the unconverted mana cost of the card "Ancest… | ❌ | 0.10 | 0.00 |
| bird_card_games_115 | bird | Among the cards with a white border color, how many … | ✅ | 1.00 | 1.00 |
| bird_card_games_116 | bird | Which of the cards that are a promotional painting h… | ✅ | 1.00 | 1.00 |
| bird_card_games_117 | bird | What's the list of all types for the card "Molimo, M… | ❌ | 0.00 | 0.00 |
| bird_card_games_118 | bird | Please list the websites where I can purchase the ca… | ✅ | 1.00 | 1.00 |
| bird_card_games_119 | bird | How many artists have designed a card with a black b… | ❌ | 0.10 | 0.00 |
| bird_card_games_120 | bird | Which card costs more converted mana, "Serra Angel" … | ❌ | 0.10 | 0.00 |
| bird_card_games_121 | bird | Which artist designed the card whose promotional nam… | ❌ | 0.00 | 0.00 |
| bird_card_games_122 | bird | Please list the names of the top 3 cards with the hi… | ✅ | 1.00 | 1.00 |
| bird_card_games_123 | bird | What's the Italian name of the set of cards with "An… | ✅ | 1.00 | 0.67 |
| bird_card_games_124 | bird | How many translations are there for the set of cards… | ✅ | 1.00 | 0.67 |
| bird_card_games_125 | bird | Please list the names of the cards in the set "Haupt… | ✅ | 1.00 | 0.67 |
| bird_card_games_126 | bird | For the set of cards with "Ancestor's Chosen" in it,… | ✅ | 1.00 | 0.67 |
| bird_card_games_127 | bird | Among the cards in the set "Hauptset Zehnte Edition"… | ✅ | 1.00 | 0.67 |
| bird_card_games_128 | bird | How many cards are there in the base set of "Hauptse… | ❌ | 0.12 | 0.00 |
| bird_card_games_129 | bird | What is the Simplified Chinese translation of the na… | ❌ | 0.00 | 0.00 |
| bird_card_games_130 | bird | Did the set of cards with "Angel of Mercy" appear on… | ✅ | 1.00 | 0.67 |
| bird_card_games_131 | bird | When was the set of cards with "Ancestor's Chosen" r… | ✅ | 1.00 | 0.67 |
| bird_card_games_132 | bird | What is the expansion type of the set "Hauptset Zehn… | ❌ | 0.10 | 0.00 |
| bird_card_games_133 | bird | Among the sets in the block "Ice Age", how many of t… | ✅ | 1.00 | 0.67 |
| bird_card_games_134 | bird | Is the set of cards with Adarkar Valkyrie only avail… | ✅ | 1.00 | 0.67 |
| bird_card_games_135 | bird | Among the sets of cards that have an Italian transla… | ✅ | 1.00 | 0.50 |
| bird_card_games_136 | bird | How many cards in the set Coldsnap have a black bord… | ✅ | 1.00 | 0.67 |
| bird_card_games_137 | bird | Please list the name of the cards in the set Coldsna… | ✅ | 1.00 | 0.67 |
| bird_card_games_138 | bird | Which of these artists have designed a card in the s… | ❌ | 0.14 | 0.00 |
| bird_card_games_139 | bird | What is card number 4 in the set Coldsnap? | ❌ | 0.14 | 0.00 |
| bird_card_games_140 | bird | Among the cards with converted mana cost higher than… | ✅ | 1.00 | 0.67 |
| bird_card_games_141 | bird | What is the Italian flavor text of the card "Ancesto… | ❌ | 0.12 | 0.00 |
| bird_card_games_142 | bird | Please list all the foreign languages in which the c… | ❌ | 0.20 | 0.00 |
| bird_card_games_143 | bird | What's the German type of the card "Ancestor's Chose… | ❌ | 0.12 | 0.00 |
| bird_card_games_144 | bird | Please list the Italian text ruling of all the cards… | ✅ | 1.00 | 0.50 |
| bird_card_games_145 | bird | Please list the Italian names of the cards in the se… | ✅ | 1.00 | 0.50 |
| bird_card_games_146 | bird | When was the ruling for the card 'Reminisce' created… | ❌ | 0.17 | 0.00 |
| bird_card_games_147 | bird | What is the percentage of the cards with a converted… | ✅ | 1.00 | 0.67 |
| bird_card_games_148 | bird | What is the percentage of incredibly powerful cards … | ✅ | 1.00 | 0.67 |
| bird_card_games_149 | bird | What's the code for the set which was released on 20… | ❌ | 0.12 | 0.00 |
| bird_card_games_150 | bird | List the keyrune code for the set whose code is 'PKH… | ❌ | 0.12 | 0.00 |
| bird_card_games_151 | bird | For the set which had 'SS2' as the code, what is its… | ❌ | 0.14 | 0.00 |
| bird_card_games_152 | bird | What's the magic card market name for the set which … | ❌ | 0.00 | 0.00 |
| bird_card_games_153 | bird | For the set "From the Vault: Lore", what is its expa… | ❌ | 0.14 | 0.00 |
| bird_card_games_154 | bird | For the set "Commander 2014 Oversized" , give its pa… | ❌ | 0.14 | 0.00 |
| bird_card_games_155 | bird | For all cards illustrated by Jim Pavelec. and descri… | ✅ | 1.00 | 0.67 |
| bird_card_games_156 | bird | What was the release date for the set which card "Ev… | ❌ | 0.12 | 0.00 |
| bird_card_games_157 | bird | What is the number of cards are there in the set of … | ❌ | 0.12 | 0.00 |
| bird_card_games_158 | bird | List the expansion type of the set "Huitième édition… | ❌ | 0.10 | 0.00 |
| bird_card_games_159 | bird | What's the French name of the set of cards with "Ten… | ✅ | 1.00 | 0.67 |
| bird_card_games_160 | bird | How many translations of the name of the set "Tenth … | ❌ | 0.00 | 0.00 |
| bird_card_games_161 | bird | Tell the Japanese name of the set which card "Fellwa… | ❌ | 0.00 | 0.00 |
| bird_card_games_162 | bird | Which card name in the set 'Journey into Nyx Hero's … | ❌ | 0.00 | 0.00 |
| bird_card_games_163 | bird | What is the release date for the set "Ola de frío"? | ❌ | 0.12 | 0.00 |
| bird_card_games_164 | bird | What was the expansion type for the set which card "… | ❌ | 0.10 | 0.00 |
| bird_card_games_165 | bird | How many cards are there in the set 'World Champions… | ✅ | 1.00 | 0.67 |
| bird_card_games_166 | bird | Show the Simplified Chinese translation of the name … | ❌ | 0.00 | 0.00 |
| bird_card_games_167 | bird | For all the set of cards that has Japanese translati… | ❌ | 0.12 | 0.00 |
| bird_card_games_168 | bird | For all the set of cards that has Brazil Portuguese … | ❌ | 0.12 | 0.00 |
| bird_card_games_169 | bird | What are the available printing types of the cards t… | ✅ | 1.00 | 1.00 |
| bird_card_games_170 | bird | What is the unique id of the set that has the highes… | ❌ | 0.00 | 0.00 |
| bird_card_games_171 | bird | Among the cards that doesn't have multiple faces on … | ✅ | 1.00 | 1.00 |
| bird_card_games_172 | bird | What is the most common visual frame effects among t… | ❌ | 0.10 | 0.00 |
| bird_card_games_173 | bird | How many cards with unknown power that can't be foun… | ✅ | 1.00 | 1.00 |
| bird_card_games_174 | bird | Among the sets whose expansion type is Commander, wh… | ✅ | 1.00 | 1.00 |
| bird_card_games_175 | bird | In duels, what are the top 10 cards with the highest… | ✅ | 1.00 | 0.67 |
| bird_card_games_176 | bird | When was the oldest mythic card released and what ar… | ❌ | 0.25 | 0.00 |
| bird_card_games_177 | bird | How many cards did Volkan BaÇµa illustrated whose fo… | ✅ | 1.00 | 0.67 |
| bird_card_games_178 | bird | How many rare enchantment Abundance cards are there … | ✅ | 1.00 | 0.67 |
| bird_card_games_179 | bird | Which of the play format has the highest number of b… | ❌ | 0.20 | 0.00 |
| bird_card_games_180 | bird | What is the language of the "Battlebond" set? | ❌ | 0.11 | 0.00 |
| bird_card_games_181 | bird | Who is the illustrator that illustrated the least am… | ✅ | 1.00 | 0.67 |
| bird_card_games_182 | bird | Among the cards whose version of frame style is 1997… | ✅ | 1.00 | 0.67 |
| bird_card_games_183 | bird | Which cards are ranked 1st on EDHRec? List all of th… | ✅ | 1.00 | 0.67 |
| bird_card_games_184 | bird | What is the annual average number of sets that were … | ✅ | 1.00 | 0.67 |
| bird_card_games_185 | bird | List the artists who illustrated cards with black bo… | ✅ | 1.00 | 1.00 |
| bird_card_games_186 | bird | Find the uuid of cards in which the old school forma… | ❌ | 0.10 | 0.00 |
| bird_card_games_187 | bird | Among the card designed by Matthew D. Wilson, how ma… | ❌ | 0.10 | 0.00 |
| bird_card_games_188 | bird | What are the rulings for the card named and designed… | ✅ | 1.00 | 0.67 |
| bird_card_games_189 | bird | List the names of all the cards in the set Hour of D… | ✅ | 1.00 | 0.50 |
| bird_card_games_190 | bird | Find and list the names of sets which doesn't have J… | ✅ | 1.00 | 0.67 |
| bird_card_games_191 | bird | List all the frame styles and cards Allen Williams w… | ✅ | 1.00 | 0.67 |
