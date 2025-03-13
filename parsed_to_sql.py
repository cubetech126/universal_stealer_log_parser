import re

# Prompt the user for the file path.
file_path = input('Enter the file path: ')

def sql_escape(value):
    """
    Escapes characters in a string for safe SQL insertion.
    First escapes backslashes, then single quotes.
    """
    # Escape backslashes
    value = value.replace('\\', '\\\\')
    # Escape single quotes
    value = value.replace("'", "''")
    return value

# Open the input file and create an output SQL file.
with open(file_path, 'r') as infile, open('output.sql', 'w') as outfile:
    for line in infile:
        line = line.strip()
        if not line:  # Skip empty lines
            continue

        # Use a regular expression to capture the URL (inside quotes) and the remaining data.
        match = re.match(r'"([^"]+)":(.+)', line)
        if match:
            url = sql_escape(match.group(1))
            data = sql_escape(match.group(2))
            # Write an INSERT statement; adjust table name and columns as needed.
            outfile.write(f"INSERT INTO logs (url, data) VALUES ('{url}', '{data}');\n")
        else:
            print("Line didn't match expected format:", line)