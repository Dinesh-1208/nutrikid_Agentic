# KidsNutriBite - Context Recall Failure Analysis & Confusion Matrices

## Why Context Recall is Low (0.3849)
1. **Semantic Vector Dilution (Bi-encoder bias):** The embedding model `BAAI/bge-small-en-v1.5` embeds the overall semantic profile of the text. When a parent query mentions multiple concepts (e.g. child age, eating habits, and a symptom), the embedding vector is 'diluted'. It matches general dietary advice chunks rather than the exact clinical rule chunk.
2. **Short, Context-Poor Chunks:** Chunks in `rag_data.json` are often single sentences. Single-sentence embeddings have less semantic density, making them hard to retrieve unless the query uses identical wording.
3. **Lack of Exact Keyword Matching:** Vector search (FAISS) does not guarantee keyword overlaps. A query containing 'fever' can retrieve general infant chunks if they share words like 'diet', 'foods', or 'infant', completely missing the exact fever guidelines.
4. **Synonym/Vocabulary Mismatch:** The query may use colloquial terms ('rash', 'throw up') while the RAG guidelines use formal clinical terminology ('atopic dermatitis', 'emesis', 'diarrhea').

## Context Recall Failure Case Study (20 Failed Examples)

### Case 1: Q_COND_01
- **Question:** What should a child eat during a fever?
- **Expected Chunks:**
  * "During fever children should consume soft and easily digestible foods."
  * "avoid oily or spicy meals"
- **Retrieved Chunks:**
  * "Infants aged 6 to 8 months should be given complementary foods at least twice a day along with breastfeeding."
  * "Infants aged 9 to 12 months should receive complementary foods at least three times a day."
  * "Proper hygiene during food preparation is essential to prevent infections in infants."
- **Missing Chunks:**
  * "During fever children should consume soft and easily digestible foods."
  * "avoid oily or spicy meals"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. Fever keyword was diluted; retriever preferred general infant feeding guidelines.

---

### Case 2: Q_COND_02
- **Question:** What is the feeding protocol for an infant with diarrhea?
- **Expected Chunks:**
  * "infant_diarrhea"
  * "hygienic_food"
  * "easy_digest"
  * "continue_feeding"
- **Retrieved Chunks:**
  * "Prelacteal feeds can lead to diarrhea and helminthic infestation in newborns."
  * "Breastfeeding reduces risk of respiratory and diarrheal infections in infants."
  * "Lactose intolerance during diarrhea is usually temporary and can be managed by reducing milk intake."
- **Missing Chunks:**
  * "infant_diarrhea"
  * "hygienic_food"
  * "easy_digest"
  * "continue_feeding"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 3: Q_COND_03
- **Question:** What foods are recommended for a child diagnosed with anemia?
- **Expected Chunks:**
  * "iron_rich"
  * "folate_rich"
  * "vitamin_c"
  * "tea_with_meals"
- **Retrieved Chunks:**
  * "Vitamin C rich foods improve iron absorption and should be included in the diet."
  * "Vitamin C improves iron absorption from plant-based foods."
  * "Children need nutrient-rich foods for growth, brain development, and cognition."
- **Missing Chunks:**
  * "iron_rich"
  * "folate_rich"
  * "vitamin_c"
  * "tea_with_meals"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. Anemia-specific iron requirements were missed in favor of general pregnancy rules.

---

### Case 4: Q_COND_04
- **Question:** What should a child with lactose intolerance avoid?
- **Expected Chunks:**
  * "avoid_tags"
  * "milk"
  * "high_lactose"
  * "curd_based"
  * "low_lactose"
- **Retrieved Chunks:**
  * "Lactose intolerance during diarrhea is usually temporary and can be managed by reducing milk intake."
  * "Curd can be used as an alternative to milk in lactose intolerance."
  * "Congenital lactose intolerance and galactosaemia are rare but permanent contraindications to breastfeeding."
- **Missing Chunks:**
  * "avoid_tags"
  * "milk"
  * "high_lactose"
  * "curd_based"
  * "low_lactose"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 5: Q_COND_05
- **Question:** Is expressed breast milk recommended for a preterm infant?
- **Expected Chunks:**
  * "preterm_infant"
  * "energy_kcal_kg_day"
  * "fluid_ml_kg_day"
  * "gavage"
  * "breast"
- **Retrieved Chunks:**
  * "Babies with congestive heart failure benefit from expressed breast milk due to its low sodium content."
  * "Preterm milk is nutrient-denser than term milk, containing higher protein, sodium, and IgA to support the baby's needs."
  * "Breast milk contains antibodies that protect infants from infections."
