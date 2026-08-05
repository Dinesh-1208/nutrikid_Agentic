# KidsNutriBite: Technical Documentation

## 1. LLM Module

### 1.1 Overview
The LLM Module (`llm_client.py`) is the centralized inference engine responsible for generating friendly, easily digestible, and mathematically sound responses. It acts as an abstraction layer to dynamically route requests to various Large Language Models (LLMs) running either locally or in the cloud.

### 1.2 Objective
To synthesize strict deterministic dietary plans and retrieved medical protocols into conversational text, while ensuring medical safety thresholds are met and avoiding hallucinations.

### 1.3 Architecture
The module uses a multi-provider wrapper architecture. It dynamically routes inference tasks based on the `model_name` requested, utilizing specific SDKs (like `google.generativeai`, `requests` for OpenRouter, or `transformers` for local models). For local models, it leverages 4-bit quantization to optimize VRAM usage.

### 1.4 Components
*   **Client Manager (`KidsNutriLLMClient`)**: The central class managing API keys, model routing, and default generation configurations.
*   **Cloud Connectors**: Handlers for Google Gemini, OpenRouter, and Groq APIs.
*   **Local Inference Engine**: A HuggingFace Transformers pipeline configured for 4-bit quantization (via `bitsandbytes`) for local execution of Qwen and Llama models.
*   **Safety & Rate Limit Handlers**: Custom exponential backoff logic for API rate limits and configured safety thresholds to prevent false positives when discussing medical symptoms.

### 1.5 Detailed Data Flow
1.  **User / Agentic Module** → System Prompt & User Prompt → **LLM Client Manager**
2.  **LLM Client Manager** → Routes to specific connector (e.g., `_call_gemini` or `_call_local_transformers`).
3.  **Connector** → Sends API request (Cloud) OR Passes through local GPU (Local).
4.  **Target LLM (Cloud/Local)** → Returns Raw Generated Text.
5.  **LLM Client Manager** → Calculates Latency, cleans EOS tokens → **Backend/Agentic Module**.

### 1.6 Workflow
1.  Initialize the client and load environment API keys.
2.  Receive a request with a specific target model, system prompt, and user prompt.
3.  If local, check the model cache; if not loaded, load the tokenizer and model into VRAM using 4-bit quantization.
4.  Execute generation using a deterministic temperature setting (`0.1`) to ensure benchmarking consistency.
5.  Handle rate limit exceptions (HTTP 429) via exponential backoff.
6.  Return the generated text and latency metrics.

### 1.7 Inputs and Outputs
*   **Inputs**: `system_prompt` (string), `user_prompt` (string), `model_name` (string - optional).
*   **Outputs**: `response_text` (string), `latency` (float - seconds).

### 1.8 APIs / Models / Tools Used
*   **APIs**: Google Gemini API, OpenRouter API, Groq API.
*   **Models**: Gemini-2.5-flash, Llama-3.1-8B, Qwen-2.5-7B, Llama-3.3-70B.
*   **Libraries**: `google-generativeai`, `transformers`, `torch`, `bitsandbytes`.

### 1.9 Error Handling
*   **Rate Limits**: Implements a 5-retry exponential backoff mechanism (base delay 12s) specifically tailored for Gemini's free-tier RPM limits.
*   **Missing Credentials**: Fallback error raising if an API key or local GPU (`torch.cuda.is_available`) is missing for the requested model.

### 1.10 Security & Privacy Considerations
*   **Safety Thresholds**: Google Generative AI safety settings are configured to `BLOCK_NONE` to prevent the model from refusing to answer legitimate medical/pediatric queries (e.g., discussing symptoms or body parts).
*   **Data Privacy**: By utilizing the local Llama/Qwen models, the system can run entirely offline, ensuring maximum privacy for Protected Health Information (PHI).

### 1.11 Advantages
*   **Flexibility**: Seamlessly switch between cutting-edge cloud models and secure local models.
*   **Resource Efficiency**: 4-bit quantization allows heavy models to run on standard 15GB VRAM consumer GPUs.

### 1.12 Limitations
*   Cloud models remain dependent on internet connectivity and third-party rate limits.
*   Local models are significantly slower than Groq/Gemini and require a dedicated CUDA GPU.

### 1.13 Future Improvements
*   Implement asynchronous streaming (`yield`) for real-time UI token rendering.
*   Add integration with vLLM for faster local inference serving.

---

## 2. Agentic AI Module (Diet Planner & RAG)

### 2.1 Overview
The Agentic AI Module is the "brain" of the operation. It combines a strict, deterministic rule-based calculation engine (`DietPlanner`) with a semantic retrieval pipeline (RAG). It calculates exact biological needs and curates a safe diet plan before passing the context to the LLM.

### 2.2 Objective
To generate mathematically sound, clinically safe dietary recommendations based on pediatric anthropometrics, while filtering out allergens and retrieving relevant clinical guidelines to ground the LLM's response.

### 2.3 Architecture
A dual-layer architecture consisting of a Python-based deterministic rules engine and a FAISS-backed dense vector retriever. The rules engine calculates raw numbers, while the RAG system provides semantic medical context.

