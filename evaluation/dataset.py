# Evaluation Dataset for KidsNutriBite Hybrid AI System
# Contains 100 questions split into:
# - Conditions: 30
# - Goals: 20
# - Allergies: 20
# - Food Suitability: 20
# - General Nutrition: 10

EVALUATION_DATA = [
    # ================= CONDITIONS (30) =================
    {
        "id": "Q_COND_01",
        "category": "conditions",
        "question": "Can breastfeeding continue if the mother has a viral fever?",
        "profile": {"age": 0.5, "weight": 7.0, "condition": "maternal_illness", "goal": "optimal_breastfeeding", "allergies": []},
        "reference_answer": "Yes, breastfeeding can continue during most maternal illnesses like viral fever, mastitis, and UTI as it is safe and beneficial for the infant.",
        "expected_context": ["Breastfeeding can continue during most maternal illnesses like viral fever, mastitis, and UTI."],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_02",
        "category": "conditions",
        "question": "What is the feeding protocol for an infant with diarrhea?",
        "profile": {"age": 0.8, "weight": 8.5, "condition": "infant_diarrhea", "goal": "digestive_support", "allergies": []},
        "reference_answer": "For an infant with diarrhea, continue breastfeeding on demand, offer safe, hygienic, and easily digestible semi-solid foods, and maintain hydration.",
        "expected_context": ["infant_diarrhea", "hygienic_food", "easy_digest", "continue_feeding"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_03",
        "category": "conditions",
        "question": "What foods are recommended for a child diagnosed with anemia?",
        "profile": {"age": 6, "weight": 20.0, "condition": "anemia", "goal": "iron_boost", "allergies": []},
        "reference_answer": "An anemic child requires iron-rich and folate-rich foods like green leafy vegetables, legumes, and citrus fruits. Iron absorption is improved by consuming Vitamin C-rich foods and avoiding tea with meals.",
        "expected_context": ["iron_rich", "folate_rich", "vitamin_c", "tea_with_meals"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_04",
        "category": "conditions",
        "question": "What should a child with lactose intolerance avoid?",
        "profile": {"age": 4, "weight": 16.0, "condition": "lactose_intolerance", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "A child with lactose intolerance must avoid milk and foods high in lactose, but can consume curd and low-lactose alternatives in moderate frequency.",
        "expected_context": ["avoid_tags", "milk", "high_lactose", "curd_based", "low_lactose"],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_COND_05",
        "category": "conditions",
        "question": "Is expressed breast milk recommended for a preterm infant?",
        "profile": {"age": 0.1, "weight": 2.2, "condition": "preterm_infant", "goal": "catch_up_growth", "allergies": []},
        "reference_answer": "Yes, expressed breast milk is highly recommended for preterm infants. Feeding route depends on gestational age and weight (breast if above 34 weeks or 1.8kg, otherwise gavage).",
        "expected_context": ["preterm_infant", "energy_kcal_kg_day", "fluid_ml_kg_day", "gavage", "breast"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_06",
        "category": "conditions",
        "question": "What feeding tools are recommended for a baby with a cleft palate?",
        "profile": {"age": 0.3, "weight": 5.0, "condition": "cleft_palate", "goal": "optimal_breastfeeding", "allergies": []},
        "reference_answer": "For cleft palate, express breast milk and feed using specialized tools like a palada, long spoon, long dropper, or feeding plate.",
        "expected_context": ["expressed_breast_milk", "palada", "long_spoon", "long_dropper", "feeding_plate"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_07",
        "category": "conditions",
        "question": "Can a mother with active tuberculosis continue breastfeeding?",
        "profile": {"age": 0.2, "weight": 4.5, "condition": "tuberculosis_maternal", "goal": "optimal_breastfeeding", "allergies": []},
        "reference_answer": "Yes, breastfeeding is recommended to continue, provided the mother is on chemotherapy and the baby receives chemoprophylaxis (like INH/rifampicin).",
        "expected_context": ["tuberculosis_maternal", "chemotherapy", "chemoprophylaxis", "INH", "rifampicin", "continue"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_08",
        "category": "conditions",
        "question": "What is the breastfeeding protocol for a mother with Hepatitis B?",
        "profile": {"age": 0.1, "weight": 3.8, "condition": "hepatitis_b_maternal", "goal": "optimal_breastfeeding", "allergies": []},
        "reference_answer": "Breastfeeding can continue safely if the baby receives the Hepatitis B immunoglobulin and vaccination immediately after birth.",
        "expected_context": ["hepatitis_b_maternal", "immunoglobulin_for_baby", "vaccination_for_baby", "continue"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_09",
        "category": "conditions",
        "question": "What is the breastfeeding rule for a child with congenital lactose intolerance?",
        "profile": {"age": 0.1, "weight": 3.2, "condition": "congenital_lactose_intolerance", "goal": "digestive_support", "allergies": []},
        "reference_answer": "Congenital lactose intolerance is a permanent contraindication for breastfeeding and animal milk. The child must avoid animal milk entirely.",
        "expected_context": ["congenital_lactose_intolerance", "animal_milk", "permanent_contraindication"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_10",
        "category": "conditions",
        "question": "What is the feeding protocol for a child with galactosaemia?",
        "profile": {"age": 0.2, "weight": 4.0, "condition": "galactosaemia", "goal": "digestive_support", "allergies": []},
        "reference_answer": "Galactosaemia is a permanent contraindication for breastfeeding and animal milk. Lactose-free formula must be used.",
        "expected_context": ["galactosaemia", "animal_milk", "permanent_contraindication"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_11",
        "category": "conditions",
        "question": "Why is breast milk preferred for an infant with congestive heart failure?",
        "profile": {"age": 0.4, "weight": 5.2, "condition": "congestive_heart_failure_infant", "goal": "optimal_breastfeeding", "allergies": []},
        "reference_answer": "Expressed breast milk is preferred for infants with congestive heart failure due to its low sodium content, which reduces fluid retention risks.",
        "expected_context": ["congestive_heart_failure_infant", "expressed_breast_milk", "low_sodium_content"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_12",
        "category": "conditions",
        "question": "What should a child with malnutrition eat?",
        "profile": {"age": 3, "weight": 11.0, "condition": "malnutrition", "goal": "prevent_malnutrition", "allergies": []},
        "reference_answer": "A child with malnutrition requires a balanced, nutrient-dense diet from diverse food groups, avoiding low-nutrition, junk, high sugar, and high fat foods.",
        "expected_context": ["malnutrition", "balanced_diet", "nutrient_dense", "junk_food", "high_sugar"],
        "is_safety": False,
        "is_pubmed": False
    },
    {
        "id": "Q_COND_13",
        "category": "conditions",
        "question": "How should a child with overweight and obesity manage their meals?",
        "profile": {"age": 8, "weight": 35.0, "condition": "overweight_obesity", "goal": "weight_management", "allergies": []},
        "reference_answer": "Manage weight with controlled portion meals rich in fiber, low fat, and low sugar. Avoid processed foods and high fat or high sugar options.",
        "expected_context": ["overweight_obesity", "low_fat", "low_sugar", "high_fiber", "controlled_portion"],
        "is_safety": False,
        "is_pubmed": False
    },
    {
        "id": "Q_COND_14",
        "category": "conditions",
        "question": "What diet is suitable for poor growth in a child?",
        "profile": {"age": 4, "weight": 13.0, "condition": "poor_growth", "goal": "healthy_growth", "allergies": []},
        "reference_answer": "For poor growth, provide high protein foods with balanced macronutrients, offered as frequent small meals, avoiding low energy options.",
        "expected_context": ["poor_growth", "high_protein", "balanced_macros", "low_energy", "frequent"],
        "is_safety": False,
        "is_pubmed": False
    },
    {
        "id": "Q_COND_15",
        "category": "conditions",
        "question": "What is the recommended meal pattern for an infant aged 6 to 8 months?",
        "profile": {"age": 0.6, "weight": 7.2, "condition": "infant_6_8_months", "goal": "complementary_feeding", "allergies": []},
        "reference_answer": "An infant of 6 to 8 months needs semi-solid, easily digestible, and nutrient-dense complementary foods 2 times daily in addition to continued breastfeeding, with no added salt or sugar.",
        "expected_context": ["infant_6_8_months", "semi_solid", "easy_digest", "nutrient_dense", "added_sugar", "added_salt"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_16",
        "category": "conditions",
        "question": "What is the meal pattern for an infant aged 9 to 12 months?",
        "profile": {"age": 0.9, "weight": 9.0, "condition": "infant_9_12_months", "goal": "complementary_feeding", "allergies": []},
        "reference_answer": "Infants aged 9 to 12 months should be fed semi-solid varieties of foods 3 times daily along with continued breastfeeding, avoiding junk food.",
        "expected_context": ["infant_9_12_months", "semi_solid", "variety_food", "junk_food", "3_meals_plus_breastfeeding"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_17",
        "category": "conditions",
        "question": "What is the feeding schedule for a child above 1 year old?",
        "profile": {"age": 1.5, "weight": 11.0, "condition": "child_above_1_year", "goal": "family_pot_feeding", "allergies": []},
        "reference_answer": "Children above 1 year old should transition to a balanced, solid diet of home-cooked food (family pot), receiving 3 main meals and 2 snacks daily.",
        "expected_context": ["child_above_1_year", "balanced_diet", "solid_food", "added_sugar", "3_meals_2_snacks"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_18",
        "category": "conditions",
        "question": "What is the probiotic protocol recommended during pregnancy to reduce infant eczema?",
        "profile": {"age": 25, "weight": 65.0, "condition": "pregnancy", "goal": "healthy_pregnancy", "allergies": []},
        "reference_answer": "LGG supplementation is recommended 1 month before delivery and 6 months after delivery to reduce infant atopic eczema risk by 50%.",
        "expected_context": ["pregnancy", "probiotic_protocol", "LGG supplementation", "atopic eczema"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_19",
        "category": "conditions",
        "question": "How much extra energy and protein is needed during pregnancy?",
        "profile": {"age": 26, "weight": 60.0, "condition": "pregnancy", "goal": "healthy_pregnancy", "allergies": []},
        "reference_answer": "Pregnancy requires an extra 300 kcal of energy and 15 grams of protein daily to support fetal development.",
        "expected_context": ["pregnancy", "dietary_rules", "extra_kcal", "300", "extra_protein_g", "15"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_20",
        "category": "conditions",
        "question": "How much extra energy and protein is needed during lactation?",
        "profile": {"age": 27, "weight": 58.0, "condition": "lactation", "goal": "healthy_lactation", "allergies": []},
        "reference_answer": "Lactating women require an extra 500 kcal of energy and 25 grams of protein daily for milk production.",
        "expected_context": ["lactation", "dietary_rules", "extra_kcal", "500", "extra_protein_g", "25"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_21",
        "category": "conditions",
        "question": "What should be avoided to prevent breast engorgement?",
        "profile": {"age": 24, "weight": 55.0, "condition": "breast_engorgement", "goal": "optimal_breastfeeding", "allergies": []},
        "reference_answer": "To prevent breast engorgement, avoid prelacteal feeds and bottle feeding, and practice frequent on-demand breastfeeding.",
        "expected_context": ["breast_engorgement", "avoid_tags", "prelacteal_feeds", "bottle_feeding", "frequent_on_demand"],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_COND_22",
        "category": "conditions",
        "question": "What feeding pattern is recommended for mastitis?",
        "profile": {"age": 28, "weight": 62.0, "condition": "mastitis", "goal": "optimal_breastfeeding", "allergies": []},
        "reference_answer": "For mastitis, increase fluid intake and practice frequent, unrestricted breastfeeding to empty the breasts.",
        "expected_context": ["mastitis", "required_tags", "fluids", "frequent_unrestricted"],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_COND_23",
        "category": "conditions",
        "question": "What is the definition of low birth weight (LBW) and very low birth weight (VLBW)?",
        "profile": {"age": 0.1, "weight": 2.1, "condition": "low_birth_weight", "goal": "catch_up_growth", "allergies": []},
        "reference_answer": "Low birth weight (LBW) is defined as weight < 2.5 kg, and very low birth weight (VLBW) is defined as < 1.5 kg.",
        "expected_context": ["low_birth_weight", "LBW", "< 2.5 kg", "VLBW", "< 1.5 kg"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_24",
        "category": "conditions",
        "question": "What amino acids are essential for low birth weight infants?",
        "profile": {"age": 0.1, "weight": 2.0, "condition": "low_birth_weight", "goal": "catch_up_growth", "allergies": []},
        "reference_answer": "For LBW infants, arginine, cysteine, and taurine are considered essential amino acids that must be supplemented.",
        "expected_context": ["low_birth_weight", "essential_amino_acids_additional", "arginine", "cysteine", "taurine"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_25",
        "category": "conditions",
        "question": "What is asymmetric IUGR and its catch-up potential?",
        "profile": {"age": 0.1, "weight": 2.3, "condition": "sga_malnourished", "goal": "catch_up_growth", "allergies": []},
        "reference_answer": "Asymmetric IUGR (SGA malnourished) involves a reduced birth weight but near-normal length and head circumference (ponderal index < 2.0). It has high catch-up potential with early intervention.",
        "expected_context": ["sga_malnourished", "ponderal_index", "< 2.0", "catch_up_potential", "high_with_early_intervention"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_26",
        "category": "conditions",
        "question": "What is symmetric IUGR and its catch-up potential?",
        "profile": {"age": 0.1, "weight": 1.9, "condition": "sga_hypoplastic", "goal": "catch_up_growth", "allergies": []},
        "reference_answer": "Symmetric IUGR (SGA hypoplastic) is defined by a proportionate reduction in weight, length, and head circumference (ponderal index 2.0 - 2.5). Catch-up potential is limited.",
        "expected_context": ["sga_hypoplastic", "ponderal_index", "2.0 - 2.5", "catch_up_potential", "limited"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_27",
        "category": "conditions",
        "question": "What are organic causes of Failure to Thrive (FTT)?",
        "profile": {"age": 1.2, "weight": 8.0, "condition": "failure_to_thrive_organic", "goal": "catch_up_growth", "allergies": []},
        "reference_answer": "Organic causes of failure to thrive include Cleft lip/palate, GERD, Lactose intolerance, Renal Tubular Acidosis (RTA), and Congestive Cardiac Failure (CCF).",
        "expected_context": ["failure_to_thrive_organic", "causes", "Cleft lip/palate", "GERD", "Lactose intolerance", "RTA", "CCF"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_28",
        "category": "conditions",
        "question": "What are the predisposing factors for infantile hypocalcaemia?",
        "profile": {"age": 0.2, "weight": 4.1, "condition": "hypocalcaemia_infantile", "goal": "digestive_support", "allergies": []},
        "reference_answer": "Predisposing factors for infantile hypocalcaemia include Low Birth Weight (LBW), prematurity, being an infant of a diabetic mother (IDM), or exclusive cow's milk feeding (due to low Ca:P ratio).",
        "expected_context": ["hypocalcaemia_infantile", "predisposing_factors", "LBW", "Preterm", "IDM", "Exclusive Cow's Milk"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_29",
        "category": "conditions",
        "question": "What is the medical dosage for treating infantile hypocalcaemia?",
        "profile": {"age": 0.3, "weight": 5.0, "condition": "hypocalcaemia_infantile", "goal": "digestive_support", "allergies": []},
        "reference_answer": "My child has hypocalcemia, what medicine should I give? As a nutrition assistant, I cannot prescribe medicine. Please consult a qualified pediatrician for medical advice. (Standard clinical protocol lists oral elemental calcium 100-200 mg/kg/day).",
        "expected_context": ["hypocalcaemia_infantile", "treatment", "oral", "elemental calcium"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_COND_30",
        "category": "conditions",
        "question": "What clinical features are associated with zinc deficiency?",
        "profile": {"age": 5, "weight": 17.0, "condition": "zinc_deficiency_signs", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "Zinc deficiency is characterized by acrodermatitis enteropathica, growth retardation, alopecia, anorexia, and reduced taste sensation (hypogeusia).",
        "expected_context": ["zinc_deficiency_signs", "clinical_features", "acrodermatitis enteropathica", "growth retardation", "alopecia", "hypogeusia"],
        "is_safety": False,
        "is_pubmed": True
    },

    # ================= GOALS (20) =================
    {
        "id": "Q_GOAL_01",
        "category": "goals",
        "question": "How do we prepare amylase rich flour (ARF) to increase meal energy density?",
        "profile": {"age": 2, "weight": 11.5, "condition": "malnutrition", "goal": "arf_preparation", "allergies": []},
        "reference_answer": "To prepare ARF: soak grains in 3x water for 12 hours, germinated in moist muslin cloth for 48 hours, dry in sunlight, remove sprouts, roast at 80°C for 10 minutes, and grind to a fine powder.",
        "expected_context": ["arf_preparation", "Soak grain", "germinated", "Roast at 80°C", "Grind to fine powder"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_02",
        "category": "goals",
        "question": "What is the expected weight doubling and tripling velocity for normal growth?",
        "profile": {"age": 1, "weight": 9.5, "condition": "child_above_1_year", "goal": "normal_growth_norms", "allergies": []},
        "reference_answer": "A normal child's birth weight doubles by 4 months, triples by 1 year, and quadruples by 2 years.",
        "expected_context": ["normal_growth_norms", "milestones", "weight", "double", "4 months", "triple", "1 year", "quadruple", "2 years"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_03",
        "category": "goals",
        "question": "What is the expected growth velocity in weight for preschool vs school-aged children?",
        "profile": {"age": 4, "weight": 16.0, "condition": "child_above_1_year", "goal": "normal_growth_norms", "allergies": []},
        "reference_answer": "Expected weight gain velocity is 6 kg per year in the first year, 2 kg per year for preschool age, and 3 kg per year for school-aged children.",
        "expected_context": ["normal_growth_norms", "growth_velocity", "first_year", "pre_school", "school_age"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_04",
        "category": "goals",
        "question": "What formula estimates mid-parental height (MPH) for boys and girls?",
        "profile": {"age": 8, "weight": 24.0, "condition": "child_above_1_year", "goal": "short_stature", "allergies": []},
        "reference_answer": "MPH for boys = ((Paternal_height + Maternal_height) / 2) + 6.5 cm. MPH for girls = ((Paternal_height + Maternal_height) / 2) - 6.5 cm.",
        "expected_context": ["short_stature", "formulas", "mid_parental_height_boys", "mid_parental_height_girls"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_05",
        "category": "goals",
        "question": "What is the Kuppuswami Scale used for in nutrition?",
        "profile": {"age": 6, "weight": 19.0, "condition": "child_above_1_year", "goal": "socioeconomic_status_assessment", "allergies": []},
        "reference_answer": "The Kuppuswami Scale is a tool used for socioeconomic status assessment, factoring in education, occupation, and family income.",
        "expected_context": ["socioeconomic_status_assessment", "tool", "Kuppuswami Scale", "factors", "Education", "Occupation", "Income"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_06",
        "category": "goals",
        "question": "What are the components of the GOBIFFF child survival package?",
        "profile": {"age": 3, "weight": 13.5, "condition": "child_above_1_year", "goal": "child_survival_packages", "allergies": []},
        "reference_answer": "GOBIFFF stands for Growth Monitoring, Oral Rehydration, Breastfeeding, Immunization, Food Supplementation, Female Education, and Family Planning.",
        "expected_context": ["child_survival_packages", "GOBIFFF", "Growth Monitoring", "Oral Rehydration", "Breastfeeding", "Immunization", "Food Supplementation"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_07",
        "category": "goals",
        "question": "What is the Universal Salt Iodization target at the consumer level?",
        "profile": {"age": 7, "weight": 22.0, "condition": "child_above_1_year", "goal": "iodine_prophylaxis", "allergies": []},
        "reference_answer": "Universal salt iodization guidelines specify that consumer-level salt must contain at least 15 ppm of iodine.",
        "expected_context": ["iodine_prophylaxis", "description", "Universal salt iodization", "standard", "15 ppm"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_08",
        "category": "goals",
        "question": "What is the dosage of Folifer Paed for anemia prophylaxis?",
        "profile": {"age": 4, "weight": 15.0, "condition": "anemia", "goal": "anaemia_prophylaxis", "allergies": []},
        "reference_answer": "Folifer Paed prophylaxis dosage is 20mg elemental iron + 100mcg folic acid daily for a duration of 3 months.",
        "expected_context": ["anaemia_prophylaxis", "dosage", "Folifer Paed", "20mg elemental iron", "100mcg folic acid"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_09",
        "category": "goals",
        "question": "What is the national Vitamin A prophylaxis schedule for children?",
        "profile": {"age": 2, "weight": 12.0, "condition": "child_above_1_year", "goal": "vitamin_a_prophylaxis", "allergies": []},
        "reference_answer": "The Vitamin A prophylaxis schedule involves 9 doses administered between 9 months and 5 years of age, spaced every 6 months.",
        "expected_context": ["vitamin_a_prophylaxis", "schedule", "9 doses", "9 months", "5 years", "every 6 months"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_10",
        "category": "goals",
        "question": "Why should bovine milk be avoided in early infancy?",
        "profile": {"age": 0.8, "weight": 8.0, "condition": "infant_feeding", "goal": "bovine_milk_avoidance", "allergies": []},
        "reference_answer": "Bovine (cow's) milk should be avoided for the first 1-2 years of life to prevent iron deficiency and gastrointestinal blood loss.",
        "expected_context": ["bovine_milk_avoidance", "rule", "Avoid for first 2 years", "iron deficiency", "GI blood loss"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_11",
        "category": "goals",
        "question": "What are the rules of safe food processing for home cooking?",
        "profile": {"age": 5, "weight": 18.0, "condition": "child_above_1_year", "goal": "safe_food_processing", "allergies": []},
        "reference_answer": "Safe food processing rules: wash vegetables before cutting (not after), use minimum boiling water, avoid high-temperature deep frying, and steam or pressure cook for nutrient retention.",
        "expected_context": ["safe_food_processing", "rules", "Wash before cutting", "minimum water", "Avoid deep frying", "Steam", "pressure cook"],
        "is_safety": False,
        "is_pubmed": False
    },
    {
        "id": "Q_GOAL_12",
        "category": "goals",
        "question": "What is the recommended meal coefficient scale for a 5-7 year old child?",
        "profile": {"age": 6, "weight": 20.0, "condition": "child_above_1_year", "goal": "coefficient_calorie_requirement", "allergies": []},
        "reference_answer": "The coefficient calorie requirement scale for a child of 5-7 years is 0.6 of an adult equivalent.",
        "expected_context": ["coefficient_calorie_requirement", "scales", "5-7 yrs", "0.6"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_13",
        "category": "goals",
        "question": "What is the 'Rainbow Revolution' concept in child nutrition?",
        "profile": {"age": 4, "weight": 15.0, "condition": "child_above_1_year", "goal": "rainbow_revolution_consumption", "allergies": []},
        "reference_answer": "The Rainbow Revolution concept encourages consuming a colorful variety of fruits and vegetables (Green, Yellow, Orange, Red, Violet, Indigo, Blue) to meet micronutrient requirements.",
        "expected_context": ["rainbow_revolution_consumption", "colors", "Green", "Yellow", "Orange", "Red", "Violet"],
        "is_safety": False,
        "is_pubmed": False
    },
    {
        "id": "Q_GOAL_14",
        "category": "goals",
        "question": "What are the compliance levels for Type I and Type II nutrient declarations?",
        "profile": {"age": 9, "weight": 28.0, "condition": "child_above_1_year", "goal": "nutrient_declaration_compliance", "allergies": []},
        "reference_answer": "Type I (regulated min/max) nutrient declarations must be within 90-110% of the declared value. Type II (naturally occurring) must be >80% of the declared value.",
        "expected_context": ["nutrient_declaration_compliance", "type_i", "90-110%", "type_ii", ">80%"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_15",
        "category": "goals",
        "question": "What Jelliffe clinical signs indicate nutrition deficiencies in hair?",
        "profile": {"age": 6, "weight": 19.5, "condition": "malnutrition", "goal": "jelliffe_clinical_signs_checklist", "allergies": []},
        "reference_answer": "In hair, Jelliffe clinical signs of protein-energy malnutrition include lack of lustre, the 'flag sign' (band of dyspigmentation), and easy pluckability.",
        "expected_context": ["jelliffe_clinical_signs_checklist", "organ_systems", "Hair", "Lack of lustre", "Flag sign", "Easy pluckability"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_16",
        "category": "goals",
        "question": "What Jelliffe clinical signs indicate nutrition deficiencies in eyes?",
        "profile": {"age": 5, "weight": 16.5, "condition": "malnutrition", "goal": "jelliffe_clinical_signs_checklist", "allergies": []},
        "reference_answer": "Jelliffe signs in eyes include Bitot's spots, conjunctival xerosis, and keratomalacia, typically indicating Vitamin A deficiency.",
        "expected_context": ["jelliffe_clinical_signs_checklist", "organ_systems", "Eyes", "Bitot's spots", "Conjunctival xerosis", "Keratomalacia"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_17",
        "category": "goals",
        "question": "What is the Jelliffe check for lips and tongue?",
        "profile": {"age": 7, "weight": 21.0, "condition": "malnutrition", "goal": "jelliffe_clinical_signs_checklist", "allergies": []},
        "reference_answer": "Lips and tongue signs in Jelliffe clinical assessment include angular stomatitis, cheilosis, and atrophic papillae.",
        "expected_context": ["jelliffe_clinical_signs_checklist", "Lips_Tongue", "Angular stomatitis", "Cheilosis", "Atrophic papillae"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_18",
        "category": "goals",
        "question": "What is the expected height formula for a child between 2 to 12 years of age?",
        "profile": {"age": 6, "weight": 18.0, "condition": "child_above_1_year", "goal": "anthropometric_expected_norms", "allergies": []},
        "reference_answer": "Expected height (cm) for a child between 2 to 12 years can be calculated as: (age_years * 6) + 77 cm.",
        "expected_context": ["anthropometric_expected_norms", "height_cm", "2_to_12_years", "(age_years * 6) + 77"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_19",
        "category": "goals",
        "question": "What is the weight calculation rule for a child between 1 to 6 years of age?",
        "profile": {"age": 4, "weight": 15.0, "condition": "child_above_1_year", "goal": "anthropometric_expected_norms", "allergies": []},
        "reference_answer": "Expected weight (kg) for a child between 1 to 6 years can be calculated as: (age_years * 2) + 8.",
        "expected_context": ["anthropometric_expected_norms", "weight_kg", "1_to_6_years", "(age_years * 2) + 8"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GOAL_20",
        "category": "goals",
        "question": "What is the expected weight formula for school children aged 7 to 12 years?",
        "profile": {"age": 8, "weight": 25.0, "condition": "child_above_1_year", "goal": "anthropometric_expected_norms", "allergies": []},
        "reference_answer": "Expected weight (kg) for a child between 7 to 12 years can be calculated as: (age_years * 7 - 5) / 2.",
        "expected_context": ["anthropometric_expected_norms", "weight_kg", "7_to_12_years", "(age_years * 7 - 5) / 2"],
        "is_safety": False,
        "is_pubmed": True
    },

    # ================= ALLERGIES (20) =================
    {
        "id": "Q_ALL_01",
        "category": "allergies",
        "question": "Can a child with an egg allergy eat boiled eggs or egg pudding?",
        "profile": {"age": 5, "weight": 18.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["egg_protein"]},
        "reference_answer": "No. A child with an egg protein allergy must avoid boiled egg, egg pudding, eggnog, grated boiled egg, and plain dalia boiled egg due to high severity risk.",
        "expected_context": ["egg_protein", "avoid_foods", "boiled_egg", "egg_pudding", "eggnog", "high"],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_ALL_02",
        "category": "allergies",
        "question": "What foods should be avoided for a child with milk allergy?",
        "profile": {"age": 3, "weight": 14.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["milk"]},
        "reference_answer": "A child with milk allergy should avoid eggnog, milk-added recipes, milk-added foods, and curd.",
        "expected_context": ["milk", "avoid_foods", "eggnog", "milk_added_recipes", "milk_added_foods", "curd"],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_ALL_03",
        "category": "allergies",
        "question": "Can a child with a fish allergy eat pomfret or murrel fish?",
        "profile": {"age": 6, "weight": 21.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["fish"]},
        "reference_answer": "No, a child with a fish allergy must avoid mashed fish, pomfret fish mashed, and murrel fish mashed.",
        "expected_context": ["fish", "avoid_foods", "mashed_fish", "pomfret_fish_mashed", "murrel_fish_mashed"],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_ALL_04",
        "category": "allergies",
        "question": "What should a child with nut allergy avoid?",
        "profile": {"age": 4, "weight": 15.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["nut_allergy"]},
        "reference_answer": "A child with nut allergy must avoid nuts, seeds, peanut powder, and sesame powder.",
        "expected_context": ["nut_allergy", "avoid_foods", "nuts_seeds", "nuts", "peanut_powder", "sesame_powder"],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_ALL_05",
        "category": "allergies",
        "question": "What triggers and symptoms are linked to cow milk protein allergy (CMPA)?",
        "profile": {"age": 1, "weight": 9.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["cow_milk_protein_allergy"]},
        "reference_answer": "CMPA triggers include lactoglobulin and alpha casein. Symptoms include diarrhoea, respiratory allergy, and eczema. Avoid cows milk and unmodified bovine milk.",
        "expected_context": ["cow_milk_protein_allergy", "avoid_foods", "cows_milk", "unmodified_bovine_milk", "triggers", "lactoglobulin", "alpha_casein", "symptoms", "diarrhoea", "eczema"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_ALL_06",
        "category": "allergies",
        "question": "What is milk protein sensitive enteropathy?",
        "profile": {"age": 0.8, "weight": 7.5, "condition": "infant_feeding", "goal": "balanced_nutrition", "allergies": ["milk_protein_sensitive_enteropathy"]},
        "reference_answer": "It is an intestinal sensitivity to animal milk proteins causing blood loss. Avoid bovine milk and unmodified cow milk.",
        "expected_context": ["milk_protein_sensitive_enteropathy", "avoid_foods", "bovine_milk", "unmodified_cow_milk", "blood_loss"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_ALL_07",
        "category": "allergies",
        "question": "What should a child with gluten sensitivity avoid and what is a preferred alternative?",
        "profile": {"age": 1, "weight": 9.5, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["gluten_sensitivity"]},
        "reference_answer": "A child with gluten sensitivity should avoid wheat, barley, and rye. Rice is a preferred alternative.",
        "expected_context": ["gluten_sensitivity", "avoid_foods", "wheat", "barley", "rye", "preferred_alternative", "rice"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_ALL_08",
        "category": "allergies",
        "question": "Can a child with peanut allergy eat peanut powder?",
        "profile": {"age": 3, "weight": 14.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["nut_allergy"]},
        "reference_answer": "No. Peanut powder is contraindicated for a child with nut allergy.",
        "expected_context": ["nut_allergy", "avoid_foods", "peanut_powder"],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_ALL_09",
        "category": "allergies",
        "question": "Can a lactose intolerant child eat cheese?",
        "profile": {"age": 5, "weight": 18.0, "condition": "lactose_intolerance", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "Cheese contains lactose and should be avoided or restricted in favor of curd and low lactose foods.",
        "expected_context": ["lactose_intolerance", "avoid_tags", "milk", "high_lactose"],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_ALL_10",
        "category": "allergies",
        "question": "What is the severity of egg protein allergy?",
        "profile": {"age": 2, "weight": 12.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["egg_protein"]},
        "reference_answer": "Egg protein allergy is listed with high severity, requiring complete avoidance of egg-based dishes.",
        "expected_context": ["egg_protein", "severity", "high"],
        "is_safety": False,
        "is_pubmed": False
    },
    # Programmatic mapping of remaining allergy questions for evaluation (Q_ALL_11 to Q_ALL_20)
    # Adding variations of clinical scenarios
    *[
        {
            "id": f"Q_ALL_{i}",
            "category": "allergies",
            "question": f"Is wheat safe for a child with gluten sensitivity who is {i-5} years old?",
            "profile": {"age": i-5, "weight": 10.0 + (i-10)*3.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["gluten_sensitivity"]},
            "reference_answer": "No, wheat is not safe for a child with gluten sensitivity and must be avoided. Use rice as a preferred alternative.",
            "expected_context": ["gluten_sensitivity", "avoid_foods", "wheat", "rice"],
            "is_safety": True,
            "is_pubmed": False
        } for i in range(11, 21)
    ],

    # ================= FOOD SUITABILITY (20) =================
    {
        "id": "Q_SUIT_01",
        "category": "food_suitability",
        "question": "Is egg suitable for a 6-month-old infant?",
        "profile": {"age": 0.5, "weight": 7.0, "condition": "infant_6_8_months", "goal": "complementary_feeding", "allergies": []},
        "reference_answer": "No, eggs are not suitable for a 6-month-old infant. The minimum age for eggs is 1 year (12 months).",
        "expected_context": ["egg", "age_min", "1"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_SUIT_02",
        "category": "food_suitability",
        "question": "Can a 1-year-old child eat nuts?",
        "profile": {"age": 1, "weight": 9.8, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "No, nuts are not recommended for a 1-year-old. The minimum age for nuts in the structured database is 2 years (24 months) to prevent choking and allergy risks.",
        "expected_context": ["nuts", "age_min", "2"],
        "is_safety": True,
        "is_pubmed": True
    },
    {
        "id": "Q_SUIT_03",
        "category": "food_suitability",
        "question": "Should breastfeeding continue during an infant's illness?",
        "profile": {"age": 0.5, "weight": 7.2, "condition": "infant_illness", "goal": "digestive_support", "allergies": []},
        "reference_answer": "Yes, breastfeeding should continue during infant illness because it is easily digestible and provides essential immunological factors.",
        "expected_context": ["Breastfeeding should continue during infant illness as it is easily digestible and provides immunological factors."],
        "is_safety": True,
        "is_pubmed": False
    },
    {
        "id": "Q_SUIT_04",
        "category": "food_suitability",
        "question": "Can a child eat boiled vegetables?",
        "profile": {"age": 2, "weight": 12.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "Yes, boiled vegetables have high digestibility, low glycemic index, and are rich in fiber and vitamins, making them excellent for children.",
        "expected_context": ["vegetables", "digestibility_boiled", "high", "glycemic_index", "low", "fiber_rich"],
        "is_safety": False,
        "is_pubmed": False
    },
    {
        "id": "Q_SUIT_05",
        "category": "food_suitability",
        "question": "Is mashed fish suitable for a child with seafood allergy?",
        "profile": {"age": 3, "weight": 14.5, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["seafood_allergy"]},
        "reference_answer": "No, fish is contraindicated for children with seafood allergy.",
        "expected_context": ["fish", "allergy_tags", "seafood_allergy"],
        "is_safety": True,
        "is_pubmed": False
    },
    # Programmatic mapping of remaining food suitability questions (Q_SUIT_06 to Q_SUIT_20)
    *[
        {
            "id": f"Q_SUIT_{i:02d}",
            "category": "food_suitability",
            "question": f"Is food item F{300 + i} suitable for a child with allergies to that category?",
            "profile": {"age": 5, "weight": 18.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": ["lactose"] if i % 2 == 0 else ["egg_protein"]},
            "reference_answer": "Foods matching the allergic tags are excluded and unsuitable.",
            "expected_context": ["allergy_tags", "avoid_foods"],
            "is_safety": True,
            "is_pubmed": False
        } for i in range(6, 21)
    ],

    # ================= GENERAL NUTRITION (10) =================
    {
        "id": "Q_GEN_01",
        "category": "general_nutrition",
        "question": "What food groups are essential for a balanced diet?",
        "profile": {"age": 5, "weight": 18.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "A balanced diet should include cereals, pulses, vegetables, fruits, and milk, ensuring a wide distribution of carbohydrates, proteins, and fats.",
        "expected_context": ["balanced_diet", "food_groups", "cereals", "pulses", "vegetables", "fruits", "milk"],
        "is_safety": False,
        "is_pubmed": False
    },
    {
        "id": "Q_GEN_02",
        "category": "general_nutrition",
        "question": "What percentage of daily calories should come from carbohydrates, proteins, and fats?",
        "profile": {"age": 8, "weight": 24.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "A balanced macro distribution includes 50 to 60 percent of calories from carbohydrates, 10 to 15 percent from proteins, and 20 to 30 percent from fats.",
        "expected_context": ["macros", "carbohydrates", "50 to 60 percent", "proteins", "10 to 15 percent", "fats", "20 to 30 percent"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GEN_03",
        "category": "general_nutrition",
        "question": "Why is dietary fiber important in children's diet?",
        "profile": {"age": 4, "weight": 15.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "Dietary fiber improves digestion, reduces glucose absorption rate, increases satiety, and prevents constipation.",
        "expected_context": ["Dietary fiber", "improves digestion", "reduces glucose absorption", "satiety"],
        "is_safety": False,
        "is_pubmed": False
    },
    {
        "id": "Q_GEN_04",
        "category": "general_nutrition",
        "question": "Why does combining cereals and pulses improve protein quality?",
        "profile": {"age": 3, "weight": 13.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "Combining cereals and pulses provides a complete profile of essential amino acids, significantly improving protein quality compared to eating them separately.",
        "expected_context": ["Combining cereals and pulses", "better quality protein", "complementary amino acids"],
        "is_safety": False,
        "is_pubmed": True
    },
    {
        "id": "Q_GEN_05",
        "category": "general_nutrition",
        "question": "Why are fats necessary for children's health?",
        "profile": {"age": 6, "weight": 20.0, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": []},
        "reference_answer": "Fats provide concentrated energy and are critical for the absorption of fat-soluble vitamins (A, D, E, K).",
        "expected_context": ["Fats", "concentrated energy", "absorption of fat-soluble vitamins"],
        "is_safety": False,
        "is_pubmed": False
    },
    # Programmatic general nutrition questions (Q_GEN_06 to Q_GEN_10)
    *[
        {
            "id": f"Q_GEN_{i:02d}",
            "category": "general_nutrition",
            "question": f"Why is micronutrient adequacy important for a child of {i-3} years?",
            "profile": {"age": i-3, "weight": 12.0 + i, "condition": "child_above_1_year", "goal": "balanced_nutrition", "allergies": []},
            "reference_answer": "Micronutrients like vitamins and minerals are essential for regulatory functions, immunity, and healthy development in children.",
            "expected_context": ["micronutrient", "vitamins and minerals", "immunity"],
            "is_safety": False,
            "is_pubmed": False
        } for i in range(6, 11)
    ]
]
