import re
import datetime

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

# Generate a timestamp in the desired format
timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Using a set to track seen lines and eliminate duplicates.
seen_lines = set()

# Open the input file and create an output SQL file.
with open(file_path, 'r') as infile, open('output.sql', 'w') as outfile:
    for raw_line in infile:
        line = raw_line.strip()
        if not line:  # Skip empty lines
            print ("[SKIP] - Empty line:", line)
            continue

        # Skip if the line is a duplicate
        if line in seen_lines:
            print ("[SKIP] - Duplicate line:", line)
            continue
        seen_lines.add(line)

        # Use a regular expression to capture the URL (inside quotes) and the remaining data.
        match = re.match(r'"([^"]+)":(.+)', line)
        if match:
            url = sql_escape(match.group(1))
            data = sql_escape(match.group(2))
            # Write an INSERT statement; adjust table name and columns as needed.
            outfile.write(f"INSERT INTO logs (url, data, created_at, updated_at) VALUES ('{url}', '{data}', '{timestamp}', '{timestamp}');\n")
        else:
            print("Line didn't match expected format:", line)