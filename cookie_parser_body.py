import os
import json
import re
import uuid
import time
from urllib.parse import urlsplit

def extract_cookies_all(main_folder, output_folder, output_file_all):
    # Print saying that the cookies are being extracted
    print("Extracting cookies...")

    # Track duplicates only during this run
    seen_entries = set()

    # Loop through all subdirectories in the main folder
    for subdir, dirs, files in os.walk(main_folder):
        for file in files:
            file_lower = file.lower()
            # Process any .txt file (case-insensitive)
            if file_lower.endswith(".txt"):
                file_path = os.path.join(subdir, file)
                file_uuid = str(uuid.uuid4())
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for raw_line in f:
                            line = raw_line.strip()
                            if not line or line.startswith("#"):
                                continue

                            # Netscape cookie format typically uses 7 TAB-separated fields
                            parts = line.split("\t")
                            if len(parts) != 7:
                                continue

                            domain, include_subdomains_str, path, secure_str, expires_str, name, value = parts

                            # Validate domain strictly
                            if not re.fullmatch(r"^\.?[A-Za-z0-9.-]+$", domain):
                                continue

                            include_subdomains = include_subdomains_str.upper() == "TRUE"
                            secure = secure_str.upper() == "TRUE"

                            # Keep expiration exactly as provided (no ms conversion)
                            try:
                                expires_num = int(expires_str)
                            except ValueError:
                                continue
                            expires_value = expires_num

                            # ToDo: If domain is facebook.com, and cookie name is `xs``, find the corresponding `c_user` and append to the value like this: xs|c_user

                            json_entry = json.dumps(
                                {
                                    "machine_id": file_uuid,
                                    "domain": domain,
                                    "include_subdomains": include_subdomains,
                                    "path": path,
                                    "secure": secure,
                                    "expires_epoch_ms": expires_value,
                                    "name": name,
                                    "value": value,
                                },
                                ensure_ascii=False,
                            )

                            if ("arthouse" in domain.lower() or "arthouse" in name.lower() or "arthouse" in value.lower()):
                                continue

                            # If expires_value (epoch ms) is in the past, skip
                            if expires_value < time.time():
                               print(f"Skipping cookie {name} because it has expired on [{expires_value}]")
                               continue

                            # array with blacklisted cookies
                            blacklisted_cookies = ["cf_clearance", "_ga", "_gid", "_gat", "__utma", "__utmb", "__utmc", "__utmz", "__utmv", "_gcl_au", "IDE", "DSID", "ANID", "_fbp", "OptanonConsent", "euconsent-v2", "CookieConsent", "CookieControl", "__hs_opt_out", "__cf_bm", "__cfruid", "cf_ob_info", "cf_use_ob", "language", "dark_mode"]

                            if (name.lower() in blacklisted_cookies):
                                print(f"Skipping cookie {name} because it is blacklisted.")
                                continue

                            # Deduplicate identical cookie records
                            normalized_key = f"{domain}|{name}|{value}|{expires_value}|"
                            if normalized_key not in seen_entries:
                                with open(os.path.join(output_folder, output_file_all), "a", encoding="utf-8") as out_f:
                                    out_f.write(json_entry + "\n")
                                seen_entries.add(normalized_key)
                except UnicodeDecodeError:
                    print(f"Error: Unable to read file {file_path}. Skipping...")
                    continue