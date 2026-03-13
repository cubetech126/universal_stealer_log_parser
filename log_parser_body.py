import os
import json
import re
from urllib.parse import urlsplit

def extract_passwords_all(main_folder, output_folder, output_file_all):
    # Print saying that the passwords are being extracted
    print("Extracting passwords...")

    # Track duplicates only during this run
    seen_entries = set()

    # Supported filenames (case-insensitive)
    supported_files = {
        'All_Passwords.txt',
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
                    try:
                        with open(file_path, "r", encoding="latin-1") as f:
                            contents = f.read()
                    except Exception:
                        print(f"Error: Unable to read file {file_path}. Skipping...")
                        continue

                # Split entries by blank lines or heavy separators (e.g., lines of ━, =, -, _ or *)
                entries = re.split(r'(?:\n\n|\n[━=\-_*]{5,}\n)', contents)

                for entry in entries:
                    if not entry.strip():
                        continue

                    records = []
                    current = {}

                    for line in entry.strip().split("\n"):
                        if ":" not in line:
                            continue
                        key, value = line.split(":", 1)
                        key = key.strip()
                        if key.startswith('"') and key.endswith('"'):
                            key = key[1:-1]
                        key = key.lower()
                        value = value.strip().rstrip(",")
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]

                        if key in ("soft", "application", "browser"):
                            if current.get("url"):
                                records.append(current)
                                current = {}
                            current["soft"] = value
                        elif key in ("url", "host", "hostname"):
                            if current.get("url"):
                                records.append(current)
                                current = {"soft": current.get("soft", "")}
                            current["url"] = value
                        elif key in ("user", "login", "username", "user login"):
                            current["user"] = value
                        elif key in ("pass", "password", "user password"):
                            current["password"] = value

                    if current.get("url"):
                        records.append(current)

                    for rec in records:
                        url = rec.get("url", "")
                        user = rec.get("user", "")
                        password = rec.get("password", "")

                        if not (url and user and password):
                            continue

                        if url.startswith("android"):
                            after_at = url.split("@", 1)[-1] if "@" in url else url[len("android://"):]
                            pkg = after_at.split("/", 1)[0].strip("/")
                            pkg = re.sub(r"[^A-Za-z0-9._\-]", "", pkg)
                            url = f"android://{pkg}" if pkg else url.strip()
                        else:
                            try:
                                url_components = urlsplit(url)
                                url = url_components.geturl()
                            except ValueError:
                                url = url.strip()

                        formatted_entry = f'"{url}"|{user}|{password}\n'
                        normalized_entry = formatted_entry.rstrip("\n")
                        json_entry = json.dumps({"url": url, "email": user, "password": password}, ensure_ascii=False)

                        if "NOT_SAVED" in password:
                            continue
                        elif any(
                            kw in val
                            for val in (url.lower(), user.lower(), password.lower())
                            for kw in ("arthouse", "cloud_arthouse", "@cloud_arthouse", "@arthouse_full_bot", "u2fp29gkufkzz", "5sbwt2_xek3mgjh", "ih73k1u", "rrntiqwtg0fjztkx")
                        ):
                            continue

                        if normalized_entry not in seen_entries:
                            with open(os.path.join(output_folder, output_file_all), "a", encoding="utf-8") as f:
                                f.write(json_entry + "\n")
                            seen_entries.add(normalized_entry)