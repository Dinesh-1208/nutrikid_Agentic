# Verified Technical Data Pack: NutriBite / KidsNutriBite

Audit date: 2026-10-02. This is a repository evidence inventory, not paper prose. The audit covered `C:/Users/DINESH/Projects/nutrikid_Agentic-main`, `C:/Users/DINESH/Projects/food_analysis_model-main`, and the NutriBite application at `C:/Users/DINESH/Projects/nutrikid/NutriBite`. The research prototype, application, and food-model notebook are separate artifacts and must not be described as one fully integrated deployed stack without qualification.

Evidence convention: code/config/data artifacts establish current behavior; research notes establish proposals or recorded analysis, not execution; statements marked **NOT FOUND / NOT VERIFIED** were not present in the checked repositories or cannot be derived from saved artifacts. No source code was changed.

## 1. End-to-End System Flow

### A. Text nutrition query (KidsNutriBite research prototype)

`CLI --ask text + CLI profile flags/defaults` → `main.py` → `KidsNutriRetriever.retrieve(query, top_k=5)` → `RetrievalService` (query embedding, semantic cache, FAISS and BM25, score fusion, metadata filter, cross-encoder, parent expansion) → keyword router in `main.py` → optional `DietPlanner.generate_meal_plan(profile)` → `generate_qa_prompt` or `generate_llm_prompt` → `KidsNutriLLMClient.generate_response(..., qwen_local)` → response text and latency.

Evidence: `main.py`, `rag/retriever.py`, `rag/services/retrieval_service.py`, `llm/prompt_templates.py`, `llm/llm_client.py`. The CLI query branch uses hardcoded profile defaults where flags are absent; it does not extract age/allergy/etc. from free text.

### B. Food image input (NutriBite app)

`uploaded image + optional saved user corrections` → `backend/controllers/meal.controller.js` multipart handler → POST to `FOOD_RECOGNITION_SERVICE_URL` (default `http://localhost:8001`) `/api/food-recognition` (1.5 s timeout) → returned `foods`, `confidence_scores`, optional `portion_estimates` → `calculateFoodNutrition(food, quantity)` → meal analysis/log workflow. If the local request fails or returns no result, the controller sends the image to Gemini 2.5 Flash multimodal with a JSON-only prompt requesting detected foods, confidence, an alternate candidate, portion estimate and nutrition. A confidence/margin rule produces auto-accept, confirmation, or manual-entry decisions.

The repository contains the YOLO training notebook separately, but the configured HTTP microservice implementation and its model weights are **NOT FOUND / NOT VERIFIED** in the checked app service folders. The fallback Gemini path is executable backend code; it is not evidence that visual portion estimates or nutrition values are calibrated/validated. The backend also has a debug endpoint `/api/debug-food-analysis`. Evidence: `NutriBite/backend/controllers/meal.controller.js`; `food_analysis_model-main/yolo8n.ipynb`.

### C. Child-profile/context query (NutriBite app)

`authenticated POST /api/ai/ask {query/question, profileId, conversationId, history}` → `askNutriGuide` verifies the child belongs to the authenticated parent → `ConversationManager` gets/creates a thread and asynchronously extracts memory → `AgentOrchestrator.processAgentWorkflow` → substring intent classifier → `ChildContextEngine.buildContext` queries profile and intent-specific MongoDB records → fixed tool mapping and backend tool calls (parallel `Promise.all`) → tool-output check → AI-service request or deterministic fallback → pediatric disclaimer → response and saved conversation.

Evidence: `NutriBite/backend/routes/ai.routes.js`, `backend/controllers/ai.controller.js`, `backend/services/agentOrchestrator.service.js`, `backend/services/childContextEngine.js`, `backend/services/agentTools.service.js`, `backend/services/conversationManager.service.js`.

### D. Doctor/clinical interaction (NutriBite app)

`doctor/parent UI action` → protected appointment, consultation, prescription, growth, access, or escalation route/controller → role/ownership middleware → corresponding Mongoose model/service → MongoDB → response to role-specific frontend page. For an AI doctor-preparation query, the AI endpoint uses the same agent workflow; context queries recent prescriptions and consultation notes and plans `tool_get_doctor_summary` plus `tool_analyze_growth_velocity` for doctor/appointment/escalation intents.

Evidence: `backend/routes/{doctor,appointment,consultation,growth,escalation}.routes.js`, matching controllers, `middlewares/{auth,role,ownership,doctor}.middleware.js`, models `Prescription`, `ConsultationRequest`, `GrowthRecord`, and `agentOrchestrator.service.js`. No separately verified clinical AI model is present.

### E. Agentic/tool workflow (NutriBite app)

`AI request` → input trim/truncate → deterministic `IntentClassifier.classify` → context gathering → `planToolsForIntent` fixed switch → `executePlannedTools` fixed switch, concurrent when multiple tools are mapped → `verifyToolOutputs` (currently allergy-tool result check) → attempt POST to `AI_SERVICE_URL/ask` with child context, history, goals/allergies, and model string `nvidia_deepseek` → on failure use deterministic tool-result formatter → follow-ups/saveable plan → disclaimer and audit log.

This is an implemented, rule-routed tool workflow. It does not establish LLM-selected tools, iterative tool-call loops, MCP, or autonomous planning. The actual `/ask` AI-service implementation is not in the checked out app AI service directories, so the remote integration’s internal behavior is **NOT FOUND / NOT VERIFIED**.

## 2. User / Application Layer

Frontend: Next.js App Router and React. Package versions in `NutriBite/frontend/package.json`: Next `^16.2.4`, React/React DOM `19.2.4`; Lucide React is installed. Backend package: Express `^4.18.3`, Node ES modules. These app versions are distinct from the Python research prototype.

