import json

with open("colab_setup.ipynb", "r", encoding="utf-8") as f:
    d = json.load(f)

d['cells'][2]['source'][0] = '!pip install sentence-transformers faiss-cpu google-generativeai pandas tabulate matplotlib groq'

source_4 = [
    "import os\n",
    "\n",
    "# Handle Kaggle environment automatically\n",
    "if os.environ.get('KAGGLE_KERNEL_RUN_TYPE'):\n",
    "    try:\n",
    "        from kaggle_secrets import UserSecretsClient\n",
    "        user_secrets = UserSecretsClient()\n",
    "        os.environ['GEMINI_API_KEY'] = user_secrets.get_secret('GEMINI_API_KEY')\n",
    "        os.environ['GROQ_API_KEY'] = user_secrets.get_secret('GROQ_API_KEY')\n",
    "        print('Loaded API keys from Kaggle Secrets.')\n",
    "    except Exception as e:\n",
    "        print('Could not load Kaggle secrets:', e)\n",
    "else:\n",
    "    # Set your API Keys here for Colab\n",
    "    os.environ['GEMINI_API_KEY'] = 'YOUR_GEMINI_API_KEY_HERE'\n",
    "    os.environ['GROQ_API_KEY'] = 'YOUR_GROQ_API_KEY_HERE'\n",
    "\n",
    "# Write keys to .env for the CLI orchestrator\n",
    "with open('.env', 'w') as f:\n",
    "    if os.environ.get('GEMINI_API_KEY'):\n",
    "        f.write(f'GEMINI_API_KEY=\"{os.environ[\"GEMINI_API_KEY\"]}\"\\n')\n",
    "    if os.environ.get('GROQ_API_KEY'):\n",
    "        f.write(f'GROQ_API_KEY=\"{os.environ[\"GROQ_API_KEY\"]}\"\\n')\n",
    "\n",
    "print('Environment keys configured successfully!')"
]
d['cells'][4]['source'] = source_4

source_6 = [
    "print(\"=== Running Gemini Diagnostics ===\")\n",
    "!python verify_gemini.py\n",
    "\n",
    "print(\"\\n=== Running Groq Diagnostics ===\")\n",
    "!python verify_groq.py\n",
    "\n",
    "print(\"\\n=== Running Qwen Local Diagnostics ===\")\n",
    "!python verify_qwen.py"
]
d['cells'][6]['source'] = source_6

with open("colab_setup.ipynb", "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2)

print("colab_setup.ipynb updated successfully")
