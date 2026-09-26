"""Condition registry: one shared vocabulary for the guide, the assessment engine and intake.

Entries are declarative and deterministic: nothing here reads a model. ``awareness`` is
factual orientation only (what the condition is and what nutrients it commonly concerns);
it never states a dose, a prescription or a personal target. Matching is exact after
casefold + trim, against the slug, the label or an alias, so a lay phrasing such as
"sugar problem" resolves to the same slug a clinician would use. Anything unmatched is
kept as unrecognised by the caller and is never force-mapped onto a guessed condition.
"""

CONDITION_REGISTRY_VERSION = "conditions-2026-09-26.1"

CATEGORIES = [
    "metabolic",
    "cardiovascular",
    "renal",
    "gastrointestinal",
    "endocrine",
    "haematologic",
    "musculoskeletal",
    "reproductive",
    "neuro/other",
]

# The shared lab vocabulary. Report extraction, the guide and intake rules all emit and
# read exactly these strings, so a parameter is comparable across the whole pipeline.
CANONICAL_LAB_KEYS = [
    "hemoglobin_g_dl",
    "rbc_million_ul",
    "wbc_thousand_ul",
    "platelet_thousand_ul",
    "mcv_fl",
    "ferritin_ng_ml",
    "fasting_glucose_mg_dl",
    "random_glucose_mg_dl",
    "hba1c_percent",
    "total_cholesterol_mg_dl",
    "ldl_cholesterol_mg_dl",
    "hdl_cholesterol_mg_dl",
    "triglycerides_mg_dl",
    "tsh_miu_l",
    "t3_ng_dl",
    "t4_ug_dl",
    "creatinine_mg_dl",
    "egfr_ml_min",
    "urea_mg_dl",
    "uric_acid_mg_dl",
    "sodium_meq_l",
    "potassium_meq_l",
    "phosphorus_mg_dl",
    "calcium_mg_dl",
    "alt_u_l",
    "ast_u_l",
    "bilirubin_total_mg_dl",
    "albumin_g_dl",
    "alp_u_l",
    "vitamin_d_ng_ml",
    "vitamin_b12_pg_ml",
    "folate_ng_ml",
    "crp_mg_l",
    "systolic_bp_mmhg",
    "diastolic_bp_mmhg",
    "weight_kg",
    "height_cm",
    "bmi",
]

# --- Registry ---------------------------------------------------------------------------
#
# ``guidance_confidence`` follows the frozen literal:
#   established        - mainstream, widely agreed nutrient relationship
#   general_wellbeing  - sensible general food guidance, not a clinical prescription
#   clinician_only     - individual clinical advice is required; never a numeric target
#
# ``lab_links`` may be empty when a condition has no single defining laboratory value.

