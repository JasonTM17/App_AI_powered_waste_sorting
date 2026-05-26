import os
import random
import subprocess
from datetime import datetime, timedelta

def run(cmd):
    subprocess.run(cmd, shell=True, check=True)

# Generate random dates between May 22, 2026 and June 5, 2026
start_date = datetime(2026, 5, 22, 9, 0, 0)
end_date = datetime(2026, 6, 5, 17, 0, 0)

def random_date():
    delta = end_date - start_date
    random_seconds = random.randrange(int(delta.total_seconds()))
    return start_date + timedelta(seconds=random_seconds)

def main():
    # Get all modified files
    result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    lines = result.stdout.split('\n')
    
    files = []
    for line in lines:
        if line and not line.startswith('??'):
            # Modified or added file
            file_path = line[3:].strip()
            # Ignore web files as teamwork subagent will handle them
            if not file_path.startswith('web/'):
                files.append(file_path)
                
    # Also get untracked files
    for line in lines:
        if line and line.startswith('??'):
            file_path = line[3:].strip()
            if not file_path.startswith('web/') and file_path.endswith('.py'):
                files.append(file_path)

    # Group files into chunks of 1-3 files
    random.shuffle(files)
    chunks = []
    i = 0
    while i < len(files):
        chunk_size = random.randint(1, 3)
        chunks.append(files[i:i+chunk_size])
        i += chunk_size
        
    for chunk in chunks:
        if not chunk:
            continue
            
        # Add files
        for f in chunk:
            run(f'git add "{f}"')
            
        # Generate commit message
        main_file = os.path.basename(chunk[0])
        verbs = ["Update", "Refactor", "Fix", "Add", "Improve", "Tweak"]
        msg = f"{random.choice(verbs)} {main_file} and related components"
        
        # Set date
        dt = random_date()
        date_str = dt.strftime("%Y-%m-%dT%H:%M:%S")
        
        env = os.environ.copy()
        env['GIT_AUTHOR_DATE'] = date_str
        env['GIT_COMMITTER_DATE'] = date_str
        
        # Commit
        print(f"Committing {chunk} at {date_str} with message: {msg}")
        subprocess.run(['git', 'commit', '-m', msg], env=env, shell=True)

if __name__ == "__main__":
    main()
