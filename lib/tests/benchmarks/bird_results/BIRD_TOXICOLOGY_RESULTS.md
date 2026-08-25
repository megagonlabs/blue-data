# BIRD — toxicology — Results

**Conditions:** `keyword`  
**Queries:** 145  
**Last run:** 2026-08-25 09:56 UTC

> Two evaluation levels: **attribute-level** Hit@K (which column/table?) and **entity-level** P/R/F1 (which set of tables?). Entity-level is comparable to MEW, CORE-T, DMRAL.

---

## Attribute-level retrieval (Hit@K / MRR)

> Does the relevant column or table appear in the top-K results?

| Metric | keyword |
|--------|---------|
| Hit@1 | 34% |
| Hit@3 | 42% |
| Hit@5 | 67% |
| MRR | 48% |

```
Hit@5 (% of 145 queries)

  keyword         ██████████░░░░░   67%
```

---

## Entity-level retrieval (P / R / F1)

> Does the search return the right **set of tables** (entity records)?  
> Ideal-K uses exactly |relevant tables| as the cutoff.

| Metric | keyword |
|--------|---------|
| F1@3 | 0.298 |
| P@3 | 0.379 |
| R@3 | 0.271 |
| F1@5 | 0.426 |
| P@5 | 0.448 |
| R@5 | 0.444 |
| F1@10 | 0.611 |
| P@10 | 0.457 |
| R@10 | 0.998 |
| F1@Ideal-K | 0.259 |
| P@Ideal-K | 0.341 |
| R@Ideal-K | 0.223 |

---

## Results by category

| Category | n | keyword Hit@1 | keyword MRR | keyword F1@Ideal |
|---|---|---|---|---|
| bird | 145 | 34% | 0.48 | 0.26 |

---

## Per-question results

