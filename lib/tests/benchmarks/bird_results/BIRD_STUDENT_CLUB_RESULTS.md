# BIRD — student_club — Results

**Conditions:** `keyword`  
**Queries:** 158  
**Last run:** 2026-08-25 09:56 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 35% |
| Hit@3 | 39% |
| Hit@5 | 55% |
| MRR | 46% |

```
Hit@5 (% of 158 queries)

  keyword         ████████░░░░░░░   55%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.266 |
| P@3 | 0.383 |
| R@3 | 0.213 |
| F1@5 | 0.343 |
| P@5 | 0.424 |
| R@5 | 0.310 |
| F1@10 | 0.427 |
| P@10 | 0.289 |
| R@10 | 0.897 |
| F1@Ideal-K | 0.262 |
| P@Ideal-K | 0.383 |
| R@Ideal-K | 0.209 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 158 | 35% | 0.46 | 0.26 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_student_club_001 | bird | What's Angela Sanders's major? | ❌ | 0.12 | 0.00 |
| bird_student_club_002 | bird | How many students in the Student_Club are from the C… | ❌ | 0.11 | 0.00 |
| bird_student_club_003 | bird | Please list the full names of the students in the St… | ❌ | 0.12 | 0.00 |
| bird_student_club_004 | bird | How many students of the Student_Club have attended … | ❌ | 0.33 | 0.00 |
| bird_student_club_005 | bird | Please list the phone numbers of the students from t… | ❌ | 0.33 | 0.50 |
| bird_student_club_006 | bird | Among the students from the Student_Club who attende… | ❌ | 0.33 | 0.50 |
| bird_student_club_007 | bird | What is the event that has the highest attendance of… | ✅ | 1.00 | 1.00 |
| bird_student_club_008 | bird | Which college is the vice president of the Student_C… | ❌ | 0.11 | 0.00 |
| bird_student_club_009 | bird | Please list the event names of all the events attend… | ✅ | 1.00 | 0.50 |
| bird_student_club_010 | bird | How many events of the Student_Club did Sacha Harris… | ❌ | 0.25 | 0.00 |
| bird_student_club_011 | bird | Among the events attended by more than 10 members of… | ❌ | 0.25 | 0.00 |
| bird_student_club_012 | bird | List all the names of events that had an attendance … | ✅ | 1.00 | 0.67 |
| bird_student_club_013 | bird | What is the average attendance of meetings in 2020? | ✅ | 1.00 | 0.67 |
| bird_student_club_014 | bird | What is the most expensive item that was spent in su… | ❌ | 0.14 | 0.00 |
| bird_student_club_015 | bird | How many members of the Student_Club have majored En… | ❌ | 0.12 | 0.00 |
| bird_student_club_016 | bird | List the full name of all the members of the Student… | ❌ | 0.25 | 0.00 |
| bird_student_club_017 | bird | List the last name of all the students who majored L… | ❌ | 0.12 | 0.00 |
| bird_student_club_018 | bird | What county did Sherri Ramsey grew up? | ❌ | 0.17 | 0.00 |
| bird_student_club_019 | bird | What college offers the major that Tyler Hewitt took… | ✅ | 1.00 | 0.67 |
| bird_student_club_020 | bird | What is the amount of the funds that the Vice Presid… | ❌ | 0.10 | 0.00 |
| bird_student_club_021 | bird | How much did the Student_Club members spend on food … | ❌ | 0.25 | 0.00 |
| bird_student_club_022 | bird | What city and state did the President of the Student… | ❌ | 0.14 | 0.00 |
| bird_student_club_023 | bird | List the full name of the Student_Club members that … | ❌ | 0.20 | 0.00 |
| bird_student_club_024 | bird | How much did the Student_Club members spend on adver… | ❌ | 0.25 | 0.00 |
| bird_student_club_025 | bird | What department offers the major that Pierce and Gui… | ✅ | 1.00 | 0.67 |
| bird_student_club_026 | bird | What is the total budgeted amount for all category i… | ❌ | 0.14 | 0.00 |
| bird_student_club_027 | bird | Was each expense in October Meeting on October 8, 20… | ✅ | 1.00 | 0.50 |
| bird_student_club_028 | bird | Calculate the total average cost that Elijah Allen s… | ❌ | 0.12 | 0.00 |
| bird_student_club_029 | bird | Calculate the difference of the total amount spent i… | ❌ | 0.14 | 0.00 |
| bird_student_club_030 | bird | Give the location for "Spring Budget Review". | ❌ | 0.17 | 0.00 |
| bird_student_club_031 | bird | What was the cost for the "Posters" on 2019/9/4? | ❌ | 0.14 | 0.00 |
| bird_student_club_032 | bird | With the biggest budget for the "Food", what was the… | ✅ | 1.00 | 1.00 |
| bird_student_club_033 | bird | What was the notes of the fundraising on 2019/9/14? | ❌ | 0.00 | 0.00 |
| bird_student_club_034 | bird | How many majors are there in "College of Humanities … | ❌ | 0.10 | 0.00 |
| bird_student_club_035 | bird | Tell the phone number of "Carlo Jacobs". | ❌ | 0.11 | 0.00 |
| bird_student_club_036 | bird | Tell the hometown county for "Adela O'Gallagher". | ❌ | 0.17 | 0.00 |
| bird_student_club_037 | bird | For all the budgets for "November Meeting", how many… | ❌ | 0.25 | 0.00 |
| bird_student_club_038 | bird | Provide the total number of the budget amount for "S… | ✅ | 1.00 | 0.67 |
| bird_student_club_039 | bird | What is the status of the event which bought "Post C… | ❌ | 0.14 | 0.00 |
| bird_student_club_040 | bird | What was Brent Thomason's major? | ❌ | 0.12 | 0.00 |
| bird_student_club_041 | bird | For all the club members from "Business" major, how … | ❌ | 0.12 | 0.00 |
| bird_student_club_042 | bird | What's Christof Nielson's zip code type? | ❌ | 0.17 | 0.00 |
| bird_student_club_043 | bird | State the major name for the Vice President of the c… | ✅ | 1.00 | 0.67 |
| bird_student_club_044 | bird | Where is the hometown state for "Sacha Harrison"? | ❌ | 0.17 | 0.00 |
| bird_student_club_045 | bird | Which department was the President of the club in? | ❌ | 0.11 | 0.00 |
| bird_student_club_046 | bird | State the date Connor Hilton paid his/her dues. | ❌ | 0.11 | 0.00 |
| bird_student_club_047 | bird | Who was the first one paid his/her dues? Tell the fu… | ❌ | 0.12 | 0.00 |
| bird_student_club_048 | bird | How many times was the budget in Advertisement for "… | ✅ | 1.00 | 0.67 |
| bird_student_club_049 | bird | What percentage was the budget for Parking to the to… | ✅ | 1.00 | 0.67 |
| bird_student_club_050 | bird | What is the total cost of the pizzas for all the eve… | ❌ | 0.14 | 0.00 |
| bird_student_club_051 | bird | How many cities are there in Orange County, Virginia… | ❌ | 0.20 | 0.00 |
| bird_student_club_052 | bird | List all of the College of Humanities and Social Sci… | ❌ | 0.00 | 0.00 |
| bird_student_club_053 | bird | Where is Amy Firth's hometown? | ❌ | 0.20 | 0.00 |
| bird_student_club_054 | bird | What are the expenses of the budget with the lowest … | ✅ | 1.00 | 0.67 |
| bird_student_club_055 | bird | List all the members who attended the event "October… | ✅ | 1.00 | 0.50 |
| bird_student_club_056 | bird | Which college do most of the members go to? | ❌ | 0.11 | 0.00 |
| bird_student_club_057 | bird | What does the person with the phone number "809-555-… | ✅ | 1.00 | 0.67 |
| bird_student_club_058 | bird | Which event has the highest budget amount? | ✅ | 1.00 | 1.00 |
| bird_student_club_059 | bird | List all the expenses incurred by the vice president… | ❌ | 0.17 | 0.00 |
| bird_student_club_060 | bird | How many members attended the "Women's Soccer" event… | ❌ | 0.25 | 0.00 |
| bird_student_club_061 | bird | When did the member, Casey Mason, received the incom… | ❌ | 0.12 | 0.00 |
| bird_student_club_062 | bird | How many of the members' hometowns are from Maryland… | ❌ | 0.20 | 0.00 |
| bird_student_club_063 | bird | How many events did the member with the phone number… | ✅ | 1.00 | 0.67 |
| bird_student_club_064 | bird | List all the members of the "School of Applied Scien… | ❌ | 0.12 | 0.00 |
| bird_student_club_065 | bird | Among all the closed events, which event has the hig… | ✅ | 1.00 | 0.67 |
| bird_student_club_066 | bird | How many student have the position of president? | ❌ | 0.11 | 0.00 |
| bird_student_club_067 | bird | What is the highest amount of budget spend for an ev… | ✅ | 1.00 | 1.00 |
| bird_student_club_068 | bird | How many meeting events were held in 2020? | ❌ | 0.25 | 0.00 |
| bird_student_club_069 | bird | What is the total amount of money spent for food? | ❌ | 0.00 | 0.00 |
| bird_student_club_070 | bird | List the name of students that have attended more th… | ❌ | 0.14 | 0.00 |
| bird_student_club_071 | bird | Among the students majored in interior design, who h… | ❌ | 0.25 | 0.40 |
| bird_student_club_072 | bird | State the name of students from Georgetown, South Ca… | ❌ | 0.17 | 0.00 |
| bird_student_club_073 | bird | How many income generated by Grant Gilmour? | ✅ | 1.00 | 0.67 |
| bird_student_club_074 | bird | Which student was able to generate income more than … | ✅ | 1.00 | 0.67 |
| bird_student_club_075 | bird | What is the total expense for the Yearly Kickoff? | ✅ | 1.00 | 0.50 |
| bird_student_club_076 | bird | Which student has been entrusted to manage the budge… | ✅ | 1.00 | 0.40 |
| bird_student_club_077 | bird | Which students manage to generate the highest income… | ✅ | 1.00 | 0.67 |
| bird_student_club_078 | bird | Which event has the lowest cost? | ✅ | 1.00 | 0.50 |
| bird_student_club_079 | bird | Based on the total cost for all event, what is the p… | ❌ | 0.20 | 0.00 |
| bird_student_club_080 | bird | What is the ratio between students majored in financ… | ❌ | 0.10 | 0.00 |
| bird_student_club_081 | bird | Indicate the top source of funds received in Septemb… | ❌ | 0.00 | 0.00 |
| bird_student_club_082 | bird | Provide the full name and email address of the Stude… | ❌ | 0.11 | 0.00 |
| bird_student_club_083 | bird | How many members of the Student_Club have major in '… | ❌ | 0.33 | 0.00 |
| bird_student_club_084 | bird | How many members did attend the event 'Community The… | ✅ | 1.00 | 0.67 |
| bird_student_club_085 | bird | Provide the number of events attended by Luisa Guidi… | ❌ | 0.14 | 0.00 |
| bird_student_club_086 | bird | On average, how much did the Student_Club spend on f… | ❌ | 0.11 | 0.00 |
| bird_student_club_087 | bird | Name the event with the highest amount spent on adve… | ✅ | 1.00 | 0.67 |
| bird_student_club_088 | bird | Did Maya Mclean attend the 'Women's Soccer' event? | ❌ | 0.25 | 0.00 |
| bird_student_club_089 | bird | Among all events hold by the Student_Club in 2019, f… | ❌ | 0.25 | 0.00 |
| bird_student_club_090 | bird | Indicate the cost of posters for 'September Speaker'… | ❌ | 0.20 | 0.00 |
| bird_student_club_091 | bird | What is the most popular size of t-shirt ordered by … | ❌ | 0.12 | 0.00 |
| bird_student_club_092 | bird | Indicate the name of the closed event whose cost has… | ✅ | 1.00 | 1.00 |
| bird_student_club_093 | bird | Identify the type of expenses and their total value … | ❌ | 0.14 | 0.00 |
| bird_student_club_094 | bird | Calculate the amount budgeted for 'April Speaker' ev… | ✅ | 1.00 | 0.67 |
| bird_student_club_095 | bird | Among the budgets for Food, which one has the highes… | ❌ | 0.11 | 0.00 |
| bird_student_club_096 | bird | Among the budgets for Advertising, list out top thre… | ❌ | 0.11 | 0.00 |
| bird_student_club_097 | bird | Calculate the total cost spent for Parking in the li… | ❌ | 0.12 | 0.00 |
| bird_student_club_098 | bird | Mention the total expense used on 8/20/2019. | ✅ | 1.00 | 1.00 |
| bird_student_club_099 | bird | List out the full name and total cost that member id… | ✅ | 1.00 | 0.67 |
| bird_student_club_100 | bird | State what kind of expenses that Sacha Harrison incu… | ❌ | 0.14 | 0.00 |
| bird_student_club_101 | bird | What kind of expenses incurred by members who have X… | ❌ | 0.17 | 0.00 |
| bird_student_club_102 | bird | Mention the zip code of member who incurred less tha… | ✅ | 1.00 | 0.67 |
| bird_student_club_103 | bird | State the name of major that Phillip Cullen has join… | ✅ | 1.00 | 0.67 |
| bird_student_club_104 | bird | List out the position of members who joined major of… | ✅ | 1.00 | 0.67 |
| bird_student_club_105 | bird | How many members of Business have the Medium size of… | ❌ | 0.12 | 0.00 |
| bird_student_club_106 | bird | List out the type of events which have remaining bud… | ✅ | 1.00 | 0.67 |
| bird_student_club_107 | bird | Mention the category of events which were held at MU… | ❌ | 0.20 | 0.00 |
| bird_student_club_108 | bird | What is the category of event which was taken place … | ✅ | 1.00 | 0.67 |
| bird_student_club_109 | bird | State the name of major that Vice President has join… | ✅ | 1.00 | 0.67 |
| bird_student_club_110 | bird | Calculate the percentage of members who are major Bu… | ✅ | 1.00 | 0.67 |
| bird_student_club_111 | bird | State the category of events were held at MU 215. | ❌ | 0.17 | 0.00 |
| bird_student_club_112 | bird | How many income are received with an amount of 50? | ✅ | 1.00 | 1.00 |
| bird_student_club_113 | bird | Among the members, how many of them have an extra la… | ❌ | 0.12 | 0.00 |
| bird_student_club_114 | bird | In the College of Agriculture and Applied Sciences, … | ❌ | 0.00 | 0.00 |
| bird_student_club_115 | bird | List the last name of members with a major in enviro… | ✅ | 1.00 | 0.67 |
| bird_student_club_116 | bird | What are the budget category of the events located a… | ✅ | 1.00 | 0.67 |
| bird_student_club_117 | bird | List the city and state of members enrolled under el… | ❌ | 0.14 | 0.00 |
| bird_student_club_118 | bird | What is the name of the social event that was attend… | ❌ | 0.33 | 0.50 |
| bird_student_club_119 | bird | What is the last name and position of the student th… | ❌ | 0.14 | 0.00 |
| bird_student_club_120 | bird | List the last name of the members of the club that a… | ❌ | 0.25 | 0.00 |
| bird_student_club_121 | bird | Among the members with t-shirt size of medium, what … | ❌ | 0.10 | 0.00 |
| bird_student_club_122 | bird | Which countries have zip codes with post office boxe… | ❌ | 0.17 | 0.00 |
| bird_student_club_123 | bird | What are the zip codes that have post office boxes i… | ❌ | 0.14 | 0.00 |
| bird_student_club_124 | bird | List the names of closed event as "game" that was cl… | ✅ | 1.00 | 1.00 |
| bird_student_club_125 | bird | Please provide links to events for members who have … | ❌ | 0.17 | 0.00 |
| bird_student_club_126 | bird | Which members who were approved from 1/10/2019 to 11… | ❌ | 0.50 | 0.40 |
| bird_student_club_127 | bird | Please indicate the college of the person whose firs… | ✅ | 1.00 | 0.67 |
| bird_student_club_128 | bird | Please list the phone numbers of the members who maj… | ❌ | 0.10 | 0.00 |
| bird_student_club_129 | bird | List emails of people who paid more than 20 dollars … | ❌ | 0.17 | 0.00 |
| bird_student_club_130 | bird | How many members have education major in the College… | ✅ | 1.00 | 0.67 |
| bird_student_club_131 | bird | What is the percentage of the events that went over … | ❌ | 0.11 | 0.00 |
| bird_student_club_132 | bird | Give the event ID, location, and status of events co… | ✅ | 1.00 | 1.00 |
| bird_student_club_133 | bird | List the expenses that spend more than fifty dollars… | ❌ | 0.17 | 0.00 |
| bird_student_club_134 | bird | Find the full name of members whose t-shirt size is … | ❌ | 0.12 | 0.00 |
| bird_student_club_135 | bird | Calculate the percentage of zip codes that are PO bo… | ❌ | 0.17 | 0.00 |
| bird_student_club_136 | bird | List the name and location of events that underspend… | ❌ | 0.20 | 0.00 |
| bird_student_club_137 | bird | Find the name and date of events with expenses for p… | ❌ | 0.25 | 0.00 |
| bird_student_club_138 | bird | What is the name and major of members who had to spe… | ✅ | 1.00 | 0.50 |
| bird_student_club_139 | bird | In the events with more than forty incomes, list the… | ❌ | 0.17 | 0.00 |
| bird_student_club_140 | bird | Among the members who incurred expenses in more than… | ❌ | 0.25 | 0.40 |
| bird_student_club_141 | bird | What is the average amount paid by students in a pos… | ❌ | 0.11 | 0.00 |
| bird_student_club_142 | bird | List the name of events with less than average parki… | ❌ | 0.25 | 0.00 |
| bird_student_club_143 | bird | What is the percentage of the cost for the meeting e… | ❌ | 0.20 | 0.00 |
| bird_student_club_144 | bird | Which budget allowed the most money for water, chips… | ✅ | 1.00 | 0.67 |
| bird_student_club_145 | bird | List the full name of the top five members who spend… | ❌ | 0.17 | 0.00 |
| bird_student_club_146 | bird | Give the full name and contact number of members who… | ❌ | 0.17 | 0.00 |
| bird_student_club_147 | bird | Calculate the difference in the percentage of member… | ❌ | 0.20 | 0.00 |
| bird_student_club_148 | bird | What is the major of Garrett Gerke and which departm… | ✅ | 1.00 | 0.67 |
| bird_student_club_149 | bird | Write the full name of the member who spent money fo… | ✅ | 1.00 | 0.67 |
| bird_student_club_150 | bird | List the last names of students under the Elementary… | ✅ | 1.00 | 0.67 |
| bird_student_club_151 | bird | What category was budgeted for the 'January Speaker'… | ✅ | 1.00 | 0.67 |
| bird_student_club_152 | bird | List the event names which were budgeted for the foo… | ✅ | 1.00 | 0.67 |
| bird_student_club_153 | bird | Write the full names of students who received funds … | ❌ | 0.17 | 0.00 |
| bird_student_club_154 | bird | Which budget category does the expense 'Posters' fal… | ✅ | 1.00 | 1.00 |
| bird_student_club_155 | bird | Write the full name of the club member with the posi… | ✅ | 1.00 | 0.67 |
| bird_student_club_156 | bird | Calculate the total amount spent on speaker gifts an… | ✅ | 1.00 | 0.67 |
| bird_student_club_157 | bird | Where is the hometown of Garrett Gerke? | ❌ | 0.20 | 0.00 |
| bird_student_club_158 | bird | Which student has the hometown of Lincolnton, North … | ❌ | 0.17 | 0.00 |