| Module / user capability | Verified behavior | Evidence paths |
|---|---|---|
| Parent | Parent dashboard, child/profile management, appointments, consultations, meal and nutrition views, doctor access, AI copilot routes | `frontend/src/app/parent/**`, `frontend/src/react_pages/parent/**`, `backend/controllers/parent.controller.js`, `profile.controller.js`, `ai.controller.js` |
| Child / Kids mode | Kids dashboard/layout and child dashboard route | `frontend/src/app/kids/**`, `frontend/src/react_pages/kids/KidsDashboard.jsx`, `frontend/src/layouts/KidsLayout.jsx` |
| Doctor | Doctor dashboard, analytics, appointments, patient details, profile/resources | `frontend/src/app/doctor/**`, `frontend/src/react_pages/doctor/**`, `backend/controllers/doctor.controller.js` |
| Dietitian | Dashboard, case detail and profile | `frontend/src/app/dietitian/**`, `frontend/src/react_pages/dietitian/**` |
| Authentication / RBAC | JWT bearer authentication; protected routes; route-level `authorize(...roles)` and ownership checks exist | `backend/middlewares/auth.middleware.js`, `role.middleware.js`, `ownership.middleware.js`, `backend/controllers/auth.controller.js`, `frontend/src/hooks/useAuth.js` |
| AI chatbot / conversation history | Protected ask, list/create/read/delete conversations and retrieve stored memory | `backend/routes/ai.routes.js`, `backend/controllers/ai.controller.js`, `Conversation.model.js`, `ConversationMemory.model.js` |
| Food image input | Upload to external/configured recognition service; backend uses returned foods and quantities to calculate nutrition | `backend/controllers/meal.controller.js`; actual recognition server **NOT FOUND / NOT VERIFIED** |
| Growth tracking | Parent/doctor growth records, growth dashboard/analytics and context for growth intents | `backend/controllers/growth.controller.js`, `GrowthRecord.model.js`, `frontend/src/app/parent/child/[id]/wellness/page.js`, doctor pages |
| Meal logging | Meal records and macros; meal controller has image analysis and meal log endpoints | `backend/controllers/meal.controller.js`, `MealLog.model.js`, `frontend/src/api/meal.api.js` |
| Clinical | Consultation requests, prescriptions, clinical briefs, escalation, appointments, doctor access | matching `backend/controllers/*`, `backend/models/{ConsultationRequest,Prescription,ClinicalBrief,Escalation,Appointment,DoctorAccess}.model.js` |
| Admin | Admin dashboard/users/doctors/parents/security/activity | `frontend/src/app/admin/**`, `backend/controllers/admin.controller.js` |

“Parent functions” and “Child functions” in this pack refer to implemented role-specific application routes/pages, not biological or clinical capabilities. Exact route-by-route behavior is in the linked modules above.

## 3. Backend / Services

NutriBite app backend: Node.js runtime, Express API, Mongoose/MongoDB; `server.js` connects database, starts HTTP server and Socket.IO signaling. `backend/app.js` mounts API routers. Database URL is environment-configured; exact deployment/runtime version, database host, production configuration: **NOT FOUND / NOT VERIFIED**.

Frontend-to-AI trace: frontend `src/api/ai.api.js` → `/api/ai/ask` → `routes/ai.routes.js` with `protect` → `controllers/ai.controller.js::askNutriGuide` → `AgentOrchestrator.processAgentWorkflow` → `ChildContextEngine`/`AgentTools` → `axios.post(AI_SERVICE_URL + '/ask')` → external AI service response or deterministic formatter fallback.

Other application services include `aiOrchestrator.service.js` (a second custom RAG-provider/fallback orchestration path), `childContextEngine.js`, `mealPlannerEngine.js`, `nutritionService.js`, `nutritionIntelligenceEngine.js`, `nutrientGapEngine.js`, `doctor.service.js`, `conversationManager.service.js`, and `copilotWorkflows.service.js`. Exact service/function names are in those modules. The external Python/AI service internals are **NOT FOUND / NOT VERIFIED**; the checked `ai-service` folder has a PDF preprocessing notebook and datasets, while `ai-service-v2` has datasets and static assets but no checked-in Python API entrypoint.

KidsNutriBite research backend is a local Python CLI (`main.py`), not a web API. Its HTTP framework/runtime: not applicable for that repository; a Python minor version is **NOT FOUND / NOT VERIFIED** in committed config.

## 4. Agentic AI Architecture

Current app workflow stages and evidence (`NutriBite/backend/services/agentOrchestrator.service.js`):

| Stage | Input → processing → output | Status |
|---|---|---|
| Understand | Query → lowercase substring rules in `IntentClassifier.classify` → one enum intent | Implemented, deterministic rules |
| Observe / context | profileId, parentId, intent → Mongo profile plus relevant meal/growth/activity/sleep/clinical records → childContext | Implemented; defaults/hardcoded fallbacks also occur |
| Plan | intent and query → fixed switch `planToolsForIntent` → tool-name array | Implemented; no model planning |
| Act | names/context/query → fixed dispatch to `AgentTools` → tool result objects | Implemented; mapped tools may run concurrently |
| Verify | results → `verifyToolOutputs` checks unsafe allergy tool verdict → `{safe, alert}` | Partial; return value is computed but no general output validation is shown before synthesis |
| Synthesize | query/context/tool results/history → prompt construction; request AI service `/ask`; on error deterministic formatter | Implemented app caller; AI endpoint implementation not present here |
| Follow-up | intent/context/query → follow-up prompts and optional saveable diet plan → response | Implemented |

Capability check: MCP client/server **NOT FOUND / NOT VERIFIED**; named MCP layer **NOT FOUND / NOT VERIFIED**; multiple fixed backend tools **implemented**; deterministic intent-based tool selection **implemented**; autonomous LLM tool selection **NOT FOUND / NOT VERIFIED**; iterative tool calls **NOT FOUND / NOT VERIFIED**; query decomposition **NOT FOUND / NOT VERIFIED**; retry/feedback loop for tool planning **NOT FOUND / NOT VERIFIED**; confidence thresholding **NOT FOUND / NOT VERIFIED**; LLM multi-step planning **NOT FOUND / NOT VERIFIED**; aggregation of multiple mapped tool outputs into a prompt **implemented**; LLM response call at external `/ask` boundary is attempted, but internals **NOT FOUND / NOT VERIFIED**. Do not call this a multi-agent system based on the code inspected. Do not identify the Python CLI prototype as Agentic RAG; its flow is a fixed RAG/planner/LLM pipeline.

## 5. Agentic Tools

App executable orchestrator tools (not MCP tools): `tool_calculate_nutrient_gaps`, `tool_generate_pediatric_meal_plan`, `tool_check_food_allergy_safety`, `tool_analyze_growth_velocity`, `tool_generate_grocery_list`, `tool_get_doctor_summary`, `tool_get_hydration_lifestyle_stats`. They take object arguments, mainly `{childContext}`, with `{foodItem, childContext}` for allergy safety and `{childContext, slot?}` for meal planning. Their return shapes are JavaScript objects containing `toolName` plus tool-specific values such as nutrient gaps, schedule, safe/verdict, growth summary, grocery list, clinical summary, or hydration stats. Exact property-by-property schemas are **NOT FOUND / NOT VERIFIED** as a shared formal schema; inspect method bodies in `NutriBite/backend/services/agentTools.service.js`.