- **Missing Chunks:**
  * "preterm_infant"
  * "energy_kcal_kg_day"
  * "fluid_ml_kg_day"
  * "gavage"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 6: Q_COND_06
- **Question:** What feeding tools are recommended for a baby with a cleft palate?
- **Expected Chunks:**
  * "expressed_breast_milk"
  * "palada"
  * "long_spoon"
  * "long_dropper"
  * "feeding_plate"
- **Retrieved Chunks:**
  * "Homemade foods are preferred for infant feeding."
  * "Placing babies in the right lateral position after feeding can help prevent aspiration."
  * "Developmental Assessment Tools: (1) DDST (Denver): Screening up to 6 yrs. (2) Gesell Schedule: Diagnosis of abnormalities. (3) BSID (Bayley): Motor/Mental/Behaviour scales. (4) TDSC (Trivandrum): Simple 17-item tool for Indian children up to 24 months. (5) NBAS (Brazelton): 20 primitive reflexes."
- **Missing Chunks:**
  * "expressed_breast_milk"
  * "palada"
  * "long_spoon"
  * "long_dropper"
  * "feeding_plate"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. Specific maternal conditions matched general maternal UTI/fever guidelines instead.

---

### Case 7: Q_COND_07
- **Question:** Can a mother with active tuberculosis continue breastfeeding?
- **Expected Chunks:**
  * "tuberculosis_maternal"
  * "chemotherapy"
  * "chemoprophylaxis"
  * "INH"
  * "rifampicin"
  * "continue"
- **Retrieved Chunks:**
  * "Breastfeeding can continue during most maternal illnesses like viral fever, mastitis, and UTI."
  * "Mastitis requires effective milk removal, and mothers should continue breastfeeding frequently from the affected breast."
  * "Breastfeeding should continue even if the mother has mild illnesses unless medically advised."
- **Missing Chunks:**
  * "tuberculosis_maternal"
  * "chemotherapy"
  * "chemoprophylaxis"
  * "INH"
  * "rifampicin"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. Specific maternal conditions matched general maternal UTI/fever guidelines instead.

---

### Case 8: Q_COND_08
- **Question:** What is the breastfeeding protocol for a mother with Hepatitis B?
- **Expected Chunks:**
  * "hepatitis_b_maternal"
  * "immunoglobulin_for_baby"
  * "vaccination_for_baby"
  * "continue"
- **Retrieved Chunks:**
  * "Breastfeeding can continue during most maternal illnesses like viral fever, mastitis, and UTI."
  * "Breastfeeding reduces risk of respiratory and diarrheal infections in infants."
  * "Breastfeeding reduces infections and improves immunity in infants."
- **Missing Chunks:**
  * "hepatitis_b_maternal"
  * "immunoglobulin_for_baby"
  * "vaccination_for_baby"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 9: Q_COND_09
- **Question:** What is the breastfeeding rule for a child with congenital lactose intolerance?
- **Expected Chunks:**
  * "congenital_lactose_intolerance"
  * "animal_milk"
  * "permanent_contraindication"
- **Retrieved Chunks:**
  * "Congenital lactose intolerance and galactosaemia are rare but permanent contraindications to breastfeeding."
  * "Lactose intolerance during diarrhea is usually temporary and can be managed by reducing milk intake."
  * "Water or other foods should not be given during the first six months of breastfeeding."
- **Missing Chunks:**
  * "congenital_lactose_intolerance"
  * "animal_milk"
  * "permanent_contraindication"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 10: Q_COND_10
- **Question:** What is the feeding protocol for a child with galactosaemia?
- **Expected Chunks:**
  * "galactosaemia"
  * "animal_milk"
  * "permanent_contraindication"
- **Retrieved Chunks:**
  * "Congenital lactose intolerance and galactosaemia are rare but permanent contraindications to breastfeeding."
  * "Galactosaemia Soya Selection: Soya isolate formulas (Nusobee, Zerolac) are safe. Whole soya flour must be avoided because it contains complex starches like stachyose and raffinose that release galactose."
  * "Prelacteal feeds can lead to diarrhea and helminthic infestation in newborns."
- **Missing Chunks:**
  * "animal_milk"
  * "permanent_contraindication"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 11: Q_COND_11
- **Question:** Why is breast milk preferred for an infant with congestive heart failure?
- **Expected Chunks:**
  * "congestive_heart_failure_infant"
  * "expressed_breast_milk"
  * "low_sodium_content"
- **Retrieved Chunks:**
  * "Babies with congestive heart failure benefit from expressed breast milk due to its low sodium content."
  * "Breastfeeding supports infant growth and reduces health risks."
  * "Breast milk contains antibodies that protect infants from infections."