CONDITIONS = [
    {
        "slug": "type_1_diabetes",
        "label": "Type 1 diabetes",
        "category": "metabolic",
        "aliases": ["type 1 diabetes", "t1dm", "insulin dependent diabetes", "juvenile diabetes"],
        "nutrient_focus": ["carbohydrate", "added sugars", "saturated fat"],
        "awareness": (
            "Type 1 diabetes is an autoimmune condition in which the body produces little or "
            "no insulin. Carbohydrate amount and timing interact with insulin, so food choices "
            "are usually planned with the clinical team rather than from a fixed number."
        ),
        "questions": [
            "How should carbohydrate be counted for the insulin plan I use?",
            "Which foods should I adjust when my readings run high?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/type-1-diabetes"
        ],
        "lab_links": ["hba1c_percent", "fasting_glucose_mg_dl"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "type_2_diabetes",
        "label": "Type 2 diabetes",
        "category": "metabolic",
        "aliases": [
            "type 2 diabetes",
            "t2dm",
            "diabetes",
            "sugar problem",
            "sugar disease",
            "madhumeh",
        ],
        "nutrient_focus": ["carbohydrate", "added sugars", "saturated fat", "fibre"],
        "awareness": (
            "Type 2 diabetes is a condition where blood glucose runs high because insulin is "
            "less effective or is produced in insufficient amounts. Total carbohydrate, free "
            "sugars and saturated fat are the nutrients most discussed for glucose and heart "
            "risk, and a sugar-free label does not by itself make a food low in carbohydrate."
        ),
        "questions": [
            "What daily carbohydrate amount fits my glucose readings and medicines?",
            "How much free sugar should I treat as my ceiling?",
        ],
        "sources": [
            "https://www.who.int/news-room/fact-sheets/detail/diabetes",
            "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/type-2-diabetes",
        ],
        "lab_links": ["hba1c_percent", "fasting_glucose_mg_dl", "random_glucose_mg_dl"],
        "guidance_confidence": "established",
    },
    {
        "slug": "prediabetes",
        "label": "Prediabetes",
        "category": "metabolic",
        "aliases": [
            "pre-diabetes",
            "borderline diabetes",
            "impaired glucose tolerance",
            "impaired fasting glucose",
        ],
        "nutrient_focus": ["added sugars", "carbohydrate", "fibre"],
        "awareness": (
            "Prediabetes means blood glucose is above the usual range but not yet in the "
            "diabetes range. Free sugars and refined carbohydrate are commonly reduced, and "
            "regular activity and weight change are usually part of the plan."
        ),
        "questions": [
            "How often should my glucose be rechecked?",
            "What sugar intake should I aim for while I make changes?",
        ],
        "sources": ["https://www.cdc.gov/diabetes/about/prediabetes.html"],
        "lab_links": ["hba1c_percent", "fasting_glucose_mg_dl"],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "metabolic_syndrome",
        "label": "Metabolic syndrome",
        "category": "metabolic",
        "aliases": ["syndrome x", "insulin resistance syndrome", "metabolic disorder"],
        "nutrient_focus": ["added sugars", "saturated fat", "sodium", "fibre"],
        "awareness": (
            "Metabolic syndrome is a cluster of findings - raised waist measure, glucose, "
            "triglycerides or blood pressure, with low HDL. It signals higher heart and "
            "diabetes risk, so food guidance usually addresses sugars, saturated fat and sodium "
            "together."
        ),
        "questions": [
            "Which of my readings put me in this cluster?",
            "Which single change would help most of these readings at once?",
        ],
        "sources": ["https://www.heart.org/en/health-topics/metabolic-syndrome"],
        "lab_links": [
            "hba1c_percent",
            "fasting_glucose_mg_dl",
            "triglycerides_mg_dl",
            "hdl_cholesterol_mg_dl",
        ],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "obesity",
        "label": "Obesity",
        "category": "metabolic",
        "aliases": ["overweight", "high bmi", "weight problem", "motaapa"],
        "nutrient_focus": ["energy", "added sugars", "saturated fat", "fibre"],
        "awareness": (
            "Obesity is a condition of excess body fat that raises the risk of diabetes, heart "
            "disease and joint problems. Energy intake, free sugars and saturated fat are the "
            "usual food levers, alongside activity and sleep."
        ),
        "questions": [
            "What weight or waist change would be meaningful for my health?",
            "How should I structure meals to reduce energy without losing nutrients?",
        ],
        "sources": ["https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight"],
        "lab_links": ["bmi", "weight_kg", "height_cm"],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "dyslipidaemia",
        "label": "Dyslipidaemia",
        "category": "metabolic",
        "aliases": [
            "high cholesterol",
            "cholesterol problem",
            "high triglycerides",
            "lipid problem",
            "high ldl",
        ],
        "nutrient_focus": ["saturated fat", "fibre", "added sugars"],
        "awareness": (
            "Dyslipidaemia means one or more blood fats are outside the usual range, such as "
            "raised LDL cholesterol or triglycerides. Saturated fat raises LDL, soluble fibre "
            "lowers it, and added sugars raise triglycerides."
        ),
        "questions": [
            "Which of my lipid values is the priority to change?",
            "What saturated fat ceiling fits my risk?",
        ],
        "sources": [
            "https://www.heart.org/en/health-topics/cholesterol",
            "https://www.nhlbi.nih.gov/health/blood-cholesterol",
        ],
        "lab_links": [
            "total_cholesterol_mg_dl",
            "ldl_cholesterol_mg_dl",
            "hdl_cholesterol_mg_dl",
            "triglycerides_mg_dl",
        ],
        "guidance_confidence": "established",
    },
    {
        "slug": "gout",
        "label": "Gout",
        "category": "metabolic",
        "aliases": ["hyperuricaemia", "high uric acid", "uric acid problem", "gouty arthritis"],
        "nutrient_focus": ["added sugars", "purines", "alcohol", "energy"],
        "awareness": (
            "Gout is joint inflammation caused by urate crystals when uric acid stays high. "
            "Purine-rich foods, alcohol and fructose-sweetened drinks are commonly discussed, "
            "and weight change can lower uric acid."
        ),
        "questions": [
            "Which foods are the main trigger for me?",
            "How should sugary drinks change with my uric acid level?",
        ],
        "sources": ["https://www.niams.nih.gov/health-topics/gout"],
        "lab_links": ["uric_acid_mg_dl"],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "nafld",
        "label": "Fatty liver disease (NAFLD/MASLD)",
        "category": "metabolic",
        "aliases": [
            "fatty liver",
            "nafld",
            "masld",
            "liver fat",
            "hepatic steatosis",
            "fatty liver disease",
        ],
        "nutrient_focus": ["added sugars", "saturated fat", "energy", "fibre"],
        "awareness": (
            "Fatty liver disease is fat accumulation in the liver, often linked to weight, "
            "diabetes and blood fats. Added sugars, saturated fat and total energy are the "
            "usual food focus, and alcohol is usually discussed separately."
        ),
        "questions": [
            "How often should my liver tests be rechecked?",
            "Which change would most reduce liver fat for me?",
        ],
        "sources": ["https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash"],
        "lab_links": ["alt_u_l", "ast_u_l", "triglycerides_mg_dl", "hba1c_percent"],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "hypertension",
        "label": "Hypertension",
        "category": "cardiovascular",
        "aliases": [
            "high blood pressure",
            "bp",
            "high bp",
            "htn",
            "blood pressure problem",
            "raised blood pressure",
        ],
        "nutrient_focus": ["sodium", "potassium", "alcohol", "energy"],
        "awareness": (
            "Hypertension is blood pressure that stays above the usual range, which raises "
            "heart, kidney and stroke risk. Sodium drives blood pressure up for many people, "
            "and potassium from whole foods tends to work the other way."
        ),
        "questions": [
            "What sodium target fits my blood pressure and medicines?",
            "Do any of my medicines change potassium advice for me?",
        ],
        "sources": [
            "https://www.who.int/news-room/fact-sheets/detail/hypertension",
            "https://www.heart.org/en/health-topics/high-blood-pressure",
        ],
        "lab_links": ["systolic_bp_mmhg", "diastolic_bp_mmhg"],
        "guidance_confidence": "established",
    },
    {
        "slug": "heart_failure",
        "label": "Heart failure",
        "category": "cardiovascular",
        "aliases": ["congestive heart failure", "chf", "heart weakness", "weak heart"],
        "nutrient_focus": ["sodium", "fluid", "potassium", "energy"],
        "awareness": (
            "Heart failure means the heart pumps less effectively than the body needs, often "
            "causing fluid build-up. Sodium reduction and sometimes fluid limits are usually "
            "individualised, because potassium advice also depends on the medicines used."
        ),
        "questions": [
            "What sodium and fluid limits apply to me?",
            "Should my potassium be watched with my current medicines?",
        ],
        "sources": ["https://www.heart.org/en/health-topics/heart-failure"],
        "lab_links": ["sodium_meq_l", "potassium_meq_l", "egfr_ml_min"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "coronary_artery_disease",
        "label": "Coronary artery disease",
        "category": "cardiovascular",
        "aliases": ["cad", "heart disease", "coronary heart disease", "blocked arteries", "ihd"],
        "nutrient_focus": ["saturated fat", "fibre", "sodium", "added sugars"],
        "awareness": (
            "Coronary artery disease is narrowing of the arteries supplying the heart muscle. "
            "Saturated fat, soluble fibre and sodium are the usual food levers for lowering "
            "heart risk."
        ),
        "questions": [
            "What saturated fat and fibre pattern suits my heart risk?",
            "How does my blood pressure target change my sodium?",
        ],
        "sources": ["https://www.cdc.gov/heart-disease/about/index.html"],
        "lab_links": ["ldl_cholesterol_mg_dl", "hdl_cholesterol_mg_dl", "triglycerides_mg_dl"],
        "guidance_confidence": "established",
    },
    {
        "slug": "stroke",
        "label": "Stroke",
        "category": "cardiovascular",
        "aliases": ["brain attack", "cerebrovascular accident", "cva", "paralysis attack"],
        "nutrient_focus": ["sodium", "saturated fat", "fibre"],
        "awareness": (
            "A stroke happens when blood flow to part of the brain is interrupted. Blood "
            "pressure, blood fats and glucose all influence the risk of a further stroke, so "
            "sodium, saturated fat and fibre are commonly discussed."
        ),
        "questions": [
            "Which readings matter most in preventing another stroke?",
            "What sodium target suits my blood pressure now?",
        ],
        "sources": ["https://www.cdc.gov/stroke/about/index.html"],
        "lab_links": ["systolic_bp_mmhg", "ldl_cholesterol_mg_dl", "hba1c_percent"],
        "guidance_confidence": "established",
    },
    {
        "slug": "ckd",
        "label": "Chronic kidney disease",
        "category": "renal",
        "aliases": [
            "chronic kidney disease",
            "kidney disease",
            "kidney problem",
            "renal disease",
            "ckd",
        ],
        "nutrient_focus": ["sodium", "potassium", "phosphorus", "protein"],
        "awareness": (
            "Chronic kidney disease means kidney function is reduced over time. Sodium, "
            "potassium, phosphorus and protein advice depends on the stage and on blood "
            "results, so it is set individually rather than from a general figure."
        ),
        "questions": [
            "Which stage am I at, and what does that change in my diet?",
            "Which of potassium, phosphorus or protein should I adjust first?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd"
        ],
        "lab_links": ["egfr_ml_min", "creatinine_mg_dl", "potassium_meq_l", "phosphorus_mg_dl"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "hyperkalaemia",
        "label": "High potassium (hyperkalaemia)",
        "category": "renal",
        "aliases": ["high potassium", "hyperkalemia", "raised potassium", "potassium problem"],
        "nutrient_focus": ["potassium"],
        "awareness": (
            "Hyperkalaemia means blood potassium is above the usual range, which can affect "
            "heart rhythm. Potassium intake, some medicines and kidney function all contribute, "
            "so the safe intake is set by the clinical team."
        ),
        "questions": [
            "Which foods raise my potassium the most?",
            "Do my medicines change how I should handle potassium?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd"
        ],
        "lab_links": ["potassium_meq_l", "egfr_ml_min"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "hyperphosphataemia",
        "label": "High phosphate (hyperphosphataemia)",
        "category": "renal",
        "aliases": ["high phosphate", "high phosphorus", "hyperphosphatemia", "phosphate problem"],
        "nutrient_focus": ["phosphorus"],
        "awareness": (
            "Hyperphosphataemia means blood phosphate is above the usual range, which is "
            "common when kidney function is reduced. Phosphate intake and phosphate binders "
            "are managed together by the clinical team."
        ),
        "questions": [
            "Which foods contribute most phosphate for me?",
            "How should food phosphate fit with my binders and timing?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd"
        ],
        "lab_links": ["phosphorus_mg_dl", "egfr_ml_min"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "ibs",
        "label": "Irritable bowel syndrome",
        "category": "gastrointestinal",
        "aliases": [
            "irritable bowel syndrome",
            "spastic colon",
            "mucus colitis",
            "gas problem",
            "ibs",
        ],
        "nutrient_focus": ["fibre", "fluid", "caffeine"],
        "awareness": (
            "Irritable bowel syndrome is a functional gut disorder causing pain, bloating and "
            "changed bowel habit without structural damage. Fibre type, meal size and trigger "
            "foods vary between people, so patterns are usually identified individually."
        ),
        "questions": [
            "Which fibre type suits my predominant symptom?",
            "Should I trial a structured elimination diet with support?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/digestive-diseases/irritable-bowel-syndrome"
        ],
        "lab_links": ["crp_mg_l", "hemoglobin_g_dl"],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "ibd",
        "label": "Inflammatory bowel disease",
        "category": "gastrointestinal",
        "aliases": ["crohn's disease", "crohns", "ulcerative colitis", "colitis", "ibd"],
        "nutrient_focus": ["energy", "protein", "iron", "vitamin B12"],
        "awareness": (
            "Inflammatory bowel disease covers Crohn's disease and ulcerative colitis, in "
            "which the gut is inflamed. Nutrient absorption can fall during flares, so energy, "
            "protein, iron and vitamin B12 are commonly monitored."
        ),
        "questions": [
            "Which nutrients should be monitored with my disease pattern?",
            "What should I eat during a flare?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/digestive-diseases/crohns-disease"
        ],
        "lab_links": ["hemoglobin_g_dl", "ferritin_ng_ml", "vitamin_b12_pg_ml", "albumin_g_dl"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "coeliac_disease",
        "label": "Coeliac disease",
        "category": "gastrointestinal",
        "aliases": ["celiac disease", "gluten allergy", "gluten intolerance", "coeliac", "celiac"],
        "nutrient_focus": ["fibre", "iron", "calcium", "vitamin D", "folate"],
        "awareness": (
            "Coeliac disease is an immune reaction to gluten that damages the small bowel. "
            "Gluten must be excluded strictly, and iron, calcium, vitamin D and folate are "
            "commonly monitored because absorption can be reduced before diagnosis."
        ),
        "questions": [
            "How should gluten-free eating change my fibre and B-vitamin intake?",
            "Which nutrients need monitoring with my coeliac disease?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/digestive-diseases/celiac-disease"
        ],
        "lab_links": [
            "hemoglobin_g_dl",
            "ferritin_ng_ml",
            "folate_ng_ml",
            "vitamin_d_ng_ml",
            "calcium_mg_dl",
        ],
        "guidance_confidence": "established",
    },
    {
        "slug": "lactose_intolerance",
        "label": "Lactose intolerance",
        "category": "gastrointestinal",
        "aliases": ["lactose problem", "milk sugar intolerance", "dairy intolerance"],
        "nutrient_focus": ["calcium", "protein", "vitamin D"],
        "awareness": (
            "Lactose intolerance is difficulty digesting milk sugar, causing bloating, wind or "
            "loose stools. The tolerated amount varies, and calcium and vitamin D need attention "
            "when dairy is reduced."
        ),
        "questions": [
            "How much lactose am I likely to tolerate per meal?",
            "How should I replace calcium if I cut dairy?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/digestive-diseases/lactose-intolerance"
        ],
        "lab_links": ["calcium_mg_dl", "vitamin_d_ng_ml"],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "gerd",
        "label": "Acid reflux (GERD)",
        "category": "gastrointestinal",
        "aliases": [
            "acid reflux",
            "gastro-oesophageal reflux",
            "gastroesophageal reflux",
            "heartburn",
            "acidity",
            "gerd",
        ],
        "nutrient_focus": ["fat", "energy", "caffeine"],
        "awareness": (
            "Gastro-oesophageal reflux disease is when stomach contents flow back into the "
            "food pipe, causing burning or a sour taste. Large, high-fat or late meals and "
            "some drinks commonly worsen symptoms."
        ),
        "questions": [
            "Which foods most provoke my reflux?",
            "How should meal timing change for my symptoms?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/digestive-diseases/acid-reflux-ger-gerd-adults"
        ],
        "lab_links": [],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "post_bariatric_surgery",
        "label": "Post-bariatric surgery",
        "category": "gastrointestinal",
        "aliases": [
            "bariatric surgery",
            "gastric bypass",
            "sleeve gastrectomy",
            "weight loss surgery",
            "gastric sleeve",
        ],
        "nutrient_focus": ["protein", "fibre", "sodium", "added sugars"],
        "awareness": (
            "After bariatric surgery the stomach holds much less, so portion size and eating "
            "pace change and protein is prioritised. Vitamins and minerals such as B12, iron, "
            "calcium and vitamin D are commonly monitored long term."
        ),
        "questions": [
            "What protein amount should I reach each day?",
            "Which supplements and monitoring does my surgery type need?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/weight-management/bariatric-surgery"
        ],
        "lab_links": ["albumin_g_dl", "vitamin_b12_pg_ml", "iron", "vitamin_d_ng_ml"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "hypothyroidism",
        "label": "Hypothyroidism",
        "category": "endocrine",
        "aliases": [
            "underactive thyroid",
            "low thyroid",
            "thyroid problem",
            "thyroid",
            "hypothyroid",
        ],
        "nutrient_focus": ["iodine", "selenium", "fibre", "energy"],
        "awareness": (
            "Hypothyroidism is an underactive thyroid, which slows metabolism and can cause "
            "fatigue and weight gain. Iodine is needed to make thyroid hormone, and very high "
            "fibre or soy loads can affect absorption timing of replacement hormone."
        ),
        "questions": [
            "How should I time my thyroid medicine against food and supplements?",
            "Should my iodine intake change?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/endocrine-diseases/hypothyroidism"
        ],
        "lab_links": ["tsh_miu_l", "t4_ug_dl", "t3_ng_dl"],
        "guidance_confidence": "established",
    },
    {
        "slug": "hyperthyroidism",
        "label": "Hyperthyroidism",
        "category": "endocrine",
        "aliases": [
            "overactive thyroid",
            "high thyroid",
            "thyrotoxicosis",
            "grave's disease",
            "graves disease",
        ],
        "nutrient_focus": ["iodine", "calcium", "energy", "protein"],
        "awareness": (
            "Hyperthyroidism is an overactive thyroid, which speeds metabolism and can cause "
            "weight loss and a rapid heartbeat. Iodine, calcium and adequate energy are "
            "commonly discussed because bone and nutrient needs change while it is active."
        ),
        "questions": [
            "Should I limit iodine-rich foods while my thyroid is overactive?",
            "Do my bones need checking with this condition?",
        ],
        "sources": [
            "https://www.niddk.nih.gov/health-information/endocrine-diseases/hyperthyroidism"
        ],
        "lab_links": ["tsh_miu_l", "t4_ug_dl", "calcium_mg_dl"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "pcos",
        "label": "Polycystic ovary syndrome",
        "category": "endocrine",
        "aliases": [
            "pcos",
            "polycystic ovary syndrome",
            "polycystic ovaries",
            "pcod",
            "hormone problem",
        ],
        "nutrient_focus": ["added sugars", "carbohydrate", "saturated fat", "fibre"],
        "awareness": (
            "Polycystic ovary syndrome affects hormones and ovulation and is often linked to "
            "insulin resistance. Free sugars and the quality of carbohydrate are commonly "
            "discussed, and weight change can improve both hormonal and metabolic markers."
        ),
        "questions": [
            "How does insulin resistance affect my PCOS?",
            "Which eating pattern would help my symptoms most?",
        ],
        "sources": ["https://www.nhs.uk/conditions/polycystic-ovary-syndrome/"],
        "lab_links": [
            "fasting_glucose_mg_dl",
            "hba1c_percent",
            "triglycerides_mg_dl",
            "hdl_cholesterol_mg_dl",
        ],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "iron_deficiency_anaemia",
        "label": "Iron-deficiency anaemia",
        "category": "haematologic",
        "aliases": [
            "anaemia",
            "anemia",
            "low haemoglobin",
            "low hemoglobin",
            "iron deficiency",
            "low iron",
            "khoon ki kami",
        ],
        "nutrient_focus": ["iron", "vitamin C", "folate", "vitamin B12"],
        "awareness": (
            "Iron-deficiency anaemia means low haemoglobin because iron stores are depleted. "
            "Iron-rich foods are best paired with a vitamin C source, because tea, coffee and "
            "calcium reduce iron absorption when taken at the same time."
        ),
        "questions": [
            "What is the cause of my iron deficiency?",
            "Which iron-rich foods and pairings suit me?",
        ],
        "sources": ["https://www.nhlbi.nih.gov/health/anemia/iron-deficiency-anemia"],
        "lab_links": ["hemoglobin_g_dl", "ferritin_ng_ml", "mcv_fl", "rbc_million_ul"],
        "guidance_confidence": "established",
    },
    {
        "slug": "vitamin_b12_deficiency",
        "label": "Vitamin B12 deficiency",
        "category": "haematologic",
        "aliases": ["b12 deficiency", "low b12", "cobalamin deficiency", "b12 problem"],
        "nutrient_focus": ["vitamin B12", "folate"],
        "awareness": (
            "Vitamin B12 deficiency can cause anaemia and nerve symptoms, and is more common "
            "with a vegetarian or vegan diet, gut disease or long-term acid-reducing medicine. "
            "B12 occurs naturally mainly in animal foods, with some fortified products."
        ),
        "questions": [
            "What caused my B12 deficiency?",
            "How should my B12 be monitored and replaced?",
        ],
        "sources": ["https://www.nhlbi.nih.gov/health/anemia/vitamin-b12-deficiency-anemia"],
        "lab_links": ["vitamin_b12_pg_ml", "hemoglobin_g_dl", "mcv_fl"],
        "guidance_confidence": "established",
    },
    {
        "slug": "folate_deficiency",
        "label": "Folate deficiency",
        "category": "haematologic",
        "aliases": [
            "folic acid deficiency",
            "low folate",
            "low folic acid",
            "vitamin b9 deficiency",
        ],
        "nutrient_focus": ["folate", "vitamin B12", "iron"],
        "awareness": (
            "Folate deficiency can cause anaemia and is especially important around pregnancy, "
            "because folate is needed for early fetal development. Leafy greens, pulses and "
            "fortified grains are the usual sources."
        ),
        "questions": [
            "Should my B12 be checked alongside folate?",
            "Which folate-rich foods fit my diet?",
        ],
        "sources": ["https://www.nhlbi.nih.gov/health/anemia/vitamin-b12-deficiency-anemia"],
        "lab_links": ["folate_ng_ml", "hemoglobin_g_dl", "mcv_fl"],
        "guidance_confidence": "established",
    },
    {
        "slug": "osteoporosis",
        "label": "Osteoporosis",
        "category": "musculoskeletal",
        "aliases": ["weak bones", "bone loss", "low bone density", "osteopenia", "bone problem"],
        "nutrient_focus": ["calcium", "vitamin D", "protein", "sodium"],
        "awareness": (
            "Osteoporosis is loss of bone strength that raises fracture risk. Calcium and "
            "vitamin D support bone, adequate protein helps maintain it, and very high sodium "
            "increases calcium loss."
        ),
        "questions": [
            "What calcium and vitamin D amounts suit my risk?",
            "How should protein and exercise support my bones?",
        ],
        "sources": ["https://www.niams.nih.gov/health-topics/osteoporosis"],
        "lab_links": ["calcium_mg_dl", "vitamin_d_ng_ml", "alp_u_l"],
        "guidance_confidence": "established",
    },
    {
        "slug": "vitamin_d_deficiency",
        "label": "Vitamin D deficiency",
        "category": "musculoskeletal",
        "aliases": [
            "low vitamin d",
            "vitamin d problem",
            "vitamin d insufficiency",
            "sunlight vitamin deficiency",
        ],
        "nutrient_focus": ["vitamin D", "calcium"],
        "awareness": (
            "Vitamin D deficiency means the level needed for bone and muscle health is not "
            "reached, often because of limited sun exposure or darker skin at higher latitudes. "
            "Fatty fish, egg yolk and fortified foods contribute, and supplementation is usually "
            "advised by a clinician."
        ),
        "questions": [
            "What level should I aim for, and how will it be rechecked?",
            "How much fortified food or supplement suits me?",
        ],
        "sources": ["https://www.nhs.uk/conditions/vitamin-d-deficiency/"],
        "lab_links": ["vitamin_d_ng_ml", "calcium_mg_dl"],
        "guidance_confidence": "established",
    },
    {
        "slug": "gestational_diabetes",
        "label": "Gestational diabetes",
        "category": "reproductive",
        "aliases": [
            "gdm",
            "diabetes in pregnancy",
            "pregnancy diabetes",
            "sugar problem in pregnancy",
        ],
        "nutrient_focus": ["carbohydrate", "added sugars", "fibre"],
        "awareness": (
            "Gestational diabetes is high blood glucose that first appears during pregnancy. "
            "Carbohydrate amount and distribution across the day matter for both the pregnancy "
            "and the baby's growth, and targets are set with the maternity team."
        ),
        "questions": [
            "What glucose targets apply to my pregnancy?",
            "How should carbohydrate be spread across my meals?",
        ],
        "sources": ["https://www.cdc.gov/diabetes/about/gestational-diabetes.html"],
        "lab_links": ["fasting_glucose_mg_dl", "hba1c_percent"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "pregnancy",
        "label": "Pregnancy",
        "category": "reproductive",
        "aliases": ["pregnant", "antenatal", "expecting", "gravid"],
        "nutrient_focus": ["folate", "iron", "calcium", "vitamin D", "protein", "energy"],
        "awareness": (
            "Pregnancy raises the need for several nutrients, especially folate in early "
            "pregnancy and iron later on. Energy needs rise only modestly, and food safety "
            "avoidances matter alongside nutrient adequacy."
        ),
        "questions": [
            "Which supplements does my stage of pregnancy need?",
            "How should I cover iron and calcium from food?",
        ],
        "sources": ["https://www.who.int/news-room/fact-sheets/detail/healthy-diet"],
        "lab_links": ["hemoglobin_g_dl", "ferritin_ng_ml", "folate_ng_ml", "vitamin_d_ng_ml"],
        "guidance_confidence": "clinician_only",
    },
    {
        "slug": "lactation",
        "label": "Breastfeeding (lactation)",
        "category": "reproductive",
        "aliases": ["breastfeeding", "nursing", "lactating", "feeding mother", "chestfeeding"],
        "nutrient_focus": ["energy", "protein", "calcium", "vitamin D", "iodine", "fluid"],
        "awareness": (
            "Breastfeeding uses extra energy and nutrients to make milk. Energy and fluid needs "
            "rise, and calcium, vitamin D and iodine are commonly discussed for the mother's "
            "own stores."
        ),
        "questions": [
            "How much extra energy and fluid do I need while feeding?",
            "Which nutrients should I keep taking in a supplement?",
        ],
        "sources": [
            "https://www.cdc.gov/breastfeeding-special-circumstances/hcp/diet-micronutrients/index.html"
        ],
        "lab_links": ["hemoglobin_g_dl", "calcium_mg_dl", "vitamin_d_ng_ml"],
        "guidance_confidence": "general_wellbeing",
    },
    {
        "slug": "epilepsy",
        "label": "Epilepsy",
        "category": "neuro/other",
        "aliases": ["seizures", "fits", "seizure disorder", "mirgi"],
        "nutrient_focus": ["calcium", "vitamin D", "folate", "energy"],
        "awareness": (
            "Epilepsy is a tendency to recurrent seizures, usually managed with medicines. Some "
            "anti-seizure medicines affect bone strength and folate, so calcium, vitamin D and "
            "folate are commonly monitored, and ketogenic diets are used only under close "
            "clinical supervision."
        ),
        "questions": [
            "Do my medicines affect calcium, vitamin D or folate for me?",
            "Would any diet change interact with my treatment?",
        ],
        "sources": ["https://www.nhs.uk/conditions/epilepsy/"],
        "lab_links": ["calcium_mg_dl", "vitamin_d_ng_ml", "folate_ng_ml"],
        "guidance_confidence": "clinician_only",
    },
]

# --- Awareness packs (assessment engine) -------------------------------------------------
#
# A pack is the deterministic awareness wording the assessment engine attaches to one
# record for a recognised condition. A pack either reads one food nutrient value (and so
# also has an honest "unknown" counterpart) or is a fixed nutrient-adequacy note. Every
# pack names the nutrient it concerns.

AWARENESS_PACKS = {
    "type_2_diabetes": {
        "code": "condition_carbohydrate_awareness",
        "unknown_code": "condition_carbohydrate_unknown",
        "nutrient_key": "carbohydrates_g",
        "unit": "g",
        "title": "Carbohydrate: check the portion",
        "known_detail": (
            "Total carbohydrate on the label: {amount}. Sugar-free wording does not "
            "establish that this product fits the serving you will eat."
        ),
        "unknown_detail": (
            "You recorded diabetes, but the total carbohydrate value is missing, so this "
            "serving cannot be checked."
        ),
        "message": "Check total carbohydrate against your serving; sugar-free wording does not settle it.",
        "unknown_title": "Carbohydrate: no value to check",
        "unknown_message": "No total carbohydrate value is available, so this record cannot be checked.",
        "next_step": (
            "Check the total carbohydrate figure against the serving you will eat, not the "
            "sugar-free claim."
        ),
        "unknown_next_step": "Find the total carbohydrate value on the nutrition panel.",
        "affects": ["condition:diabetes", "nutrient:carbohydrates_g"],
        "kind": "carbohydrate_awareness",
    },
    "hypertension": {
        "code": "condition_sodium_awareness",
        "unknown_code": "condition_sodium_unknown",
        "nutrient_key": "sodium_mg",
        "unit": "mg",
        "unknown_amount": "unknown",
        "title": "Sodium: compare with your limit",
        "known_detail": (
            "Sodium on the label: {amount}. Any sodium limit you recorded still applies "
            "to the serving you actually eat."
        ),
        "unknown_detail": (
            "You recorded hypertension, but the sodium value is missing, so this serving "
            "cannot be checked."
        ),
        "message": "Compare the sodium figure with any limit you recorded.",
        "unknown_title": "Sodium: no value to check",
        "unknown_message": "No sodium value is available, so this record cannot be checked.",
        "next_step": (
            "Compare this sodium figure with the limit you recorded, or ask what daily limit "
            "fits you."
        ),
        "unknown_next_step": "Find the sodium value on the nutrition panel.",
        "affects": ["condition:hypertension", "nutrient:sodium_mg"],
        "kind": "sodium_awareness",
    },
    "ckd": {
        "code": "condition_ckd_limits_only",
        "unknown_code": None,
        "nutrient_key": None,
        "unit": "",
        "title": "CKD: only recorded limits are checked",
        "known_detail": (
            "Kidney nutrient limits depend on your own clinical advice. This check therefore "
            "covers just the limits, allergies and exclusions you entered yourself."
        ),
        "unknown_detail": None,
        "message": "CKD limits are individual, so this check uses only the restrictions you entered.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": None,
        "unknown_next_step": None,
        "affects": ["condition:ckd"],
        "kind": "individual_guidance",
    },
    "prediabetes": {
        "code": "condition_prediabetes_awareness",
        "unknown_code": None,
        "nutrient_key": "sugars_g",
        "unit": None,
        "title": "Prediabetes: added and free sugars",
        "known_detail": (
            "Total sugars on the label: {amount}. That figure counts the natural sugars in milk "
            "and fruit, so the added and free kinds are the ones to limit when blood sugar "
            "is managed."
        ),
        "unknown_detail": None,
        "message": "Total sugars include natural milk and fruit sugars; added and free sugars are the ones to watch.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": (
            "Compare the added and free sugars with the target you recorded, or ask which "
            "target applies to you."
        ),
        "unknown_next_step": None,
        "affects": ["condition:prediabetes", "nutrient:sugars_g"],
        "kind": "sugar_awareness",
    },
    "dyslipidaemia": {
        "code": "condition_dyslipidaemia_awareness",
        "unknown_code": None,
        "nutrient_key": "saturated_fat_g",
        "unit": None,
        "title": "Saturated fat: check the amount",
        "known_detail": (
            "Saturated fat on the label: {amount}. This fat raises LDL cholesterol, so "
            "compare it with the ceiling you recorded if you set one."
        ),
        "unknown_detail": None,
        "message": "Saturated fat raises LDL cholesterol; compare it with your recorded ceiling.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Compare the saturated fat figure with your recorded ceiling, or ask which ceiling fits you.",
        "unknown_next_step": None,
        "affects": ["condition:dyslipidaemia", "nutrient:saturated_fat_g"],
        "kind": "saturated_fat_awareness",
    },
    "gout": {
        "code": "condition_gout_awareness",
        "unknown_code": None,
        "nutrient_key": "sugars_g",
        "unit": None,
        "title": "Gout: fructose and purines",
        "known_detail": (
            "Total sugars on the label: {amount}. Fructose-sweetened food and drink raise "
            "uric acid, so check the ingredient list too for purine-rich items such as "
            "shellfish, liver and beer."
        ),
        "unknown_detail": None,
        "message": "Sugars, purine-rich ingredients and alcohol all matter for uric acid.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Compare the sugars and any purine-rich ingredients with your uric acid target.",
        "unknown_next_step": None,
        "affects": ["condition:gout", "nutrient:sugars_g"],
        "kind": "sugar_awareness",
    },
    "nafld": {
        "code": "condition_nafld_awareness",
        "unknown_code": None,
        "nutrient_key": "sugars_g",
        "unit": None,
        "title": "Fatty liver: sugars and saturated fat",
        "known_detail": (
            "Total sugars on the label: {amount}. Added sugars, saturated fat and total "
            "energy are the food factors usually discussed for liver fat, so review them "
            "together."
        ),
        "unknown_detail": None,
        "message": "Added sugars and saturated fat are the food factors usually discussed for liver fat.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Compare the added sugars and saturated fat with the changes you agreed with your clinician.",
        "unknown_next_step": None,
        "affects": ["condition:nafld", "nutrient:sugars_g", "nutrient:saturated_fat_g"],
        "kind": "sugar_awareness",
    },
    "pcos": {
        "code": "condition_pcos_awareness",
        "unknown_code": None,
        "nutrient_key": "sugars_g",
        "unit": None,
        "title": "PCOS: free sugars and saturated fat",
        "known_detail": (
            "Total sugars on the label: {amount}. Where insulin resistance is part of "
            "PCOS, free sugars and saturated fat are the two usually reduced."
        ),
        "unknown_detail": None,
        "message": "Free sugars and saturated fat are the usual targets when insulin resistance is present.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Compare the free sugars and saturated fat with the plan you recorded.",
        "unknown_next_step": None,
        "affects": ["condition:pcos", "nutrient:sugars_g", "nutrient:saturated_fat_g"],
        "kind": "sugar_awareness",
    },
    "iron_deficiency_anaemia": {
        "code": "condition_anaemia_awareness",
        "unknown_code": None,
        "nutrient_key": None,
        "unit": "",
        "title": "Iron: pair it with vitamin C",
        "known_detail": (
            "This record carries no iron value, so no iron number is shown. Pair iron-rich "
            "ingredients with a vitamin C source, and keep tea, coffee and calcium away from "
            "that meal."
        ),
        "unknown_detail": None,
        "message": "Pair iron-rich ingredients with vitamin C; tea, coffee and calcium work against it.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Check whether this product names an iron-rich ingredient and a vitamin C source.",
        "unknown_next_step": None,
        "affects": ["condition:iron_deficiency_anaemia", "nutrient:iron"],
        "kind": "iron_pairing",
    },
    "vitamin_b12_deficiency": {
        "code": "condition_b12_awareness",
        "unknown_code": None,
        "nutrient_key": None,
        "unit": "",
        "title": "B12: check the product covers it",
        "known_detail": (
            "This record carries no B12 value, so no number is shown. B12 occurs naturally "
            "mainly in animal foods, with some fortified products."
        ),
        "unknown_detail": None,
        "message": "Check B12 sources; no numeric target comes from a food record.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Check the ingredients for B12-fortified items, or ask whether a supplement is needed.",
        "unknown_next_step": None,
        "affects": ["condition:vitamin_b12_deficiency", "nutrient:vitamin_b12"],
        "kind": "adequacy_awareness",
    },
    "vitamin_d_deficiency": {
        "code": "condition_vitamin_d_awareness",
        "unknown_code": None,
        "nutrient_key": None,
        "unit": "",
        "title": "Vitamin D: check the product covers it",
        "known_detail": (
            "This record carries no vitamin D value, so no number is shown. Fatty fish, egg "
            "yolk and fortified foods contribute, and supplements are usually led by your "
            "clinician."
        ),
        "unknown_detail": None,
        "message": "Check vitamin D sources; no numeric target comes from a food record.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Check for vitamin D-fortified items or oily fish, and ask which supplement amount applies to you.",
        "unknown_next_step": None,
        "affects": ["condition:vitamin_d_deficiency", "nutrient:vitamin_d"],
        "kind": "adequacy_awareness",
    },
    "hypothyroidism": {
        "code": "condition_hypothyroidism_awareness",
        "unknown_code": None,
        "nutrient_key": None,
        "unit": "",
        "title": "Hypothyroidism: iodine and medicine timing",
        "known_detail": (
            "This record carries no iodine value, so no number is shown. Keep food and "
            "supplements away from the times you take replacement hormone."
        ),
        "unknown_detail": None,
        "message": "Iodine matters, and food timing matters around your thyroid medicine.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Ask about iodine intake and how long to leave between food and your thyroid medicine.",
        "unknown_next_step": None,
        "affects": ["condition:hypothyroidism", "nutrient:iodine"],
        "kind": "adequacy_awareness",
    },
    "hyperthyroidism": {
        "code": "condition_hyperthyroidism_awareness",
        "unknown_code": None,
        "nutrient_key": None,
        "unit": "",
        "title": "Hyperthyroidism: iodine and calcium",
        "known_detail": (
            "This record carries no iodine or calcium values, so no numbers are shown. "
            "Nutrient and bone needs change while the thyroid is overactive."
        ),
        "unknown_detail": None,
        "message": "Iodine and calcium matter; needs change while the thyroid is overactive.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Ask whether iodine-rich foods and bone checks apply to you.",
        "unknown_next_step": None,
        "affects": ["condition:hyperthyroidism", "nutrient:iodine", "nutrient:calcium"],
        "kind": "adequacy_awareness",
    },
    "osteoporosis": {
        "code": "condition_osteoporosis_awareness",
        "unknown_code": None,
        "nutrient_key": "calcium_mg",
        "unit": None,
        "title": "Osteoporosis: calcium and sodium",
        "known_detail": (
            "Calcium on the label: {amount}. Calcium and vitamin D support bone, and a "
            "very high sodium intake increases calcium loss."
        ),
        "unknown_detail": None,
        "message": "Calcium and vitamin D support bone; high sodium increases calcium loss.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Check whether this product names a calcium-rich ingredient, and keep sodium portions modest.",
        "unknown_next_step": None,
        "affects": ["condition:osteoporosis", "nutrient:calcium"],
        "kind": "adequacy_awareness",
    },
    "pregnancy": {
        "code": "condition_pregnancy_awareness",
        "unknown_code": None,
        "nutrient_key": None,
        "unit": "",
        "title": "Pregnancy: folate, iron and food safety",
        "known_detail": (
            "This record carries no folate or iron values, so no numbers are shown. Folate "
            "matters most early and iron later, and food-safety advice is set with your "
            "maternity team."
        ),
        "unknown_detail": None,
        "message": "Folate early and iron later; food-safety advice comes from your maternity team.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Ask which supplements and iron sources fit your stage of pregnancy.",
        "unknown_next_step": None,
        "affects": ["condition:pregnancy", "nutrient:folate", "nutrient:iron"],
        "kind": "adequacy_awareness",
    },
    "heart_failure": {
        "code": "condition_heart_failure_awareness",
        "unknown_code": None,
        "nutrient_key": "sodium_mg",
        "unit": None,
        "title": "Heart failure: sodium and fluid limits",
        "known_detail": (
            "Sodium on the label: {amount}. Sodium and sometimes fluid limits are set for "
            "you individually, and potassium advice depends on the medicines you take."
        ),
        "unknown_detail": None,
        "message": "Sodium and fluid limits are individual and depend on your medicines.",
        "unknown_title": None,
        "unknown_message": None,
        "next_step": "Compare this sodium figure with the limit you were given, and ask how fluid fits in.",
        "unknown_next_step": None,
        "affects": ["condition:heart_failure", "nutrient:sodium_mg"],
        "kind": "sodium_awareness",
    },
}

# --- Indexes and helpers -----------------------------------------------------------------


def _index():
    by_slug = {}
    by_alias = {}
    for entry in CONDITIONS:
        by_slug[entry["slug"]] = entry
        for value in [entry["slug"], entry["label"], *entry["aliases"]]:
            by_alias[value.casefold()] = entry["slug"]
    return by_slug, by_alias


BY_SLUG, BY_ALIAS = _index()


def resolve_condition(text: str) -> str | None:
    """Resolve one profile condition string to a slug, or ``None`` when unmatched.

    Matching is exact after casefold + trim, so nothing is force-mapped onto a guess.
    """
    if not isinstance(text, str):
        return None
    return BY_ALIAS.get(text.strip().casefold())


def resolve_conditions(values) -> tuple[list[str], list[str]]:
    """Split profile conditions into (recognised slugs, unrecognised raw strings).

    Order is preserved and duplicates collapse, so the acknowledged list stays stable.
    """
    recognised: list[str] = []
    unrecognised: list[str] = []
    for value in values:
        slug = resolve_condition(value)
        if slug is None:
            if value not in unrecognised:
                unrecognised.append(value)
        elif slug not in recognised:
            recognised.append(slug)
    return recognised, unrecognised


def condition_info(slug: str) -> dict | None:
    entry = BY_SLUG.get(slug)
    return dict(entry) if entry else None


def registry_payload() -> dict:
    """The frozen ``ConditionRegistry`` shape for ``GET /api/conditions``."""
    return {
        "version": CONDITION_REGISTRY_VERSION,
        "conditions": [dict(entry) for entry in CONDITIONS],
        "categories": list(CATEGORIES),
        "coverage": (
            "Awareness and intake-planning vocabulary only. A selected condition never "
            "activates a complete clinical diet and never sets a limit by itself."
        ),
        "notes": [
            "Matching is exact after casefold and trim; unmatched conditions are reported, "
            "never silently mapped.",
            "Guidance confidence marks how much of the content is established versus needing "
            "individual clinical advice.",
        ],
    }


def awareness_codes() -> set[str]:
    """Every finding code the awareness packs can emit.

    Exposed so tests can assert the code contract without hardcoding the list: a new
    condition in the registry extends this set, and the stability test stays honest.
    """
    codes = {"condition_pack_unsupported"}
    for pack in AWARENESS_PACKS.values():
        codes.add(pack["code"])
        if pack.get("unknown_code"):
            codes.add(pack["unknown_code"])
    return codes