| ID | Cat | Intent | keyword H@1 | keyword MRR | keyword F1@Ideal |
|---|---|--- |---|--- |--- |
| bird_toxicology_001 | bird | What is the most common bond type? | ✅ | 1.00 | 1.00 |
| bird_toxicology_002 | bird | In the non-carcinogenic molecules, how many contain … | ❌ | 0.20 | 0.00 |
| bird_toxicology_003 | bird | Calculate the average number of oxygen atoms in sing… | ❌ | 0.20 | 0.00 |
| bird_toxicology_004 | bird | On average how many carcinogenic molecules are singl… | ❌ | 0.20 | 0.00 |
| bird_toxicology_005 | bird | In the molecule containing sodium atoms, how many ar… | ✅ | 1.00 | 0.67 |
| bird_toxicology_006 | bird | Find the triple-bonded molecules which are carcinoge… | ❌ | 0.17 | 0.00 |
| bird_toxicology_007 | bird | What is the percentage of carbon in double-bond mole… | ❌ | 0.20 | 0.00 |
| bird_toxicology_008 | bird | How many triple type bonds are there? | ❌ | 0.14 | 0.00 |
| bird_toxicology_009 | bird | In how many atoms is there no bromine? | ❌ | 0.20 | 0.00 |
| bird_toxicology_010 | bird | Of the first 100 molecules in number order, how many… | ❌ | 0.17 | 0.00 |
| bird_toxicology_011 | bird | Identify by their ID the molecules in which there is… | ❌ | 0.20 | 0.00 |
| bird_toxicology_012 | bird | What elements are in the TR004_8_9 bond atoms? | ❌ | 0.20 | 0.00 |
| bird_toxicology_013 | bird | What elements are in a double type bond? | ❌ | 0.25 | 0.00 |
| bird_toxicology_014 | bird | Which type of label is the most numerous in atoms wi… | ❌ | 0.17 | 0.00 |
| bird_toxicology_015 | bird | Chlorine is in what type of bond? | ❌ | 0.25 | 0.00 |
| bird_toxicology_016 | bird | What atoms are connected in single type bonds? | ✅ | 1.00 | 0.67 |
| bird_toxicology_017 | bird | Indicate which atoms are connected in non-carcinogen… | ✅ | 1.00 | 0.50 |
| bird_toxicology_018 | bird | Which element is the least numerous in non-carcinoge… | ❌ | 0.17 | 0.00 |
| bird_toxicology_019 | bird | What type of bond is there between the atoms TR004_8… | ✅ | 1.00 | 0.67 |
| bird_toxicology_020 | bird | What type of label is not on molecules with atoms wi… | ❌ | 0.17 | 0.00 |
| bird_toxicology_021 | bird | How many atoms with iodine and with sulfur type elem… | ✅ | 1.00 | 0.50 |
| bird_toxicology_022 | bird | Identify all connected atoms with a triple bond. | ✅ | 1.00 | 0.67 |
| bird_toxicology_023 | bird | Identify all the atoms that are connected to the ato… | ✅ | 1.00 | 0.67 |
| bird_toxicology_024 | bird | What percentage of carcinogenic-type molecules does … | ❌ | 0.20 | 0.00 |
| bird_toxicology_025 | bird | What is the percentage of carcinogenic molecules in … | ❌ | 0.20 | 0.00 |
| bird_toxicology_026 | bird | Please list top three elements of the toxicology of … | ❌ | 0.17 | 0.00 |
| bird_toxicology_027 | bird | What are the atoms that are bonded in the molecule T… | ❌ | 0.50 | 0.00 |
| bird_toxicology_028 | bird | What is the difference between the number of molecul… | ❌ | 0.17 | 0.00 |
| bird_toxicology_029 | bird | What are the atom IDs of the bond TR000_2_5? | ❌ | 0.17 | 0.00 |
| bird_toxicology_030 | bird | What are the bond IDs that have the same atom ID 2 o… | ❌ | 0.17 | 0.00 |
| bird_toxicology_031 | bird | Please list top five molecules that have double bond… | ❌ | 0.14 | 0.00 |
| bird_toxicology_032 | bird | What is the percentage of double bonds in the molecu… | ❌ | 0.14 | 0.00 |
| bird_toxicology_033 | bird | What is the percentage of molecules that are carcino… | ❌ | 0.17 | 0.00 |
| bird_toxicology_034 | bird | How much of the hydrogen in molecule TR206 is accoun… | ❌ | 0.17 | 0.00 |
| bird_toxicology_035 | bird | What is the type of bond that molecule TR000 has whe… | ❌ | 0.50 | 0.00 |
| bird_toxicology_036 | bird | What are the elements of the toxicology and label of… | ❌ | 0.33 | 0.00 |
| bird_toxicology_037 | bird | Which bond type accounted for the majority of the bo… | ❌ | 0.50 | 0.00 |
| bird_toxicology_038 | bird | Please list top three molecules that have single bon… | ❌ | 0.17 | 0.00 |
| bird_toxicology_039 | bird | Please list top two bonds that happened with the mol… | ❌ | 0.20 | 0.00 |
| bird_toxicology_040 | bird | How many bonds which involved atom 12 does molecule … | ❌ | 0.17 | 0.00 |
| bird_toxicology_041 | bird | How many molecules are carcinogenic and have the bro… | ❌ | 0.20 | 0.00 |
| bird_toxicology_042 | bird | What are the bond type and the atoms of the bond ID … | ✅ | 1.00 | 0.67 |
| bird_toxicology_043 | bird | Which molecule does the atom TR001_10 belong to? Ple… | ✅ | 1.00 | 1.00 |
| bird_toxicology_044 | bird | How many molecules have a triple bond type? | ✅ | 1.00 | 1.00 |
| bird_toxicology_045 | bird | How many connections does the atom 19 have? | ❌ | 0.20 | 0.00 |
| bird_toxicology_046 | bird | List all the elements of the toxicology of the molec… | ❌ | 0.17 | 0.00 |
| bird_toxicology_047 | bird | How many of the molecules are not carcinogenic? | ❌ | 0.17 | 0.00 |
| bird_toxicology_048 | bird | Among all the atoms from 21 to 25, list all the mole… | ❌ | 0.20 | 0.00 |
| bird_toxicology_049 | bird | What are the bonds that have phosphorus and nitrogen… | ✅ | 1.00 | 0.67 |
| bird_toxicology_050 | bird | Is the molecule with the most double bonds carcinoge… | ✅ | 1.00 | 0.67 |
| bird_toxicology_051 | bird | What is the average number of bonds the atoms with t… | ❌ | 0.20 | 0.00 |
| bird_toxicology_052 | bird | List the bond type and the bond ID of the atom 45. | ❌ | 0.50 | 0.50 |
| bird_toxicology_053 | bird | List all the elements of atoms that can not bond wit… | ❌ | 0.20 | 0.00 |
| bird_toxicology_054 | bird | What are the atoms of the triple bond with the molec… | ❌ | 0.50 | 0.40 |
| bird_toxicology_055 | bird | What are the elements of the atoms of TR144_8_19? | ❌ | 0.25 | 0.00 |
| bird_toxicology_056 | bird | Of all the carcinogenic molecules, which one has the… | ❌ | 0.17 | 0.00 |
| bird_toxicology_057 | bird | What is the least common element of all carcinogenic… | ❌ | 0.17 | 0.00 |
| bird_toxicology_058 | bird | What are the atoms that can bond with the atom that … | ✅ | 1.00 | 0.50 |
| bird_toxicology_059 | bird | List the elements of all the triple bonds. | ❌ | 0.25 | 0.00 |
| bird_toxicology_060 | bird | What percentage of bonds have the most common combin… | ❌ | 0.25 | 0.00 |
| bird_toxicology_061 | bird | What proportion of single bonds are carcinogenic? Pl… | ❌ | 0.17 | 0.00 |
| bird_toxicology_062 | bird | Calculate the total atoms consisting of the element … | ❌ | 0.17 | 0.00 |
| bird_toxicology_063 | bird | List down atom id2 for atoms with element sulfur. | ✅ | 1.00 | 0.67 |
| bird_toxicology_064 | bird | What are the bond type for atoms with element Tin? | ✅ | 1.00 | 0.50 |
| bird_toxicology_065 | bird | How many elements are there for single bond molecule… | ✅ | 1.00 | 0.50 |
| bird_toxicology_066 | bird | Calculate the total atoms with triple-bond molecules… | ❌ | 0.17 | 0.00 |
| bird_toxicology_067 | bird | Write down bond id for molecules that are carcinogen… | ✅ | 1.00 | 0.67 |
| bird_toxicology_068 | bird | Among the single bond molecule id, which molecules a… | ✅ | 1.00 | 1.00 |
| bird_toxicology_069 | bird | What is the composition of element chlorine in perce… | ✅ | 1.00 | 0.50 |
| bird_toxicology_070 | bird | What are the labels for TR000, TR001 and TR002? | ❌ | 0.17 | 0.00 |
| bird_toxicology_071 | bird | List down the molecule id for non carcinogenic molec… | ✅ | 1.00 | 1.00 |
| bird_toxicology_072 | bird | Calculate the total carcinogenic molecules for molec… | ✅ | 1.00 | 1.00 |
| bird_toxicology_073 | bird | List down the bond type for molecules from molecule … | ✅ | 1.00 | 1.00 |
| bird_toxicology_074 | bird | What are the elements for bond id TR001_10_11? | ❌ | 0.20 | 0.00 |
| bird_toxicology_075 | bird | How many bond id have element iodine? | ✅ | 1.00 | 0.50 |
| bird_toxicology_076 | bird | Among the molecules with element Calcium, are they m… | ❌ | 0.17 | 0.00 |
| bird_toxicology_077 | bird | Does bond id TR001_1_8 have both element of chlorine… | ❌ | 0.17 | 0.00 |
| bird_toxicology_078 | bird | List down two molecule id of triple bond non carcino… | ✅ | 1.00 | 0.80 |
| bird_toxicology_079 | bird | What is the percentage of element chlorine in carcin… | ❌ | 0.17 | 0.00 |
| bird_toxicology_080 | bird | List the toxicology elements associated with molecul… | ❌ | 0.17 | 0.00 |
| bird_toxicology_081 | bird | Give me the molecule ID of the double bond type. | ❌ | 0.50 | 0.00 |
| bird_toxicology_082 | bird | Write down the atom IDs of the first and second atom… | ❌ | 0.50 | 0.50 |
| bird_toxicology_083 | bird | What are the toxicology elements associated with bon… | ❌ | 0.20 | 0.00 |
| bird_toxicology_084 | bird | How many of the single bond type molecules are non-c… | ✅ | 1.00 | 0.67 |
| bird_toxicology_085 | bird | What is the label for bond ID TR001_10_11? | ✅ | 1.00 | 0.67 |
| bird_toxicology_086 | bird | Enumerate the bond ID of triple bond type molecules … | ✅ | 1.00 | 0.67 |
| bird_toxicology_087 | bird | Tally the toxicology element of the 4th atom of each… | ❌ | 0.33 | 0.00 |
| bird_toxicology_088 | bird | What is the ratio of Hydrogen elements in molecule I… | ✅ | 1.00 | 0.50 |
| bird_toxicology_089 | bird | Identify whether the chemical compound that contains… | ❌ | 0.20 | 0.00 |
| bird_toxicology_090 | bird | Determine the bond type that is formed in the chemic… | ✅ | 1.00 | 0.67 |
| bird_toxicology_091 | bird | Name chemical elements that form a bond TR001_10_11. | ✅ | 1.00 | 0.50 |
| bird_toxicology_092 | bird | Among all chemical compounds identified in the datab… | ❌ | 0.14 | 0.00 |
| bird_toxicology_093 | bird | Among all chemical compounds that contain molecule T… | ❌ | 0.14 | 0.00 |
| bird_toxicology_094 | bird | Identify whether the molecule that contains atom TR0… | ✅ | 1.00 | 1.00 |
| bird_toxicology_095 | bird | Is molecule TR151 carcinogenic? | ✅ | 1.00 | 1.00 |
| bird_toxicology_096 | bird | Which toxic element can be found in the molecule TR1… | ❌ | 0.14 | 0.00 |
| bird_toxicology_097 | bird | How many chemical compounds in the database are iden… | ❌ | 0.17 | 0.00 |
| bird_toxicology_098 | bird | Identify the atoms belong to the molecule with ID be… | ❌ | 0.14 | 0.00 |
| bird_toxicology_099 | bird | How many atoms belong to the molecule labeled with c… | ✅ | 1.00 | 0.67 |
| bird_toxicology_100 | bird | Which bond ids are double-bond with carcinogenic com… | ✅ | 1.00 | 0.67 |
| bird_toxicology_101 | bird | How many atoms belong to the molecule that element i… | ✅ | 1.00 | 0.67 |
| bird_toxicology_102 | bird | Indicate the molecule id is belonging to the TR000_1… | ❌ | 0.33 | 0.00 |
| bird_toxicology_103 | bird | Among the atoms that contain element carbon, which o… | ❌ | 0.17 | 0.00 |
| bird_toxicology_104 | bird | Calculate the percentage of molecules containing car… | ❌ | 0.17 | 0.00 |
| bird_toxicology_105 | bird | Is molecule TR124 carcinogenic? | ✅ | 1.00 | 1.00 |
| bird_toxicology_106 | bird | What atoms comprise TR186? | ❌ | 0.20 | 0.00 |
| bird_toxicology_107 | bird | What is the bond type of TR007_4_19? | ✅ | 1.00 | 1.00 |
| bird_toxicology_108 | bird | Name the elements that comprise the atoms of bond TR… | ❌ | 0.20 | 0.00 |
| bird_toxicology_109 | bird | How many double bonds does TR006 have and is it carc… | ❌ | 0.17 | 0.00 |
| bird_toxicology_110 | bird | List all carcinogenic molecules and their elements. | ❌ | 0.20 | 0.00 |
| bird_toxicology_111 | bird | Name all bonds with single bond types and what atoms… | ✅ | 1.00 | 1.00 |
| bird_toxicology_112 | bird | Which molecules have triple bonds and list all the e… | ❌ | 0.20 | 0.00 |
| bird_toxicology_113 | bird | Name the atoms' elements that form bond TR000_2_3. | ❌ | 0.20 | 0.00 |
| bird_toxicology_114 | bird | How many bonds are created by bonding atoms with chl… | ❌ | 0.25 | 0.00 |
| bird_toxicology_115 | bird | List out the atom id that belongs to the TR346 molec… | ✅ | 1.00 | 0.50 |
| bird_toxicology_116 | bird | How many molecules have a double bond type and among… | ✅ | 1.00 | 0.67 |
| bird_toxicology_117 | bird | How many molecules without sulphur element is not ha… | ❌ | 0.17 | 0.00 |
| bird_toxicology_118 | bird | What is the carcinogenic label for bond TR001_2_4? | ✅ | 1.00 | 0.50 |
| bird_toxicology_119 | bird | How many atoms belong to molecule id TR001? | ❌ | 0.17 | 0.00 |
| bird_toxicology_120 | bird | How many single bonds are there in the list? | ❌ | 0.14 | 0.00 |
| bird_toxicology_121 | bird | Among the molecules which contain "cl" element, whic… | ❌ | 0.20 | 0.00 |
| bird_toxicology_122 | bird | Among the molecules which contain "c" element, which… | ❌ | 0.20 | 0.00 |
| bird_toxicology_123 | bird | Calculate the percentage of carcinogenic molecules w… | ❌ | 0.20 | 0.00 |
| bird_toxicology_124 | bird | What is the molecule id of bond id TR001_1_7? | ❌ | 0.17 | 0.00 |
| bird_toxicology_125 | bird | How many elements are contained in bond_id TR001_3_4… | ❌ | 0.17 | 0.00 |
| bird_toxicology_126 | bird | What is the type of the bond which is presenting the… | ✅ | 1.00 | 0.67 |
| bird_toxicology_127 | bird | What is the molecule of atom id "TR000_2" and atom i… | ❌ | 0.17 | 0.00 |
| bird_toxicology_128 | bird | What is the element of toxicology for the atom with … | ❌ | 0.33 | 0.00 |
| bird_toxicology_129 | bird | Is molecule TR000 is carcinogenic or not? | ✅ | 1.00 | 1.00 |
| bird_toxicology_130 | bird | Find the percentage of atoms with single bond. | ❌ | 0.14 | 0.00 |
| bird_toxicology_131 | bird | How many carcinogenic molecules that consisted of Ni… | ❌ | 0.20 | 0.00 |
| bird_toxicology_132 | bird | Which molecule consisted of Sulphur atom with double… | ✅ | 1.00 | 0.50 |
| bird_toxicology_133 | bird | Which non-carcinogenic molecules consisted more than… | ❌ | 0.20 | 0.00 |
| bird_toxicology_134 | bird | List all the elements with double bond, consisted in… | ❌ | 0.17 | 0.00 |
| bird_toxicology_135 | bird | Which carcinogenic molecule have the highest number … | ✅ | 1.00 | 0.67 |
| bird_toxicology_136 | bird | Calculate the percentage of carcinogenic molecules w… | ❌ | 0.20 | 0.00 |
| bird_toxicology_137 | bird | How many of the molecules are carcinogenic? | ❌ | 0.17 | 0.00 |
| bird_toxicology_138 | bird | Among the molecules between TR004 to TR010, how many… | ❌ | 0.14 | 0.00 |
| bird_toxicology_139 | bird | In the molecule TR008, how many carbons are present? | ❌ | 0.17 | 0.00 |
| bird_toxicology_140 | bird | What is the element with the atom ID of TR004_7 in m… | ✅ | 1.00 | 1.00 |
| bird_toxicology_141 | bird | What is the total number of molecules with double bo… | ❌ | 0.20 | 0.00 |
| bird_toxicology_142 | bird | in molecules with triple bonds, how many of them are… | ❌ | 0.17 | 0.00 |
| bird_toxicology_143 | bird | List the element and bond type included in the molec… | ❌ | 0.50 | 0.50 |
| bird_toxicology_144 | bird | What is the atom ID of double bonded carbon in TR012… | ✅ | 1.00 | 0.50 |
| bird_toxicology_145 | bird | List the atom ID of the carcinogenic molecule that c… | ✅ | 1.00 | 1.00 |