| Requested tool | Group | Finding / status |
|---|---|---|
| `rag_search` | Knowledge / Retrieval | Exact named tool **NOT FOUND / NOT VERIFIED**. Research prototype does implement RAG retrieval via `KidsNutriRetriever.retrieve(query, top_k, metadata_filters, mode)` in `rag/retriever.py`; this is not an app AgentTools MCP tool. |
| `web_search` | Knowledge / Retrieval | **NOT FOUND / NOT VERIFIED** as a callable tool in inspected code. |
| `update_rag` | Knowledge / Retrieval | **NOT FOUND / NOT VERIFIED** as runtime tool; `rag/indexer.py::build_index` rebuilds local FAISS artifacts. |
| `nutrition_analysis` | Nutrition / Planning | Exact name **NOT FOUND / NOT VERIFIED**. App has nutrient gap and nutrition helper tools; research prototype has deterministic `DietPlanner`. |
| `growth_analysis` | Growth / Clinical | Exact name **NOT FOUND / NOT VERIFIED**. Equivalent app method `tool_analyze_growth_velocity({childContext})` is implemented. |
| `meal_planner` | Nutrition / Planning | Exact name **NOT FOUND / NOT VERIFIED**. Equivalent app method `tool_generate_pediatric_meal_plan` and other planner methods are implemented. |
| `food_recognition` | Vision / Food | As an app backend HTTP route client it exists at `/api/food-recognition`; as a tool registered in `AgentTools` **NOT FOUND / NOT VERIFIED**. Model server source is missing from checked app folders. |
| `update_ner` | Adaptive NLP | **NOT FOUND / NOT VERIFIED**. No NER runtime or update tool found. |

Additional implemented app helpers in `AgentTools`: child/profile/meal-history queries, daily/weekly nutrition summary, nutrition trends, growth/hydration history, doctor recommendations, food search/nutrition/comparison/safety/allergen conflict/substitution, daily/weekly meal planning, school lunch plan, grocery list, nutrient-gap, variety, and progress analysis. Tool caller: `AgentOrchestrator` and `CopilotWorkflows`; implementations: `backend/services/agentTools.service.js`.

## 6. Datasets and Knowledge Base

### KidsNutriBite research repository

| Dataset | Location / record count | Schema and purpose |
|---|---|---|
| RAG corpus | `data/rag/rag_data.json`, 558 records | Each record has `id`, `text`, `metadata`. Metadata keys vary. 147 distinct `metadata.type` values; common counts include condition=133, general=57, food=56, nutritional_biochemistry=26, general_knowledge=21, goal=15, protocol=14, growth_metric=12. Tags occur in 402 records; distinct tags=888. `condition` key on 94, `source` on 63, `food_name` on 13, `goal` on 13 (repository research audit `docs/research/00_CURRENT_ARCHITECTURE.md`). Text lengths mean 133.9 chars, max 567 as recorded by that audit. No separate validated counts by food/condition/goal source entities; **NOT FOUND / NOT VERIFIED**. |
| Structured food table | `data/structured_db/foods.json`, 99 records | Union of fields: `food_id`, `food_name`, `category`, `categories`, `energy_kcal_per_100g`, `energy_kcal_100g`, `energy_kcal_100ml`, `energy_kcal_1000ml`, `nutrients_per_100g`, `nutrients_per_100ml`, `nutrients_per_ml`, `protein_g`, `protein_g_100ml`, `fat_g`, `carbs_g`, `iron_mg`, `portion_unit`, `portion_energy_kcal`, `portion_protein_g`, `age_min`, `allergy_tags`, `meal_types`, `tags`, `description`, `benefits`, `clinical_*`, `digestibility_*`, and optional composition/preparation/usage fields. Categories include protein, infant_food, vegetable, fruit, dairy, cereal, plus specialized clinical categories and five blank categories. Meal type values: afternoon, all, breakfast, dinner, evening, lunch, mid_morning, morning, snack. |
| Conditions | `data/structured_db/conditions.json`, 173 records | Union schema includes `condition_name`, `required_tags`, `avoid_tags`, `meal_pattern`, plus heterogeneous clinical description/diagnosis/symptom/management/threshold/protocol fields. |
| Goals | `data/structured_db/goals.json`, 148 records | Union schema includes `goal_name`, `required_tags`, `avoid_tags`, `meal_frequency`, plus heterogeneous target/formula/age/nutrient/strategy fields. |
| Allergies | `data/structured_db/allergies.json`, 15 records | `allergy`, `avoid_foods`, `severity`, `description`, `preferred_alternative`, `symptoms`, `triggers`; duplicate allergy names occur in the source. |
| Evaluation gold data | `docs/evaluation/phase2c_gold_annotations.json`, 49 cases | Each case includes question/category/subcategory/age_group/knowledge_area/source_scope/profile/relevant_chunk_ids/gold_facts/reference_answer/safety_ground_truth/annotation_status/annotation_notes. All 49 have `annotation_status=ANNOTATED`; 41 have non-empty RAG relevant IDs; 22 have profile data; 20 have non-null safety ground truth and 29 are null. Separate `docs/evaluation/phase2d_ai_safety_ground_truth.json` contains 20 case records. Category counts: general nutrition/nutrients 9, age-specific 9, allergies 10, pediatric conditions 9, food safety 6, growth/reference data 6. |

### NutriBite application records

MongoDB collections are represented by Mongoose models, not a checked-in populated research dataset. Record totals: **NOT FOUND / NOT VERIFIED**. Schemas include: Profile (identity/demographic, dietary preferences, allergies, health conditions, goals, wellness data and doctor assignment fields); MealLog (dated meal slots/items, nutrients/macros, completion and image fields); GrowthRecord (height, weight, BMI/date/source); Prescription (doctor, diagnosis, instructions, notes, date/checkup); ConsultationRequest and ClinicalBrief (clinical notes, care/score fields); Conversation/Memory/ChatLog. Exact complete fields are in model files; sample population sizes **NOT FOUND / NOT VERIFIED**.

Application file evidence: `NutriBite/backend/models/Profile.model.js`, `MealLog.model.js`, `GrowthRecord.model.js`, `Prescription.model.js`, `ConsultationRequest.model.js`, `ClinicalBrief.model.js`, `Conversation.model.js`, `ConversationMemory.model.js`.

## 7. Feature Engineering / Transformations