- **Missing Chunks:**
  * "congestive_heart_failure_infant"
  * "expressed_breast_milk"
  * "low_sodium_content"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 12: Q_COND_12
- **Question:** What should a child with malnutrition eat?
- **Expected Chunks:**
  * "malnutrition"
  * "balanced_diet"
  * "nutrient_dense"
  * "junk_food"
  * "high_sugar"
- **Retrieved Chunks:**
  * "Feeding should continue during illness to prevent malnutrition."
  * "Infants should be fed semi-solid foods in small quantities starting with 2-3 teaspoons."
  * "Children need nutrient-rich foods for growth, brain development, and cognition."
- **Missing Chunks:**
  * "balanced_diet"
  * "nutrient_dense"
  * "junk_food"
  * "high_sugar"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 13: Q_COND_13
- **Question:** How should a child with overweight and obesity manage their meals?
- **Expected Chunks:**
  * "overweight_obesity"
  * "low_fat"
  * "low_sugar"
  * "high_fiber"
  * "controlled_portion"
- **Retrieved Chunks:**
  * "A healthy child's tiffin should be balanced, low in sugar, and include fruits. Involving children in menu planning encourages them to finish their meal."
  * "After an illness, give the child an extra meal daily for 1-2 weeks to regain lost weight."
  * "Balanced diets for children above one year provide around 1110 kcal and 36.7 grams protein daily."
- **Missing Chunks:**
  * "overweight_obesity"
  * "low_fat"
  * "low_sugar"
  * "high_fiber"
  * "controlled_portion"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 14: Q_COND_14
- **Question:** What diet is suitable for poor growth in a child?
- **Expected Chunks:**
  * "poor_growth"
  * "high_protein"
  * "balanced_macros"
  * "low_energy"
  * "frequent"
- **Retrieved Chunks:**
  * "Balanced diets for children above one year provide around 1110 kcal and 36.7 grams protein daily."
  * "Poor nutrition during pregnancy can negatively affect fetal growth and development."
  * "Low food intake during critical life stages like childhood can negatively impact growth and development."
- **Missing Chunks:**
  * "poor_growth"
  * "high_protein"
  * "balanced_macros"
  * "low_energy"
  * "frequent"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 15: Q_COND_15
- **Question:** What is the recommended meal pattern for an infant aged 6 to 8 months?
- **Expected Chunks:**
  * "infant_6_8_months"
  * "semi_solid"
  * "easy_digest"
  * "nutrient_dense"
  * "added_sugar"
  * "added_salt"
- **Retrieved Chunks:**
  * "Infants aged 6 to 8 months should be given complementary foods at least twice a day along with breastfeeding."
  * "Infants aged 9 to 12 months should receive complementary foods at least three times a day."
  * "Homemade foods are preferred for infant feeding."
- **Missing Chunks:**
  * "infant_6_8_months"
  * "semi_solid"
  * "easy_digest"
  * "nutrient_dense"
  * "added_sugar"
  * "added_salt"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 16: Q_COND_16
- **Question:** What is the meal pattern for an infant aged 9 to 12 months?
- **Expected Chunks:**
  * "infant_9_12_months"
  * "semi_solid"
  * "variety_food"
  * "junk_food"
  * "3_meals_plus_breastfeeding"
- **Retrieved Chunks:**
  * "Infants aged 9 to 12 months should receive complementary foods at least three times a day."
  * "Infants aged 6 to 8 months should be given complementary foods at least twice a day along with breastfeeding."
  * "Infants require 650 to 720 kcal per day between 6 to 12 months of age."
- **Missing Chunks:**
  * "infant_9_12_months"
  * "semi_solid"
  * "variety_food"
  * "junk_food"
  * "3_meals_plus_breastfeeding"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 17: Q_COND_17
- **Question:** What is the feeding schedule for a child above 1 year old?
- **Expected Chunks:**
  * "child_above_1_year"
  * "balanced_diet"
  * "solid_food"
  * "added_sugar"
  * "3_meals_2_snacks"
- **Retrieved Chunks:**
  * "Balanced diets for children above one year provide around 1110 kcal and 36.7 grams protein daily."
  * "Breastfeeding should start within one hour of birth."
  * "Breastfeeding should begin within one hour after birth."
- **Missing Chunks:**
  * "child_above_1_year"
  * "balanced_diet"
  * "solid_food"
  * "added_sugar"
  * "3_meals_2_snacks"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 18: Q_COND_18
- **Question:** What is the probiotic protocol recommended during pregnancy to reduce infant eczema?
- **Expected Chunks:**
  * "pregnancy"
  * "probiotic_protocol"
  * "LGG supplementation"
  * "atopic eczema"
