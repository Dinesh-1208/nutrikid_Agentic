# KidsNutriBite Google Colab Run Guide

Follow these steps to upload, configure, and execute the KidsNutriBite research prototype in a GPU-accelerated Google Colab environment.

---

## 1. Upload Project Files
* Zip the project directory files locally:
  ```powershell
  Compress-Archive -Path data, evaluation, llm, planner, rag, main.py, verify_gemini.py, verify_qwen.py, verify_openrouter.py, requirements.txt -DestinationPath project.zip
  ```
* Open [Google Colab](https://colab.research.google.com/).
* Click **Upload** (or select **File -> Upload notebook**) and upload the playbook notebook:
  `colab_setup.ipynb`
* Open the file explorer pane on the left sidebar (Folder Icon 📁).
* Click the **Upload** icon and upload the `project.zip` file.
* Run the unzip cell:
  ```python
  !unzip -o project.zip
  ```

---

## 2. Install Requirements
* Execute the dependency install cell in Colab:
  ```python
  !pip install sentence-transformers faiss-cpu google-generativeai pandas tabulate matplotlib
  ```

---

## 3. Enable T4 GPU
* Go to the top menu in Colab and select **Runtime -> Change runtime type**.
* Under **Hardware accelerator**, select **T4 GPU** (or any available GPU).
* Click **Save**.

---

## 4. Verify CUDA
* Run this command in a new cell to confirm that PyTorch can access the GPU:
  ```python
  import torch
  print("CUDA Available:", torch.cuda.is_available())
  if torch.cuda.is_available():
      print("GPU Name:", torch.cuda.get_device_name(0))
  ```

---

## 5. Verify Gemini
* In Step 2 of the notebook, configure your API key:
  ```python
  import os
  os.environ["GEMINI_API_KEY"] = "YOUR_GEMINI_API_KEY_HERE"
  ```
* Run the Gemini diagnostics command:
  ```python
  !python verify_gemini.py
  ```
* Confirm that the output reports `API reachable: YES`.

---

## 6. Verify Qwen
* Run the local open-source model diagnostics:
  ```python
  !python verify_qwen.py
  ```
* Confirm that the output reports `* GPU detected: YES` and successfully returns a sample response.

---

## 7. Run 5 Sample Evaluation
* Run a quick initial dry-run over 5 questions to verify that the evaluation judge and local pipeline run smoothly without issues:
  ```python
  !python main.py --evaluate --num-samples 5 --models gemini,qwen_local
  ```

---

## 8. Run 20 Sample Evaluation
* Execute a intermediate-sized evaluation to verify accuracy trend statistics:
  ```python
  !python main.py --evaluate --num-samples 20 --models gemini,qwen_local
  ```

---

## 9. Run 100 Sample Evaluation
* Run the full evaluation benchmark across all 100 questions in the dataset:
  ```python
  !python main.py --evaluate --num-samples 100 --models gemini,qwen_local
  ```

---

## 10. Generate Final Reports
Check the generated files under the `reports/` folder in the Colab sidebar:
* **GPU Hardware Status:** `reports/gpu_diagnostics.txt`
* **Real Inference Validation Proof:** `reports/inference_validation.md`
* **Retrieval Trace Scores:** `reports/retrieval_trace.csv`
* **Top-K Tuning Experiment (K=3, 5, 10):** `reports/retrieval_experiment.csv`
* **RAGAS Evaluations:** `reports/ragas_report.csv`
* **Safety Confusion Matrices:** `reports/safety_analysis.md`
* **Hallucination Rate & Evidence:** `reports/hallucination_analysis.md`
* **Final Summary Metrics Comparison:** `reports/final_model_comparison.csv`