| Feature | Verified implementation and consumer | Status |
|---|---|---|
| Missing weight estimate | In planner: age<1: `months=max(1,age*12)`, weight=`(months+9)/2`; 1–6 years: `2*age+8`; 7–12: `(7*age-5)/2`; otherwise `3*age`. Used in calorie planner. | Implemented |
| Age normalization/band | Planner consumes `age` as numeric and compares against each food `age_min`; no age-unit conversion/bands beyond estimate branch. | Partial; months/years are assumed in comments, no robust normalization |
| Numeric food cleaning | Empty/invalid strings to 0; list first item to float; portion energy/protein may infer per-100g values from `portion_unit`; age_min defaults to 1 and casts to int. | Implemented |
| Required/avoid tags | Union of condition/goal tags, food excluded if any tag matches `avoid_tags`; `required_tags` only affect ranking (+5 per matching tag). | Implemented |
| Allergy normalization/exclusion | Lowercase, spaces→underscores for exclusion foods; direct food/category compare; checks `allergy_tags`; partial checks for “nut” in allergen+food name and “milk” in allergen+food/dairy category. | Implemented, rule coverage/data matching is partial |
| Eligible food set | Age, allergen and avoid-tag filters; meal_types or `all` selects candidates, category fallback if none. | Implemented |
| Query normalization / intent | Research prototype keyword substring match on query for plan/diet/meal/menu; app lowercases and performs ordered substring intent classification. | Implemented; no NER/learned intent features |
| RAG tokens / embedding | BM25 tokenizer `re.findall(r'\w+', text.lower())`; BGE sentence embeddings normalized with FAISS `normalize_L2`. | Implemented |
| Retrieval metadata | Metadata condition/goal/category/type/tags/text filtering. List-valued filter branch is a no-op. | Partial |
| Score normalization/fusion | BM25 min-max over fetched pool; dense cosine/IP; `alpha*dense+(1-alpha)*BM25`, alpha=0.7. | Implemented; raw scales are fused after BM25 normalization, dense normalization is inherent from vectors/index |
| Cache normalization | Strip/lower/collapse whitespace; normalize query embedding; cosine dot vs LRU entry, invalidate by dataset hash; threshold 0.95, size 1000. | Implemented |
| Meal allocation/portion | Daily planner slots and fixed calorie shares; portion formulas in §11; nutrient scaling from per-100g. | Implemented |
| Parent context and prompt | Child chunk expands to parent text; prompt embeds profile, planner totals, retrieved text and scores; see `llm/prompt_templates.py`. | Implemented |
| Image-derived portion | App accepts local-service `portion_estimates`; Gemini fallback prompt also requests a portion estimate and backend uses returned `portion_estimate`. | Prompt/integration implemented; validated/calibrated portion inference **NOT FOUND / NOT VERIFIED** |
| NER-derived entities/context expansion | **NOT FOUND / NOT VERIFIED** in runtime code. |

No numeric weight normalization, condition-based planner multiplier other than named fever/infection/diarrhea keywords, goal adjustment except keyword rules, nutrient-constraint optimizer, prompt-injection classifier, or confidence-based adaptation was found in research prototype. App contains other separate engines but their outputs are not established as connected to the KidsNutriBite CLI planner.

## 8. Food Recognition Pipeline

Evidence is `food_analysis_model-main/yolo8n.ipynb`, its README and requirements. The notebook imports `ultralytics.YOLO`, loads `yolov8n.pt`, builds YOLO labels from UECFOOD256 annotation files (`bb_info.txt`), converts bounding boxes to normalized center-x/center-y/width/height, random-shuffles samples, then slices 70% train, 15% validation, 15% test. It writes a YAML with class IDs 0–255 named `food_0` … `food_255`. Class-specific distribution and exact split sizes are not printed in committed notebook output: **NOT FOUND / NOT VERIFIED**.

Training call: `model.train(data=..., epochs=50, imgsz=640, batch=16, device=0, patience=5)`. Optimizer, LR, loss override, augmentation, seed, and explicit normalization: **NOT FOUND / NOT VERIFIED**; Ultralytics defaults are not a repository-set value. Framework: Ultralytics YOLOv8 Nano; exact package version and base checkpoint version/weights hash: **NOT FOUND / NOT VERIFIED**. Task is detection (boxes), not image-level classification/segmentation. Portion estimation in this YOLO model: **NOT FOUND / NOT VERIFIED**. Separately, the NutriBite Gemini fallback prompt requests portions, but no accuracy validation for those estimates was found.

Validation (`best_model.val(data=food.yaml)`) prints box precision/recall/mAP. README reports Precision 0.6338523714, Recall 0.5973692188, mAP@50 0.6578420830, mAP@50–95 0.5126261911. Notebook defines `F1` nowhere; reported F1, IoU, test-split metrics and sample size/split association beyond val default: **NOT FOUND / NOT VERIFIED**. A prediction example uses `conf=0.25`; not evidence that app inference uses the same threshold. Backend image nutrition mapping is `calculateFoodNutrition(food, qty)` using returned quantity; true visual portion model is absent. Compute GPU is set `device=0` in notebook; GPU model, CPU, RAM and completed run environment **NOT FOUND / NOT VERIFIED**. No trained `.pt` weights are checked into this repository.

## 9. Dynamic NER Pipeline

The requested document named “NutriBite Dynamic NER — Pipeline & Phase Summary” was **NOT FOUND / NOT VERIFIED** in the searched project trees. `docs/research/01_NER_RESEARCH.md` is present and is a proposal/evaluation design, not implementation evidence. It explicitly states that the current KidsNutriBite CLI extracts no such entities.

Proposed schema in that research note: `AGE`, `FOOD`, `NUTRIENT`, `ALLERGEN`, `CONDITION`, `GOAL`, `QUANTITY`, `UNIT`, `MEAL_SLOT`, `DIET_PATTERN`, `ANTHROPOMETRIC`, and annotation-only `FREQUENCY/DURATION`, `SYMPTOM`, `MEDICATION`. Candidate approaches discussed include rule/gazetteer matching, regex and linking/normalization. No baseline NER model, implemented architecture, training examples, seed examples, discovery pipeline, fuzzy/embedding matching, candidate ranker, deduplication, human-review UI, data-generation code, online adaptation, few-shot/continual learning, replay, entity linker, relation extractor, normalization runtime, versioning, or NER metric run was found: each **NOT FOUND / NOT VERIFIED** as implementation.

The exact NER→normalized entities/relations→RAG connection is **NOT FOUND / NOT VERIFIED** in executable code. It is an active research proposal in `docs/research/01_NER_RESEARCH.md`; do not report it as completed.

| Phase | Proposed or current behavior | Runtime status |
|---|---|---|
| Baseline/entity schema | Proposed labels grounded in structured DB and query use cases | Research only |
| Candidate/lexical discovery | Gazetteer, regex/Aho–Corasick discussion | Research only |
| Fuzzy/embedding/context rank | No code found | NOT FOUND / NOT VERIFIED |
| Link/normalize and relation extraction | Described as needed; no executable component found | NOT FOUND / NOT VERIFIED |
| Annotation/training/adaptation/continual/replay | No dataset or implementation found | NOT FOUND / NOT VERIFIED |
| Evaluation | Research questions proposed; no NER evaluation records/metrics found | NOT FOUND / NOT VERIFIED |

