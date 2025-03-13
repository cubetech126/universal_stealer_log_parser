import re

# Prompt the user for the file path.
file_path = input('Enter the file path: ')

# Open the input file and create an output SQL file.
with open(file_path, 'r') as infile, open('output.sql', 'w') as outfile:
    for line in infile:
        # Use a regular expression to capture the URL (inside quotes) and the remaining data.
        match = re.match(r'"([^"]+)":(.+)', line.strip())
        if match:
            url = match.group(1).replace("'", "''")  # Escape single quotes for SQL
            data = match.group(2).replace("'", "''")
            outfile.write(f"INSERT INTO logs (url, data) VALUES ('{url}', '{data}');\n")