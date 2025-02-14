import os

def combine_files(project_dir, output_file):
    excluded_items = {'app_data.pkl', 'icons','dist', 'logger_config.py','logs','custom_posts.pkl','main.cpython-312-darwin.so','main.c','Tests', 'main.spec','setup.py', 'build', 'test', 'build/main', '.DS_Store', 'exportsTxt.py', 'test.py','utils', 'app.log', '__pycache__','venv', 'planningt.txt', 'SAVE base.txt', 'SAV 2.txt','SAV3.txt'}
    
    with open(output_file, "w", encoding='utf-8') as outfile:
        for root, dirs, files in os.walk(project_dir):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in excluded_items]
            
            for file in files:
                if file in excluded_items:
                    continue
                
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding='utf-8') as infile:
                        relative_path = os.path.relpath(file_path, project_dir)
                        outfile.write(f"# {relative_path}\n\n")
                        outfile.write(infile.read())
                        outfile.write("\n\n")
                except UnicodeDecodeError:
                    print(f"Skipping file due to encoding issues: {file_path}")

project_directory = "/Users/arkane/Documents/Planning"
output_file_path = "/Users/arkane/Documents/Planning/planningt.txt"
combine_files(project_directory, output_file_path)