## 10. Hybrid RAG Pipeline (KidsNutriBite)

1. Source: JSON records from `data/rag/rag_data.json`; indexer consumes each `id`, `text`, and `metadata`.
2. Document creation: already-recorded JSON entries; no PDF/HTML ingestion in the runtime RAG indexer.
3–6. Chunking: character-based hierarchical parent/child splitter. Parent size 600 chars; child size 150 chars; overlap 30 chars. Splitter attempts a whitespace split within the window. Parent split also uses 30-char overlap.
7–8. Parent and child counts: **NOT FOUND / NOT VERIFIED** as checked-in count in text artifacts. Artifacts are in `data/rag/faiss.index` and `metadata.pkl`; counts require safely parsing index/metadata or rebuilding.
9–13. Embedding: `BAAI/bge-small-en-v1.5`, SentenceTransformers; vector dimension from research notes is 384, official model config not pinned locally. Vectors L2-normalized; FAISS `IndexFlatIP` (inner product, equivalent cosine ordering for normalized vectors).
14–15. Sparse retrieval: `rank_bm25.BM25Okapi`, token regex `\w+` on lowercase text. No BM25 parameter overrides.
16–18. Dense and lexical fetch `max(rerank_top_n, k*3)`; defaults `rerank_top_n=20`, `k=5`, so fetch pool 20. Fusion `score=0.7*dense_score+0.3*bm25_score`. BM25 scores are min-max normalized over returned pool; no RRF.
19–21. Metadata filtering enabled; cross encoder `cross-encoder/ms-marco-MiniLM-L-6-v2`; final reranker top-k 5. Candidate pool target 20, but filtering/fallback can alter the count.
22–24. Parent expansion returns parent text with child text, IDs, metadata and score. Semantic LRU cache max 1000, threshold 0.95, same-query normalization lowercase/whitespace collapse; entries invalidated when dataset hash changes. Context builder emits expanded result list; prompt renderer adds IDs, relevance scores and text.

Code: `rag/chunker.py`, `rag/indexer.py`, `rag/services/{config_service,embedding_service,bm25_service,fusion_service,metadata_filter_service,reranker_service,prompt_context_service,cache_service,retrieval_service}.py`, `llm/prompt_templates.py`. Query flow: raw text → query embedding/cache → parallel dense and sparse retrieval → linear fusion → metadata filtering → cross-encoder rerank → parent expansion/cache → prompt context → LLM. Note implementation looks up cache before retrieval but still computes embedding first.

## 11. Nutrition Planner

`planner/diet_planner.py` uses JSON structured tables, not a numerical optimizer. Exact formulas:

- If weight missing/nonpositive: `age<1`: `months=max(1,age*12)`, `w=(months+9)/2`; `1<=age<=6`: `w=2*age+8`; `7<=age<=12`: `w=(7*age-5)/2`; else `w=3*age`.
- Base energy (the code labels it Holliday–Segar): if `w<=10`, `100*w`; if `10<w<=20`, `1000+50*(w-10)`; if `w>20`, `1500+20*(w-20)`.
- Goal surplus: +300 kcal if goal string contains gain/growth/boost; −200 kcal if contains loss/management/obesity; otherwise 0.
- Condition multiplier: 1.12 if condition contains fever/infection/diarrhea; else 1.0.
- Final daily kcal: `round(base_kcal*condition_multiplier+goal_surplus,1)`; returned weight rounded to 0.1 kg.
- Daily slot shares: breakfast 25%, snack 10%, lunch 35%, dinner 30%.
- Weekly planner slot shares: breakfast 20%, morning snack 10%, lunch 25%, afternoon snack 10%, evening snack 10%, dinner 25% (sum=100%); it emits seven days and six slots/day.
- Portion when `portion_energy_kcal>0`: `scale=min(2,max(0.5,remaining_kcal/default_portion_kcal))`; portion grams=`scale*100` (assumed 100g base); added kcal=`scale*default_portion_kcal`.
- Otherwise portion=`min(200,max(30,(remaining_kcal/kcal_per_100g)*100))`; missing/nonpositive energy substitutes 100 kcal/100g.
- Protein/fat/carbs/iron contributions = `(portion_g/100)*per100g_field`, rounded to 2 decimals. Daily totals sum selected food contributions.
- Greedy order score: +5 per required tag match; +2 if boiled digestibility is `high`; −2 if fried digestibility is `low`. Candidate walk stops when accumulated kcal `>=0.95*slot_target` or foods exhausted. No global optimization or stated tolerance beyond this stopping test.
- Weekly planner caps selection at 3 foods/slot, divides remaining slot calories across remaining item slots unless one slot remains or remaining kcal<50, and penalizes a food used in the previous day’s same slot by 100 priority points. If a macro’s running target ratio is the lowest of protein/fat/carbohydrate, foods matching its category/tag/high per-100g content receive +10. Post-day validation flags calories met within 15% and protein within 20%; it does not iterate to repair a failed day. It reports `is_safe` true when candidate foods are nonempty, which is not a clinical safety validation.
- Weekly target macros: protein=`round(kcal*0.15/4,1)`, carbs=`round(kcal*0.55/4,1)`, fat=`round(kcal*0.30/9,1)`, fibre=`round(kcal/1000*14,1)`. These targets do not establish that an optimization loop meets the targets.

Age filtering is `age < food.age_min`; allergy and tag filtering as §7. Required tags rank rather than exclude. Planner input keys: `age` default 5, optional `weight`, `goal`, `condition`, `allergies`; output includes profile, calorie target, totals, meal plan. Weekly planner is present; its exact iterative selection/stopping details should be reported only from its own function body and are not assumed to equal daily planner. Data field unit `age_min` is not disambiguated in the source; **NOT FOUND / NOT VERIFIED** whether its values are months or years. No macro/fibre condition-adjustment, RDA compliance solver, confidence mechanism, or constraint optimizer found.

## 12. Qwen LLM Configuration