### 2.4 Components
*   **Nutritional Database (`KidsNutriDatabase`)**: An in-memory JSON data layer containing structured data on foods, conditions, goals, and allergies.
*   **Anthropometric Calculator**: Calculates Base Metabolic Rate (BMR) and caloric needs based on age, weight, and condition modifiers (using the Holliday-Segar formula).
*   **Food Segmenter & Filter**: A constraint-solver that filters candidate foods by age limits, absolute allergy exclusions, and required/avoided tags.
*   **RAG Retriever**: A dense vector index (FAISS + `BAAI/bge-small-en-v1.5`) that searches pediatric guidelines.

### 2.5 Detailed Data Flow
1.  **User UI** → Submits Query + Profile (Age, Weight, Allergies, Condition) → **Backend API**
2.  **Backend API** → Routes to **Agentic AI Module (Diet Planner)**.
3.  **Diet Planner** → Checks Database → **Anthropometric Calculator** (Calculates target calories, e.g., +12% for fever).
4.  **Diet Planner** → **Food Filter** (Removes allergens/unsafe foods based on tags) → Distributes calories across 4 meals (Breakfast, Lunch, Dinner, Snack).
5.  **RAG Retriever** → Embeds User Query → Searches FAISS Vector DB → Retrieves top clinical protocols.
6.  **Agentic AI Module** → Compiles structured JSON Diet Plan + Retrieved Text Context → Sends to **LLM Module**.

### 2.6 Workflow
1.  Ingest the user profile (age, weight, condition, allergies).
2.  Calculate baseline caloric needs. If weight is missing, extrapolate from pediatric age-weight norms.
3.  Adjust caloric targets based on the specific condition (e.g., hypermetabolism during fever) or goal (weight gain).
4.  Filter the global food database strictly removing any food matching user allergies.
5.  Score and select remaining foods based on digestibility and condition tags, splitting them into mathematically accurate meal portions to meet calorie goals.
6.  Output a structured JSON plan ready for LLM synthesis.

### 2.7 Inputs and Outputs
*   **Inputs**: User Profile Dictionary (age, weight, condition, goal, allergies), User Query (string).
*   **Outputs**: Structured Diet Plan (JSON: meal breakdowns, exact portions in grams, macro totals), Retrieved RAG Context (string).

### 2.8 APIs / Models / Tools Used
*   **Database**: Local JSON structured storage.
*   **Embedding Model**: `BAAI/bge-small-en-v1.5` (via `sentence-transformers`).
*   **Vector Store**: FAISS.

### 2.9 Error Handling
*   **Missing Data Extrapolation**: If a child's weight is not provided, the module uses standard pediatric formulas to estimate weight based on age (months/years).
*   **Portion Fallbacks**: If database items lack specific energy densities, the system scales standard 100g portions safely to meet target calories.

### 2.10 Security & Privacy Considerations
*   **Deterministic Safety**: By calculating calories and filtering allergens via rigid Python rules *before* LLM intervention, the architecture guarantees that an LLM hallucination cannot accidentally recommend an allergen or miscalculate BMR.

### 2.11 Advantages
*   Zero-hallucination guarantee on mathematics and allergen exclusions.
*   Highly customizable through simple JSON file edits without needing model fine-tuning.

### 2.12 Limitations
*   Rigid rule sets; the system cannot create dynamic recipes if the ingredients are missing from the local JSON database.
*   In-memory JSON database will not scale efficiently to millions of food items.

### 2.13 Future Improvements
*   Migrate from JSON to a relational database like PostgreSQL/SQLite for scalable querying.
*   Integrate external APIs (e.g., USDA FoodData Central) for real-time nutritional lookups.

---

## 3. UI Integration: How the Chatbot Works in Deployment

When deploying the KidsNutriBite project and connecting it to a frontend Chatbot UI (e.g., built with React, Next.js, or Flutter), the data flow transforms into a modern client-server architecture:

### 3.1 The Deployment Architecture
1.  **Frontend (Chatbot UI)**: A user interface where parents/doctors input the child's profile (Age, Weight, Allergies) into a settings modal, and type their dietary questions into a chat window.
2.  **Backend (FastAPI / Flask / Django)**: A web server wrapping the `main.py` pipeline. It exposes REST or WebSocket endpoints (e.g., `POST /api/chat`).
3.  **Core Modules**: The existing LLM and Agentic AI modules running on the server.

### 3.2 Step-by-Step UI Data Flow
1.  **User Input**: The user types "What should I feed my 5yo with a fever who is allergic to eggs?" into the UI. The UI bundles this text with the child's profile state and sends a JSON payload to the backend API.
2.  **Backend Processing**:
    *   The API receives the payload and passes the profile to the **Agentic AI Module (Diet Planner)**.
    *   The Planner mathematically calculates the child's exact caloric needs, filters out "egg" related foods from the database, and constructs a precise JSON meal plan.
    *   Simultaneously, the RAG Retriever pulls fever-related pediatric guidelines from the vector database.
3.  **LLM Synthesis**: The backend bundles the User Query, the JSON Meal Plan, and the RAG protocols into a single massive System Prompt, and sends it to the **LLM Module**.
4.  **Response Delivery**: The LLM synthesizes this into a warm, readable response. 
5.  **UI Rendering**: The backend sends the text back to the Chatbot UI. (If using Server-Sent Events or WebSockets, the LLM Module can stream the response word-by-word for a modern "typing" effect). The UI displays the message to the user, potentially rendering the JSON diet plan as a clean, interactive table or graphic alongside the chat.
