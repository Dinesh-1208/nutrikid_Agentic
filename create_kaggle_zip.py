import zipfile
import os

def create_zip():
    targets = ['data', 'evaluation', 'llm', 'planner', 'rag', 'main.py', 'verify_gemini.py', 'verify_qwen.py', 'requirements.txt', 'colab_setup.ipynb']
    
    with zipfile.ZipFile('project_kaggle.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        for target in targets:
            if os.path.isfile(target):
                zipf.write(target, target.replace(os.sep, '/'))
            elif os.path.isdir(target):
                for root, _, files in os.walk(target):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Ensure forward slashes in archive name for Kaggle compatibility!
                        archive_name = file_path.replace(os.sep, '/')
                        zipf.write(file_path, archive_name)

if __name__ == '__main__':
    create_zip()
    print("Created project_kaggle.zip successfully!")