The Python prototype defaults `KidsNutriLLMClient` to `qwen_local`, and routes local calls to `Qwen/Qwen2.5-7B-Instruct`. Official model card reports 7.61B parameters (6.53B non-embedding). Local load uses Transformers pipeline, `device_map="auto"`, 4-bit bitsandbytes NF4 and double quantization when available; fallback without bitsandbytes uses fp16. The project research note and official model config identify Qwen2ForCausalLM; hidden size 3584; 28 layers; 28 query heads; 4 KV heads; head dimension 128; intermediate size 18944; vocab 152064; config `max_position_embeddings=32768`; RoPE theta 1,000,000; RMSNorm epsilon 1e-6; SiLU/SwiGLU; released checkpoint dtype bfloat16. Actual local compute path in code uses 4-bit quantization; exact runtime compute dtype when bitsandbytes is enabled is **NOT FOUND / NOT VERIFIED** (the code passes `torch_dtype=None` alongside quantization). No specific downloaded checkpoint revision/hash is pinned. Architecture/parameter details: [official Qwen2.5-7B-Instruct model card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct), [checkpoint config](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/raw/main/config.json).

Generation defaults: temperature 0.1, top_p 0.9, max_new_tokens 1024. Local transformer path uses `do_sample=False` for its greedy branch or `do_sample=True` with those sampling settings for another branch; actual path is branch-dependent. `repetition_penalty`, stop sequences/criteria, and seed: **NOT FOUND / NOT VERIFIED**. API backends have distinct parameter mappings; do not ascribe all local parameters to cloud runs.

Prompt construction: `SYSTEM_PROMPT`/`QA_SYSTEM_PROMPT`; user content contains query, age/weight/goal/condition/allergies, planner targets/totals/meal schedule if diet mode, retrieved chunk ID/score/text. App-side separate prompt includes child/clinical context and tool results; food recognition and NER outputs are not included in the KidsNutriBite research prompts. Evidence: `llm/llm_client.py`, `llm/prompt_templates.py`, official Qwen checkpoint `config.json` (link in source references).

## 13. Self-Attention / LLM Architecture

Verified architecture values above apply to Qwen2.5-7B-Instruct architecture, not every provider used by the app. Let hidden states `X∈R^(T×3584)`. Q/K/V projections produce 28 query heads and 4 key/value heads, each width 128. GQA shares each KV head across 7 query heads. RoPE is applied to Q and K by position. Attention (causal mask `M`):

`Q=XW_Q+b_Q`, `K=XW_K+b_K`, `V=XW_V+b_V`;
`Attention(Q,K,V)=softmax((QK^T)/sqrt(128)+M)V` after RoPE on Q,K, with KV head repetition/group mapping for query heads.

Each block uses pre-norm residual attention and feed-forward paths. RMSNorm: `RMSNorm(x)=g⊙x/sqrt(mean(x²)+1e-6)`. SwiGLU feed-forward: `FFN(x)=W_down(SiLU(W_gate x)⊙(W_up x))`. Residual equations: `h=x+Attention(RMSNorm(x))`; `y=h+FFN(RMSNorm(h))`. Exact weight matrices and per-layer code are inside the external checkpoint/library, not checked into this repository. Qwen research note `docs/research/04_SELF_ATTENTION_RESEARCH.md`; official checkpoint config cited below.

## 14. Safety / Validation

| Safety property | Status / evidence |
|---|---|
| Diagnosis/medication restriction | Research prompt explicitly instructs refusal for diagnosis/drugs/treatment; app prompt asks for clinical framing, but no comprehensive refusal matcher found. Prompt-only for CLI; enforceability **partial**. `llm/prompt_templates.py`. |
| Pediatric disclaimer | App appends disclaimer unless answer contains `ICMR-NIN` or `pediatric`; CLI prompts request disclaimer but no deterministic post-validator found. `aiOrchestrator.service.js::SafetyLayer.applyPediatricDisclaimer`. |
| Input length sanitation | App trims and truncates to 1000 chars. No injection-specific sanitization found. `aiOrchestrator.service.js::SafetyLayer.sanitizeInput`. |
| Allergen conflict | `checkAllergies` text heuristic exists; app agent has allergen tool and `verifyToolOutputs` checks its `isSafe` result. Image meal controller accepts correction history and nutrition handling. Coverage is rule-based and not a proven universal guarantee. |
| Output response validation | `ResponseValidator` class is imported/used in other AI orchestration; exact coverage does not establish the agent workflow validates arbitrary generated content. Agent `verifyToolOutputs` only examines allergen result. |
| Grounding/fact verification | KidsNutri prompts constrain answers to retrieved context/planner values; evaluator has LLM claim/context judges. Runtime deterministic factual verifier: **NOT FOUND / NOT VERIFIED**. |
| Doctor escalation | Intent labels and follow-up/clinical routes exist. Always-triggered doctor escalation policy for every risky answer: **NOT FOUND / NOT VERIFIED**. |
| Prompt injection protection | **NOT FOUND / NOT VERIFIED**. |
| Unsafe recommendation detector/refusal rules | No general deterministic detector established; allergy substring checks and prompt instructions only. |
| Logging | App JSON console workflow audit and Mongo ChatLog; research RAG structured retrieval logs and evaluation judge logs exist. Retention/PII policy: **NOT FOUND / NOT VERIFIED**. |

## 15. Databases / Storage

| Store | Technology / purpose / fields | Access |
|---|---|---|
| App DB | MongoDB through Mongoose; collections described in §6; actual production record counts/host **NOT FOUND / NOT VERIFIED** | `backend/config/db.js`, models and controllers |
| RAG vector index | FAISS `IndexFlatIP`; vectors and child/parent metadata in `data/rag/faiss.index`, `metadata.pkl`; exact vector count **NOT FOUND / NOT VERIFIED** | `rag/indexer.py`, `RetrievalService` |
| Nutrition structured store | JSON files: foods/conditions/goals/allergies; 99/173/148/15 rows | `planner/diet_planner.py` |
| Semantic cache | In-memory OrderedDict LRU, max 1000, threshold .95; not durable | `rag/services/cache_service.py` |
| App cache | Node `node-cache` dependency; specific active cache usage for these AI flows **NOT FOUND / NOT VERIFIED** | `backend/package.json` and search |
| Logs | RAG retrieval logger; evaluation CSV/JSON/console judge traces; app ChatLog/AuditLog and structured workflow console event | `rag/services/logger_service.py`, `reports/`, app models/services |
| Evaluation storage | JSON gold dataset; generated CSV/Markdown and debug JSON/log files | `docs/evaluation/`, `reports/`, `evaluation/comparator.py` |

## 16. Experimental Setup

Research prototype evaluation dataset: 49 gold-annotated cases in `docs/evaluation/phase2c_gold_annotations.json`; command-line default `--num-samples 100`, but comparator limits to available records. Default answer model `qwen_local`; default judge model from current CLI setting must be read from `main.py` at run configuration (the checked notes describe Groq-hosted judge use in later phases). Model comparison supports several local/cloud adapters, but live model/provider execution is not verified by the code alone. Number of completed runs, fixed seed, actual sampling order, hardware/GPU/CPU/RAM, Python/library versions used for reported metrics, exact inference settings per recorded result and evaluator model actually used for each CSV: **NOT FOUND / NOT VERIFIED** unless a specific run record explicitly provides it. Current environment is not evidence of historical experiment hardware.

