import os
import json

def count_json_files(directory_path):
    """
    Counts "empty" JSON files and total JSON files in a given directory.
    A JSON file is considered "empty" if:
    1. Its size is 0 bytes.
    2. OR its content is exactly '{}'.
    """
    empty_json_count = 0
    total_json_files = 0 # Counter for all .json files

    if not os.path.isdir(directory_path):
        print(f"Error: Directory '{directory_path}' not found.")
        return 0, 0

    print(f"Checking for JSON files in: {directory_path}\n")

    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            total_json_files += 1 # Increment for every .json file
            filepath = os.path.join(directory_path, filename)
            if os.path.isfile(filepath):
                is_empty = False
                try:
                    file_size = os.path.getsize(filepath)
                    if file_size == 0:
                        print(f"- Found 0-byte empty JSON: {filename}")
                        is_empty = True
                    else:
                        # Try to parse as JSON, check if it's an empty object
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = json.load(f)
                        if content == {}:
                            print(f"- Found JSON file with content {{}}: {filename} (size: {file_size} bytes)")
                            is_empty = True
                        # else:
                            # print(f"  Skipping non-empty JSON content: {filename}")
                except json.JSONDecodeError:
                    # File is not 0 bytes, but could not be parsed as JSON (e.g., malformed)
                    # or it was parsed but wasn't an empty dict and we didn't print the skip message above.
                    # For our definition of "empty", a malformed JSON (that isn't 0 bytes) is not counted.
                    # We already handled the file_size == 0 case.
                    # If file_size > 0 and it's not "{}", we don't count it.
                    # print(f"  Skipping malformed or non-{{}} JSON: {filename}")
                    pass # Not matching our "empty" criteria
                except OSError as e:
                    print(f"Error accessing file {filename}: {e}")
                
                if is_empty:
                    empty_json_count += 1
            
    return empty_json_count, total_json_files

if __name__ == "__main__":
    output_dir = "/ssd1/zhen/tablellm/test_results"
    empty_count, total_count = count_json_files(output_dir)
    print(f"\n--- Summary ---")
    print(f"Total number of JSON files found: {total_count}")
    print(f"Number of empty JSON files (0-byte or content '{{}}'): {empty_count}")
