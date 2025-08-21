import os
import json
import re
from urllib.parse import urlsplit

def extract_passwords_all(main_folder, output_folder, output_file_all):
    # Track duplicates only during this run
    seen_entries = set()

    # Supported filenames (case-insensitive)
    supported_files = {
        "passwords.txt",
        "password list.txt",
        "_allpasswords_list.txt",
        "all passwords.txt",
        "found_credentials.txt",
        "credentials.txt",
        # Common variants with spaces/underscore/case
        "_allpasswords_list.txt",
        "password list.txt",
        "all passwords.txt",
        # Mixed case variants seen in other logs
        "password list.txt",
        "passwords.txt",
        "all passwords.txt",
    }

    # Loop through all subdirectories in the main folder
    for subdir, dirs, files in os.walk(main_folder):
        for file in files:
            file_lower = file.lower()
            # Include explicit case-sensitive names from older Racoon logs
            if (file_lower in supported_files):
                file_path = os.path.join(subdir, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        contents = f.read()
                except UnicodeDecodeError:
                    print(f"Error: Unable to read file {file_path}. Skipping...")
                    continue

                # Split entries by blank lines or heavy separators (e.g., lines of ━, =, -, _ or *)
                entries = re.split(r'(?:\n\n|\n[━=\-_*]{5,}\n)', contents)

                for entry in entries:
                    if not entry.strip():
                        continue
                    lines = entry.strip().split("\n")

                    url = ""
                    user = ""
                    password = ""

                    for line in lines:
                        if ":" not in line:
                            continue
                        key, value = line.split(":", 1)
                        key = key.strip().lower()
                        value = value.strip()

                        if key in ("url", "host", "hostname"):
                            url = value
                        elif key in ("user", "login", "username", "user login"):
                            user = value
                        elif key in ("pass", "password", "user password"):
                            password = value

                    if url and user and password:
                        if url.startswith("android"):
                            package_name = url.split("@")[-1]
                            package_name = package_name.replace("-", "").replace("_", "").replace(".", "")
                            package_name = ".".join(package_name.split("/")[::-1])
                            package_name = ".".join(package_name.split(".")[::-1])
                            url = f"{package_name}android.app"
                        else:
                            url_components = urlsplit(url)
                            url = url_components.geturl()

                        formatted_entry = f'"{url}"|{user}|{password}\n'
                        normalized_entry = formatted_entry.rstrip("\n")
                        json_entry = json.dumps({"url": url, "email": user, "password": password}, ensure_ascii=False)

                        # Skip undesired entries
                        if "NOT_SAVED" in password:
                            continue
                        elif (
                            "arthouse" in url.lower()
                            or "arthouse" in user.lower()
                            or "arthouse" in password.lower()
                        ):
                            continue

                        if normalized_entry not in seen_entries:
                            with open(os.path.join(output_folder, output_file_all), "a", encoding="utf-8") as f:
                                f.write(json_entry + "\n")
                            seen_entries.add(normalized_entry)