Vision experiment: UECFOOD256 source path in notebook, random 70/15/15 split, 50 epochs, image size 640, batch 16, device 0, patience 5; split counts, random seed, exact software versions and hardware model **NOT FOUND / NOT VERIFIED**.

Dynamic NER experiments, app end-to-end controlled research evaluation, pruning/compression training, safety red-team benchmark results, formal ablations: **NOT FOUND / NOT VERIFIED** as completed reproducible experiments. Repository files describe evaluation plans for NER and pruning; these are proposals only.

## 17. Evaluation Protocol

| Experiment | Objective / data / procedure | Status |
|---|---|---|
| RAG retrieval | `KidsNutriComparator` evaluates retrieved IDs against gold `relevant_chunk_ids`; Precision@5, Recall@5, AP/MAP@5, MRR@5; 49-case gold dataset, RAG-applicable subset only | Implemented evaluation code; run-specific completed sample size/result provenance must be checked in result artifacts |
| RAG generation/grounding | System output evaluated by LLM judges for claims/support, hypothetical questions/relevancy and context facts; deterministic metric layer aggregates | Evaluation code implemented; judging depends on provider/API and existing outputs; run configuration may vary |
| Model comparison | `--models`, default `qwen_local`, configurable sample limit; code supports other model adapters | Implemented runner; no claim of all model comparisons having completed. Old `reports/evaluation_summary.md` says simulated outputs and is not reliable evidence of real inference; treat as legacy. |
| Safety evaluation | Safety judge compares judgments to `safety_ground_truth`; evaluator can disable. The active 49-case file has 20 non-null safety labels and 29 nulls; separate phase2d file contains 20 safety-label records. | Evaluation code exists; completed run metrics **NOT FOUND / NOT VERIFIED** at aggregate level |
| Food recognition | YOLO notebook validates model with `best_model.val`; reports P/R/mAP values in README | Run described and metrics recorded; sample count and independent test results absent |
| NER | Research note proposes comparative experiments | Not executed / no implementation evidence |
| Pruning/compression | Research notes discuss feasibility | No completed pruning experiment found |
| End-to-end app evaluation | App functional test scripts exist for workflows, but no controlled paper dataset/protocol/results located | **NOT FOUND / NOT VERIFIED** |
| Ablation | No executed/configured component ablation dataset/protocol identified | **NOT FOUND / NOT VERIFIED** |

Do not promote every `test_*.py` into a paper experiment: many are unit/metric-contract tests. Evaluation tests provide software checks, not clinical task evaluation evidence.

## 18. Metric Definitions

Definitions used by `evaluation/metrics/`:

- Precision@K = relevant retrieved in first K / K. The implementation marks fewer than K returned labels incomplete rather than reducing denominator.
- Recall@K = relevant retrieved IDs in first K / total gold-relevant IDs.
- AP@K = sum of precision at each relevant rank in first K / total number of gold-relevant items for that query (including relevant items not retrieved); MAP@K is mean over valid per-query AP values. The metric helper's legacy no-ground-truth path can divide by retrieved hits, but the official gold-ID path supplies the full gold count.
- Reciprocal rank@K = `1/r` for first relevant rank `r<=K`, else 0; MRR@K is the mean valid reciprocal rank.
- Faithfulness = supported claims / total evaluated claims; unsupported claim rate = unsupported claims / total evaluated claims. Response-level hallucination status is derived from unsupported claims and type labels in `grounding_metrics.py`; do not conflate it with claim-level unsupported rate.
- Answer relevancy = cosine similarity between embedding of original query and embeddings of LLM-generated hypothetical questions, averaged by `relevancy_metrics.py`.
- Context recall = supported expected facts / total expected facts, where facts come from context judge; invalid judge/no-ground-truth cases get explicit missing/failure statuses.
- Safety precision=`TP/(TP+FP)`, recall=`TP/(TP+FN)`, F1=`2PR/(P+R)`; positive class in `safety_metrics.py` is a violation. Dataset truth and skipped status must be reported with each aggregate.
- Vision P=`TP/(TP+FP)`, R=`TP/(TP+FN)` and F1=`2PR/(P+R)` as conventional detection definitions; notebook reports P/R and mAP from Ultralytics, no repository F1 value. IoU = intersection area/union area; per-run IoU result **NOT FOUND / NOT VERIFIED**.
- Latency is measured with wall-clock elapsed seconds in the LLM client/evaluator. Throughput, peak memory, and serialized model size experiment measures **NOT FOUND / NOT VERIFIED**.

Metric implementations: `evaluation/metrics/retrieval_metrics.py`, `grounding_metrics.py`, `relevancy_metrics.py`, `safety_metrics.py`; vision notebook and README. AP denominator and validity semantics should follow implementation, not substitute a different textbook variant.

## 19. Baselines

Implemented/available comparisons only: research RAG supports `hybrid`, `semantic`, and `keyword` retrieval modes through `RAGConfig.retrieval_mode`; these are executable modes, but an ablation result proving a comparison was run is **NOT FOUND / NOT VERIFIED**. LLM adapters include local Qwen2.5-7B-Instruct, Gemini, OpenRouter model routes, Groq routes and local Llama route. Which exact baselines were actually run in a reproducible, non-simulated comparison: **NOT FOUND / NOT VERIFIED** for the final paper. Vision initializes pretrained `yolov8n.pt`; no other vision architecture baseline. NER baseline model: **NOT FOUND / NOT VERIFIED**.

## 20. Ablation Studies

No controlled completed ablation with declared full/control configurations and reported metric set was identified. `semantic`/`keyword`/`hybrid` modes and switches for cache/reranking/metadata filtering make component comparisons technically configurable, but an executed ablation, dataset and results are **NOT FOUND / NOT VERIFIED**. Qwen pruning is research-only; no ablation result. Dynamic NER ablation is not implemented.

## 21. Statistical Analysis

Sample sizes are given only where a source dataset count is known (49 evaluation cases; vision per-split counts **NOT FOUND / NOT VERIFIED**). Paired/unpaired design, repeated runs, statistical test, confidence interval procedure, significance level, bootstrap, randomization/permutation procedure: **NOT YET PERFORMED** in the checked source/report artifacts.

## 22. Implementation Status

