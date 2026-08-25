# BIRD — codebase_community — Results

**Conditions:** `keyword`  
**Queries:** 186  
**Last run:** 2026-08-25 09:35 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 44% |
| Hit@3 | 47% |
| Hit@5 | 58% |
| MRR | 52% |

```
Hit@5 (% of 186 queries)

  keyword         █████████░░░░░░   58%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.359 |
| P@3 | 0.452 |
| R@3 | 0.321 |
| F1@5 | 0.392 |
| P@5 | 0.433 |
| R@5 | 0.403 |
| F1@10 | 0.368 |
| P@10 | 0.253 |
| R@10 | 0.815 |
| F1@Ideal-K | 0.355 |
| P@Ideal-K | 0.452 |
| R@Ideal-K | 0.310 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 186 | 44% | 0.52 | 0.36 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_codebase_community_001 | bird | Which user has a higher reputation, Harlan or Jarrod… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_002 | bird | Please list the display names of all the users whose… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_003 | bird | How many users last accessed the website after 2014/… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_004 | bird | What is the display name of the user who has the mos… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_005 | bird | Among the users who have more than 100 upvotes, how … | ✅ | 1.00 | 1.00 |
| bird_codebase_community_006 | bird | How many users with more than 10 views created their… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_007 | bird | How many posts does the user csgillespie own? | ✅ | 1.00 | 0.67 |
| bird_codebase_community_008 | bird | Please list the titles of the posts owned by the use… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_009 | bird | Who is the owner of the post "Eliciting priors from … | ❌ | 0.12 | 0.00 |
| bird_codebase_community_010 | bird | What is the title of the post that is owned by csgil… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_011 | bird | What is the display name of the user who is the owne… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_012 | bird | What is the total number of comments of all the post… | ❌ | 0.50 | 0.50 |
| bird_codebase_community_013 | bird | For the post that got the most number of answers own… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_014 | bird | What is the display name of the user who last edited… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_015 | bird | Among the posts owned by csgillespie, how many of th… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_016 | bird | Please list the display names of all the users who o… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_017 | bird | Among the posts owned by an elder user, how many of … | ✅ | 1.00 | 0.67 |
| bird_codebase_community_018 | bird | What is the location of the owner of the post "Elici… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_019 | bird | From which post is the tag "bayesian" excerpted from… | ❌ | 0.10 | 0.00 |
| bird_codebase_community_020 | bird | From which post is the most popular tag excerpted fr… | ❌ | 0.10 | 0.00 |
| bird_codebase_community_021 | bird | How many badges has the user csgillespie obtained? | ✅ | 1.00 | 0.67 |
| bird_codebase_community_022 | bird | Please list the names of the badges obtained by csgi… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_023 | bird | Among the badges obtained by csgillespie, how many o… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_024 | bird | What is the display name of the user who has obtaine… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_025 | bird | What is the average score of the posts owned by the … | ✅ | 1.00 | 0.67 |
| bird_codebase_community_026 | bird | What is the average number of badges obtained by a u… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_027 | bird | Among the posts with a score of over 5, what is the … | ✅ | 1.00 | 0.67 |
| bird_codebase_community_028 | bird | How many votes did the user No.58 take on 2010/7/19? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_029 | bird | Indicate the creation date of the maximum number of … | ❌ | 0.14 | 0.00 |
| bird_codebase_community_030 | bird | Give the number of "Revival" badges. | ❌ | 0.25 | 0.00 |
| bird_codebase_community_031 | bird | What is the title for the post which got the highest… | ❌ | 0.10 | 0.00 |
| bird_codebase_community_032 | bird | For the post which got 1910 view counts, how many co… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_033 | bird | User No.3025 gave a comment at 20:29:39 on 2014/4/23… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_034 | bird | Give the only one comment text of the post with pare… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_035 | bird | User No.23853 gave a comment to a post at 9:08:18 on… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_036 | bird | For the owner user of post No. 65041, what is his/he… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_037 | bird | For the user with the display name of "Tiago Pasqual… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_038 | bird | Provide the display name of the user who made the vo… | ❌ | 0.14 | 0.00 |
| bird_codebase_community_039 | bird | Give the number of votes for the post about data vis… | ❌ | 0.50 | 0.67 |
| bird_codebase_community_040 | bird | For the user whose display name is "DatEpicCoderGuyW… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_041 | bird | For the user No.24, how many times is the number of … | ✅ | 1.00 | 0.67 |
| bird_codebase_community_042 | bird | How many views did the post titled 'Integration of W… | ❌ | 0.10 | 0.00 |
| bird_codebase_community_043 | bird | Write the contents of comments with a score of 17. | ✅ | 1.00 | 1.00 |
| bird_codebase_community_044 | bird | Which user has the website URL listed at 'http://sta… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_045 | bird | What is the badge name that user 'SilentGhost' obtai… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_046 | bird | Name the user that commented 'thank you user93!' | ❌ | 0.12 | 0.00 |
| bird_codebase_community_047 | bird | Write all comments made by user 'A Lion.' | ✅ | 1.00 | 0.67 |
| bird_codebase_community_048 | bird | Which user made a post titled 'Understanding what Da… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_049 | bird | Write all comments made on the post titled 'How does… | ✅ | 1.00 | 0.50 |
| bird_codebase_community_050 | bird | Name 10 users with the badge name 'Necromancer.' | ✅ | 1.00 | 0.67 |
| bird_codebase_community_051 | bird | Who is the editor of the post titled 'Open source to… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_052 | bird | List the title of posts which were edited by Vebjorn… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_053 | bird | What is the total score of the posts edited by Yevge… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_054 | bird | Write all the comments left by users who edited the … | ❌ | 0.14 | 0.00 |
| bird_codebase_community_055 | bird | How much is the total bounty amount of the post titl… | ❌ | 0.17 | 0.00 |
| bird_codebase_community_056 | bird | Which user added a bounty amount of 50 to the post t… | ❌ | 0.14 | 0.00 |
| bird_codebase_community_057 | bird | Calculate the average view count of each post tagged… | ❌ | 0.10 | 0.00 |
| bird_codebase_community_058 | bird | Give the total number of comments posted by user ID … | ✅ | 1.00 | 1.00 |
| bird_codebase_community_059 | bird | Which user ID has the highest reputation? | ❌ | 0.00 | 0.00 |
| bird_codebase_community_060 | bird | Which user ID has the lowest view? | ❌ | 0.00 | 0.00 |
| bird_codebase_community_061 | bird | How many users are awarded with supporter badge duri… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_062 | bird | How many users are awarded with more than 5 badges? | ❌ | 0.20 | 0.00 |
| bird_codebase_community_063 | bird | How many users from New York have a teacher and supp… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_064 | bird | Which user created post ID 1 and what is the reputat… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_065 | bird | Which user have only one post history per post and h… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_066 | bird | Which users have posted the most comments. List out … | ❌ | 0.20 | 0.00 |
| bird_codebase_community_067 | bird | How many users from India have the teacher badges? | ✅ | 1.00 | 0.67 |
| bird_codebase_community_068 | bird | What is the percentage difference of student badges … | ✅ | 1.00 | 1.00 |
| bird_codebase_community_069 | bird | What are the post history type IDs for post ID 3720 … | ❌ | 0.00 | 0.00 |
| bird_codebase_community_070 | bird | List out all post that are related to post ID 61217 … | ❌ | 0.00 | 0.00 |
| bird_codebase_community_071 | bird | What is the score and the link type ID for post ID 3… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_072 | bird | List out all post ID with score more than 60 and lis… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_073 | bird | What is the sum of favourite count gained by user ID… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_074 | bird | What is the average of the up votes and the average … | ❌ | 0.50 | 0.50 |
| bird_codebase_community_075 | bird | How many users obtained the "Announcer" badge? | ❌ | 0.20 | 0.00 |
| bird_codebase_community_076 | bird | List out the name of badges that users obtained on 7… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_077 | bird | How many positive comments are there on the list? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_078 | bird | State the detailed content of the comment which was … | ❌ | 0.12 | 0.00 |
| bird_codebase_community_079 | bird | How many posts have a score of 10 on the list? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_080 | bird | What are the name of badge that users who have the h… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_081 | bird | Mention the reputation of users who had obtained the… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_082 | bird | What is the name of badge that the user whose displa… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_083 | bird | List out the dates that users who are located in Roc… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_084 | bird | Among the users who obtained the "Teacher" badge, ca… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_085 | bird | Among the users who obtained the "Organizer" badges,… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_086 | bird | What is the comment's rating score of the post which… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_087 | bird | What is the detailed content of the comment of the p… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_088 | bird | List out the age of users who located in Vienna, Aus… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_089 | bird | How many adults who obtained the badge Supporter? | ❌ | 0.25 | 0.00 |
| bird_codebase_community_090 | bird | State the number of views of users who obtained the … | ✅ | 1.00 | 0.67 |
| bird_codebase_community_091 | bird | What are the name of badges that users who have the … | ✅ | 1.00 | 1.00 |
| bird_codebase_community_092 | bird | State the name of badge that the user whose display … | ❌ | 0.20 | 0.00 |
| bird_codebase_community_093 | bird | How many elders obtained the "Supporter" badge? | ❌ | 0.25 | 0.00 |
| bird_codebase_community_094 | bird | What is the name of user with the ID of 30? | ❌ | 0.00 | 0.00 |
| bird_codebase_community_095 | bird | How many users were from New York? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_096 | bird | How many votes were made in 2010? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_097 | bird | How many users were adult? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_098 | bird | Which users have the highest number of views? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_099 | bird | Calculate the ratio of votes in 2010 and 2011. | ✅ | 1.00 | 1.00 |
| bird_codebase_community_100 | bird | What is the name of tags used by John Salvatier's? | ❌ | 0.12 | 0.00 |
| bird_codebase_community_101 | bird | How many posts were created by Daniel Vassallo? | ❌ | 0.17 | 0.00 |
| bird_codebase_community_102 | bird | How many votes were made by Harlan? | ✅ | 1.00 | 0.50 |
| bird_codebase_community_103 | bird | Which post by slashnick has the most answers count? … | ❌ | 0.20 | 0.00 |
| bird_codebase_community_104 | bird | Among posts by Harvey Motulsky and Noah Snyder, whic… | ✅ | 1.00 | 0.50 |
| bird_codebase_community_105 | bird | How many posts by Matt Parker have more than 4 votes… | ✅ | 1.00 | 0.40 |
| bird_codebase_community_106 | bird | How many negative comments did Neil McGuigan get in … | ✅ | 1.00 | 0.50 |
| bird_codebase_community_107 | bird | State all the tags used by Mark Meckes in his posts … | ✅ | 1.00 | 0.40 |
| bird_codebase_community_108 | bird | List all the name of users that obtained the Organiz… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_109 | bird | Based on posts posted by Community, calculate the pe… | ❌ | 0.17 | 0.00 |
| bird_codebase_community_110 | bird | Calculate the difference in view count from post pos… | ✅ | 1.00 | 0.50 |
| bird_codebase_community_111 | bird | How many users received commentator badges in 2014? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_112 | bird | How many posts were created on 21st July, 2010? | ❌ | 0.17 | 0.00 |
| bird_codebase_community_113 | bird | What are the display names and ages of user who got … | ❌ | 0.12 | 0.00 |
| bird_codebase_community_114 | bird | Provide the last edit date and last edit user ID for… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_115 | bird | How many negative comments were given by user ID 13? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_116 | bird | Describe the post title which got positive comments … | ✅ | 1.00 | 0.50 |
| bird_codebase_community_117 | bird | Provide the badge names received in 2011 for the use… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_118 | bird | Provide the users' display names and available websi… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_119 | bird | Describe the post history counts and last edit date … | ❌ | 0.14 | 0.00 |
| bird_codebase_community_120 | bird | Describe the last accessed date and location of the … | ✅ | 1.00 | 0.67 |
| bird_codebase_community_121 | bird | Provide the related post title of "How to tell if so… | ❌ | 0.10 | 0.00 |
| bird_codebase_community_122 | bird | List the post IDs and badge names of the user Samuel… | ❌ | 0.25 | 0.00 |
| bird_codebase_community_123 | bird | What is the owner's display name of the most popular… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_124 | bird | Mention the display name and location of the user wh… | ❌ | 0.10 | 0.00 |
| bird_codebase_community_125 | bird | Write down the related posts titles and link type ID… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_126 | bird | Describe the display name of the parent ID for child… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_127 | bird | Under the vote type of 8, provide the display names … | ❌ | 0.17 | 0.00 |
| bird_codebase_community_128 | bird | What are the titles of the top 5 posts with the high… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_129 | bird | How many tags have post count between 5,000 to 7,000… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_130 | bird | What is the owner user id of the most valuable post? | ❌ | 0.00 | 0.00 |
| bird_codebase_community_131 | bird | How old is the most influential user? | ❌ | 0.12 | 0.00 |
| bird_codebase_community_132 | bird | How many posts with votes that were created in 2011 … | ✅ | 1.00 | 1.00 |
| bird_codebase_community_133 | bird | What is the id of the youngest user? | ❌ | 0.00 | 0.00 |
| bird_codebase_community_134 | bird | What is the sum of score of the post on 2010-07-19? | ❌ | 0.00 | 0.00 |
| bird_codebase_community_135 | bird | What is the average monthly number of links created … | ✅ | 1.00 | 0.67 |
| bird_codebase_community_136 | bird | Among the posts that were voted by user 1465, what i… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_137 | bird | What is the title of the post with the oldest post l… | ❌ | 0.10 | 0.00 |
| bird_codebase_community_138 | bird | What is the display name of the user who acquired th… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_139 | bird | When did 'chl' cast its first vote in a post? | ❌ | 0.17 | 0.00 |
| bird_codebase_community_140 | bird | What is the date when the youngest user made his or … | ❌ | 0.11 | 0.00 |
| bird_codebase_community_141 | bird | What is the display name of the user who acquired th… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_142 | bird | Among the users located in United Kingdom, how many … | ✅ | 1.00 | 0.67 |
| bird_codebase_community_143 | bird | What is the average number of posts voted by the old… | ❌ | 0.14 | 0.00 |
| bird_codebase_community_144 | bird | Who has the highest reputation? Please give the disp… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_145 | bird | How many users whose reputations are higher than 200… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_146 | bird | Please list all display names of users who are adult… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_147 | bird | How many posts did Jay Stevens have in 2010? | ✅ | 1.00 | 0.67 |
| bird_codebase_community_148 | bird | Which post by Harvey Motulsky has the most views? Pl… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_149 | bird | Which post has the highest score? Please give its id… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_150 | bird | What is the average score of Stephen Turner's posts? | ❌ | 0.10 | 0.00 |
| bird_codebase_community_151 | bird | Please list the users' display names whose posts had… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_152 | bird | Which is the most valuable post in 2010? Please give… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_153 | bird | What is the percentage of posts whose owners had a r… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_154 | bird | Identify the percentage of teenage users. | ❌ | 0.12 | 0.00 |
| bird_codebase_community_155 | bird | Identify the total views on the post 'Computer Game … | ❌ | 0.14 | 0.00 |
| bird_codebase_community_156 | bird | Identify the total number of posts with views above … | ✅ | 1.00 | 1.00 |
| bird_codebase_community_157 | bird | How many comments were added to the post with the hi… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_158 | bird | Identify the number of posts that have been viewed o… | ❌ | 0.50 | 0.00 |
| bird_codebase_community_159 | bird | Identify the display name and location of the user, … | ❌ | 0.00 | 0.00 |
| bird_codebase_community_160 | bird | Identify the latest badge awarded to the user with t… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_161 | bird | Identify the number of adult users who have cast ove… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_162 | bird | How long did it take the user, known by his or her d… | ❌ | 0.14 | 0.00 |
| bird_codebase_community_163 | bird | Identify the number of posts and comments left by th… | ✅ | 1.00 | 0.80 |
| bird_codebase_community_164 | bird | Provide the text of the latest 10 comments to the po… | ❌ | 0.50 | 0.50 |
| bird_codebase_community_165 | bird | How many users were awarded with 'Citizen Patrol' ba… | ❌ | 0.20 | 0.00 |
| bird_codebase_community_166 | bird | Count the number of posts with a tag specified as 'c… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_167 | bird | What is the reputation and view count of the user, w… | ❌ | 0.00 | 0.00 |
| bird_codebase_community_168 | bird | How many comments and answers were left by the users… | ❌ | 0.10 | 0.00 |
| bird_codebase_community_169 | bird | When did the user known as 'IrishStat' create his or… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_170 | bird | Identify the number of posts that offer a bounty amo… | ❌ | 0.14 | 0.00 |
| bird_codebase_community_171 | bird | Among all the posts posted by the most influential u… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_172 | bird | How many posts have a score less than 20? | ✅ | 1.00 | 1.00 |
| bird_codebase_community_173 | bird | Among the tags with tag ID below 15, how many of the… | ❌ | 0.50 | 0.00 |
| bird_codebase_community_174 | bird | What is the excerpt post ID and wiki post ID of the … | ❌ | 0.00 | 0.00 |
| bird_codebase_community_175 | bird | Give the user's reputation and up vote number of the… | ❌ | 0.12 | 0.00 |
| bird_codebase_community_176 | bird | Give the texts commented on the post about linear re… | ❌ | 0.14 | 0.00 |
| bird_codebase_community_177 | bird | Among the posts with views ranging from 100 to 150, … | ✅ | 1.00 | 0.67 |
| bird_codebase_community_178 | bird | List the creation date and age of the user that comm… | ❌ | 0.11 | 0.00 |
| bird_codebase_community_179 | bird | In comments with 0 score, how many of the posts have… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_180 | bird | In posts with 1 comment, how many of the comments ha… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_181 | bird | Among products comments with 0 score, what is the to… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_182 | bird | What is the post ID and the comments commented in th… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_183 | bird | What is the up vote number of the user that commente… | ❌ | 0.14 | 0.00 |
| bird_codebase_community_184 | bird | List the comments commented by the user with a usern… | ✅ | 1.00 | 0.67 |
| bird_codebase_community_185 | bird | In comments with score between 1 to 5, list down the… | ✅ | 1.00 | 1.00 |
| bird_codebase_community_186 | bird | Among the comments with scores between 5 to 10, what… | ✅ | 1.00 | 1.00 |