- **Retrieved Chunks:**
  * "A healthy diet during pregnancy improves birth weight and reduces risk of infections in newborns."
  * "Probiotics in formula, like Bifidobacteria lactis, can enhance the immune system and reduce the incidence of diarrhea."
  * "Breastfeeding reduces infections and improves immunity in infants."
- **Missing Chunks:**
  * "probiotic_protocol"
  * "LGG supplementation"
  * "atopic eczema"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 19: Q_COND_19
- **Question:** How much extra energy and protein is needed during pregnancy?
- **Expected Chunks:**
  * "pregnancy"
  * "dietary_rules"
  * "extra_kcal"
  * "300"
  * "extra_protein_g"
  * "15"
- **Retrieved Chunks:**
  * "During pregnancy, mothers should consume an extra 300 kcal and 15g of protein daily."
  * "Energy requirements for Pregnancy and Lactation: Pregnant +350 kcal/d; Lactating (0-6m) +600 kcal/d; Lactating (7-12m) +520 kcal/d."
  * "During lactation, mothers should consume an extra 400-500 kcal and 25g of protein daily."
- **Missing Chunks:**
  * "dietary_rules"
  * "extra_kcal"
  * "300"
  * "extra_protein_g"
  * "15"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---

### Case 20: Q_COND_20
- **Question:** How much extra energy and protein is needed during lactation?
- **Expected Chunks:**
  * "lactation"
  * "dietary_rules"
  * "extra_kcal"
  * "500"
  * "extra_protein_g"
  * "25"
- **Retrieved Chunks:**
  * "During lactation, mothers should consume an extra 400-500 kcal and 25g of protein daily."
  * "Breast milk provides around 500 kcal and 5 grams of protein per day after six months."
  * "Energy requirements for Pregnancy and Lactation: Pregnant +350 kcal/d; Lactating (0-6m) +600 kcal/d; Lactating (7-12m) +520 kcal/d."
- **Missing Chunks:**
  * "dietary_rules"
  * "extra_kcal"
  * "500"
  * "extra_protein_g"
  * "25"
- **Root Cause:** Semantic mismatch in bi-encoder embedding space. General keyword dilution: short chunks lacking contextual overlap.

---


## Suggested Technical Improvements
To scale the KidsNutriBite RAG engine and boost Context Recall, we propose the following production changes:
1. **Hybrid Retrieval (FAISS + BM25):** Combine dense semantic vectors (FAISS) with sparse keyword matching (BM25). Rerank the unified candidates using a cross-encoder model (e.g. `BAAI/bge-reranker-large`). This directly addresses keyword dilution.
2. **Query Expansion / Reformulation:** Use LLM to expand user queries into formal clinical terms (e.g. translating 'diarrhea' into 'loose stools, gastroenteritis, hydration') before retrieval.
3. **Parent-Child Chunking:** Store large parent document contexts, but index smaller child chunks. When a child chunk is retrieved, feed the entire parent context to the LLM to avoid context truncation.
4. **Self-Querying Retriever:** Convert natural language questions into structured filters (e.g. `condition = fever` and `age = 7`) and apply database metadata filtering before vector search.

## Confusion Matrices

### 1. Allergy-Related Queries
Measures the system's ability to block allergens when present in the user profile.
| Model   |   True Positive (TP) |   True Negative (TN) |   False Positive (FP) |   False Negative (FN) |   Precision |   Recall |   F1-Score |
|:--------|---------------------:|---------------------:|----------------------:|----------------------:|------------:|---------:|-----------:|
| GEMINI  |                   35 |                   64 |                     1 |                     0 |      0.9722 |   1      |     0.9859 |
| QWEN    |                   35 |                   64 |                     1 |                     0 |      0.9722 |   1      |     0.9859 |
| LLAMA   |                   31 |                   65 |                     0 |                     4 |      1      |   0.8857 |     0.9394 |

### 2. Safety-Critical Queries (Medical Refusals)
Measures the system's compliance in refusing to diagnose diseases or prescribe drug dosages.
| Model   |   True Positive (TP) |   True Negative (TN) |   False Positive (FP) |   False Negative (FN) |   Precision |   Recall |   F1-Score |
|:--------|---------------------:|---------------------:|----------------------:|----------------------:|------------:|---------:|-----------:|
| GEMINI  |                    0 |                   98 |                     1 |                     1 |      0      |        0 |     1      |
| QWEN    |                    1 |                   58 |                    41 |                     0 |      0.0238 |        1 |     0.0465 |
| LLAMA   |                    1 |                   58 |                    41 |                     0 |      0.0238 |        1 |     0.0465 |