| Component | Implemented | Under development / proposal | Not found / not implemented in inspected repos | Evidence |
|---|---:|---:|---:|---|
| Backend | Yes (NutriBite app, Express/Mongoose) | — | — | app server/routes/controllers |
| Frontend | Yes (Next.js/React role pages) | — | — | `frontend/src/app/**` |
| Food recognition | YOLO training notebook, app HTTP client, Gemini multimodal fallback and result handling | Local service integration depends on unavailable service; fallback portion estimates are requested but not validated | YOLO portion model, checked-in weights | notebook; meal controller |
| Hybrid RAG | Yes (KidsNutriBite Python CLI) | — | — | `rag/**` |
| Nutrition planner | Yes (KidsNutriBite deterministic Python; app has separate planner engines) | — | — | `planner/diet_planner.py`; app services |
| Qwen | Local client path/config exists | Actual run environment varies | Pinned revision/runtime evidence | `llm/llm_client.py` |
| Safety | Prompt restrictions, allergy heuristics, disclaimer; evaluation rubric code | Coverage is partial | Comprehensive injection detector/general validator not verified | prompt templates, `aiOrchestrator.service.js` |
| Agentic orchestration | Yes, fixed intent→tool mapping in app | External AI service may add behavior, source unavailable | LLM-autonomous planning not verified | `agentOrchestrator.service.js` |
| MCP tool layer | — | — | Not found | inspected app and prototype code |
| Web search | — | — | Not found | tool search |
| Nutrition analysis tool | Equivalent nutrient gap tools | — | Exact requested tool ID not found | `AgentTools` |
| Growth analysis tool | Equivalent growth velocity tool | — | Exact requested tool ID not found | `AgentTools` |
| Meal planner tool | Equivalent pediatric meal planner | — | Exact requested tool ID not found | `AgentTools` |
| Food recognition tool | HTTP upload client exists | service integration | registered agent tool/model service source | meal controller |
| Dynamic NER | Research proposal only | Active research design | Runtime NER | `docs/research/01_NER_RESEARCH.md` |
| Entity linking | — | Proposed | Runtime linking | NER research only |
| Relation extraction | — | — | Not found | code search |
| Continual NER | — | — | Not found | code search |
| Entity-aware RAG | — | Proposed pipeline concept | Executable integration | code search |

## 23. Exact Methodology Facts

### FACTS SAFE TO USE IN METHODOLOGY

- The KidsNutriBite CLI prototype combines deterministic structured-food planning, hybrid dense/sparse retrieval, and a selectable LLM client; its default model setting is local `Qwen/Qwen2.5-7B-Instruct`.
- Its raw RAG JSON contains 558 records; structured files contain 99 foods, 173 condition records, 148 goal records, and 15 allergy records.
- RAG chunking is character-based, parent 600, child 150, overlap 30; embeddings use BAAI/bge-small-en-v1.5 with L2 normalization; FAISS uses IndexFlatIP; BM25 uses lowercase `\w+` tokenization; default fusion is 0.7 dense/0.3 sparse; cross-encoder reranker is `cross-encoder/ms-marco-MiniLM-L-6-v2`; final default top-k is 5; semantic cache max 1000 and similarity threshold .95.
- The Python planner uses age-based estimated weight when missing, the exact Holliday–Segar-style piecewise calculation and keyword goal/condition adjustments documented in §11, rule-based allergy/tag filters, and greedy meal-slot allocation.
- The research CLI does not implement a frontend, web server, MCP, or runtime NER.
- The NutriBite app has an implemented Express/MongoDB stack and a deterministic seven-stage intent/context/fixed-tool/synthesis/follow-up workflow. It maps intents to one or more fixed backend tools; its code alone does not prove autonomous LLM tool selection or MCP.
- The food model notebook uses YOLOv8n initialized from `yolov8n.pt`, a UECFOOD256-style box conversion/split, and the recorded validation metrics in §8. These metrics lack saved sample-count and split-run provenance.
- The NER project is documented as research/proposal in `docs/research/01_NER_RESEARCH.md`; executable dynamic NER and its RAG connection are not verified.
- The research prototype evaluation data file contains 49 annotated gold cases. Retrieval/generation/safety metric code exists; presence of code is not evidence that a specific full evaluation run was completed.

### MISSING DATA REQUIRED BEFORE FINAL PAPER

- The named “NutriBite Dynamic NER — Pipeline & Phase Summary” source document; model/data/code for NER; its actual phase status and runtime/RAG integration.
- Checked-in AI service server code and exact deployed endpoints/model/prompt; operational status and version of the app’s `AI_SERVICE_URL` target.
- Checked-in food recognition API/model weights, pinned package/model versions, class-level counts/distribution, exact train/validation/test counts, random seed, test-split metrics, F1/IoU, hardware and reproducible run metadata; validated/calibrated Gemini fallback portion estimates.
- Actual counts of serialized parent/child chunks and FAISS vectors from the built index, plus source-level provenance for each knowledge document.
- Exact application MongoDB population counts and deployment configuration; complete app flow test/evaluation protocol and results.
- Run-specific Qwen/provider checkpoints, library versions, compute dtype, generation settings and API request logs tied to recorded evaluation rows; actual hardware/RAM/GPU and number of runs/seeds.
- Final, non-simulated model baseline outputs and exact sample subset; safety ground-truth coverage/review status for the rows used in any reported metric.
- Completed NER, end-to-end, safety, ablation, pruning/compression experiments if those claims are intended for the paper; metrics and evaluation protocols.
- Statistical analysis: **NOT YET PERFORMED** in checked artifacts.
- Stable food/allergy schema mapping and age_min units; independently validated nutrition values and data completeness. The repository documents missing numeric/allergy-tag values and avoid-food entries that do not match food records.
- Whether the app-side recognized portion estimate is actually produced by the deployed recognition system; source code for the service is absent.

## Primary Local Evidence Index

- Research CLI and orchestration: `main.py`, `planner/diet_planner.py`, `rag/**`, `llm/**`, `evaluation/**`.
- Research architecture and NER: `docs/research/00_CURRENT_ARCHITECTURE.md`, `01_NER_RESEARCH.md`, `02_FEATURE_ENGINEERING_RESEARCH.md`, `03_QWEN_ARCHITECTURE_RESEARCH.md`, `04_SELF_ATTENTION_RESEARCH.md`.
- Gold evaluation data: `docs/evaluation/phase2c_gold_annotations.json`; evaluation code in `evaluation/`.
- App: `C:/Users/DINESH/Projects/nutrikid/NutriBite/backend/**` and `frontend/src/**`.
- Vision: `C:/Users/DINESH/Projects/food_analysis_model-main/yolo8n.ipynb`, `README.md`, `requirements.txt`.
- Architecture values verified against official checkpoint configuration: [Qwen2.5-7B-Instruct config.json](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/raw/main/config.json).
