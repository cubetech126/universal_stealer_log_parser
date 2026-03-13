import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BINARY_CHECK_SIZE = 8192
PREVIEW_MAX_LEN = 120
NULL_BYTE = b"\x00"
WORKER_COUNT = os.cpu_count() * 4 or 16


def is_binary(filepath):
    try:
        with open(filepath, "rb") as f:
            return NULL_BYTE in f.read(BINARY_CHECK_SIZE)
    except (OSError, PermissionError):
        return True


def collect_files(root):
    paths = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            paths.append(os.path.join(dirpath, name))
    return paths


def process_file(filepath, keyword, keyword_bytes, pattern=None):
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(BINARY_CHECK_SIZE)
            if NULL_BYTE in chunk:
                return filepath, None, True

            rest = f.read()
            raw = chunk + rest

        if pattern is None and keyword_bytes not in raw:
            return filepath, [], False

        hits = []
        for line_num, line in enumerate(raw.split(b"\n"), start=1):
            try:
                decoded = line.decode("utf-8", errors="replace").strip()
            except Exception:
                continue

            if pattern is not None:
                match = pattern.search(decoded)
                if not match:
                    continue
            else:
                if keyword_bytes not in line:
                    continue

            if len(decoded) > PREVIEW_MAX_LEN:
                if pattern is not None:
                    idx = match.start()
                else:
                    idx = decoded.find(keyword)
                    if idx == -1:
                        idx = 0
                start = max(0, idx - PREVIEW_MAX_LEN // 3)
                end = min(len(decoded), start + PREVIEW_MAX_LEN)
                preview = ("..." if start > 0 else "") + decoded[start:end] + ("..." if end < len(decoded) else "")
            else:
                preview = decoded
            hits.append((line_num, preview))
        return filepath, hits, False

    except (OSError, PermissionError):
        return filepath, None, True


def format_progress(current, total, width=40):
    pct = current / total if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"\r  [{bar}] {current:>{len(str(total))}}/{total} files processed"


def progress_printer(counter, total, done_event):
    while not done_event.is_set():
        sys.stdout.write(format_progress(counter[0], total))
        sys.stdout.flush()
        time.sleep(0.05)
    sys.stdout.write(format_progress(total, total))
    sys.stdout.flush()


def ask_yes_no(prompt):
    return input(prompt).strip().lower() in ("y", "yes")


def main():
    keyword = input("\n  Enter keyword / regex pattern to search for: ").strip()
    if not keyword:
        print("  No keyword provided. Exiting.")
        return

    use_regex = ask_yes_no("  Use regex mode? (y/n): ")
    pattern = None
    if use_regex:
        try:
            pattern = re.compile(keyword)
        except re.error as e:
            print(f"  Invalid regex pattern: {e}")
            return

    search_path = input("  Enter directory path to search: ").strip()
    if not os.path.isdir(search_path):
        print(f"  '{search_path}' is not a valid directory. Exiting.")
        return

    skip_history = ask_yes_no("  Ignore files containing 'history' in the name? (y/n): ")
    skip_cookies = ask_yes_no("  Ignore files containing 'cookies' in the name? (y/n): ")
    skip_autofill = ask_yes_no("  Ignore files with 'Autofill' in the path? (y/n): ")

    print(f"\n  Collecting files in '{search_path}'...")
    all_files = collect_files(search_path)

    pre_filter = len(all_files)
    if skip_history or skip_cookies or skip_autofill:
        filtered = []
        for fp in all_files:
            name_lower = os.path.basename(fp).lower()
            if skip_history and "history" in name_lower:
                continue
            if skip_cookies and "cookies" in name_lower:
                continue
            if skip_autofill and "autofill" in fp.lower():
                continue
            filtered.append(fp)
        all_files = filtered
        print(f"  Filtered out {pre_filter - len(all_files):,} files.")
    total = len(all_files)

    if total == 0:
        print("  No files found. Exiting.")
        return

    mode_label = "regex" if use_regex else "literal"
    print(f"  Found {total:,} files. Scanning for '{keyword}' ({mode_label}) with {WORKER_COUNT} threads...\n")

    keyword_bytes = keyword.encode("utf-8", errors="replace")
    results = {}
    skipped = 0
    counter = [0]
    lock = threading.Lock()

    done_event = threading.Event()
    progress_thread = threading.Thread(target=progress_printer, args=(counter, total, done_event), daemon=True)
    progress_thread.start()

    t_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=WORKER_COUNT) as pool:
        futures = {pool.submit(process_file, fp, keyword, keyword_bytes, pattern): fp for fp in all_files}

        for future in as_completed(futures):
            filepath, hits, was_binary = future.result()
            with lock:
                counter[0] += 1
                if was_binary:
                    skipped += 1
                elif hits:
                    results[filepath] = hits

    done_event.set()
    progress_thread.join()
    elapsed = time.perf_counter() - t_start

    print("\n")

    if not results:
        print(f"  No matches found for '{keyword}'.")
    else:
        match_count = sum(len(h) for h in results.values())
        print(f"  Found {match_count:,} match(es) across {len(results):,} file(s):\n")
        print("  " + "─" * 70)

        for filepath, hits in results.items():
            print(f"\n  📄 {filepath}")
            for line_num, preview in hits:
                if pattern is not None:
                    highlighted = pattern.sub(lambda m: f"\033[91m{m.group()}\033[0m", preview)
                else:
                    highlighted = preview.replace(keyword, f"\033[91m{keyword}\033[0m")
                print(f"     Line {line_num}: {highlighted}")

        print("\n  " + "─" * 70)

    scanned = total - skipped
    print(f"\n  Stats: {total:,} total | {skipped:,} binary skipped | {scanned:,} scanned | {len(results):,} matched | {elapsed:.2f}s\n")


if __name__ == "__main__":
    main()
