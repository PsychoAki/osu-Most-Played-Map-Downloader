import requests
import time
import os
import re
from tqdm import tqdm

def sanitize_filename(name: str) -> str:
    # Remove characters invalid in Windows filenames: \ / : * ? " < > |
    return re.sub(r'[\\/*?:"<>|]', '', name)

def prompt_yes_no(prompt: str, default: str = "n") -> bool:
    while True:
        choice = input(f"{prompt} (y/n) [default: {default}]: ").strip().lower()
        if choice == '':
            choice = default
        if choice in ['y', 'n']:
            return choice == 'y'
        print("Please enter 'y' or 'n'.")

def download_single_beatmap(beatmapset_id, song_title, options):
    headers = {
        "Accept": "application/x-osu-beatmap-archive",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0",
    }

    # Build query parameters according to options
    params = {}
    # Options keys must be lowercase as per docs (noBg, noVideo, noHitsound, noStoryboard)
    # Convert bools to 'true' or 'false' strings
    for key in ['noHitsound', 'noStoryboard', 'noBg', 'noVideo']:
        param_key = key.lower()
        params[param_key] = 'true' if options.get(param_key, False) else 'false'

    url = f"https://api.nerinyan.moe/d/{beatmapset_id}"
    try:
        with requests.get(url, headers=headers, params=params, stream=True) as response:
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                filename = f"{beatmapset_id} - {sanitize_filename(song_title)}.osz"
                with open(filename, "wb") as f, tqdm(
                    total=total_size, unit='B', unit_scale=True, unit_divisor=1024,
                    desc=filename, ascii=True
                ) as bar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bar.update(len(chunk))
                return True
            else:
                print(f"Failed to download {beatmapset_id} - {song_title}: HTTP {response.status_code}")
                return False
    except Exception as e:
        print(f"Exception during download of {beatmapset_id} - {song_title}: {e}")
        return False

def download_beatmaps(beatmaps: list[dict], options):
    failed_downloads = []
    total = len(beatmaps)
    for i, beatmap in enumerate(beatmaps, 1):
        # Defensive key access
        beatmapset = beatmap.get("beatmapset") or beatmap.get("beatmap")
        if not beatmapset:
            print(f"Skipping beatmap with missing beatmapset data at index {i}")
            failed_downloads.append(None)
            continue

        beatmapset_id = beatmapset.get("id") or beatmapset.get("beatmapset_id")
        song_title = beatmapset.get("title", "Unknown Title")
        if not beatmapset_id:
            print(f"Skipping beatmap with missing id at index {i}")
            failed_downloads.append(None)
            continue

        print(f"Downloading ({i}/{total}): {beatmapset_id} - {song_title}")
        success = download_single_beatmap(beatmapset_id, song_title, options)
        if not success:
            failed_downloads.append(beatmapset_id)
        time.sleep(1)  # Rate limit delay

    if failed_downloads:
        with open("failed_downloads.txt", "w") as f:
            for fail in failed_downloads:
                if fail:
                    f.write(str(fail) + "\n")
        print(f"Failed downloads saved to failed_downloads.txt")

def retrieve_most_played_beatmaps(user_id: str, limit: int, offset: int = 0) -> list[dict]:
    beatmaps = []
    per_page = 10
    for current_offset in range(offset, offset + limit, per_page):
        try:
            url = f"https://osu.ppy.sh/users/{user_id}/beatmapsets/most_played?limit={per_page}&offset={current_offset}"
            response = requests.get(url)
            if response.status_code == 429:
                print(f"Rate limited at offset {current_offset}. Waiting 10 seconds...")
                time.sleep(10)
                continue
            elif response.status_code != 200:
                print(f"Skipping offset {current_offset} (status code: {response.status_code})")
                continue

            data = response.json()
            if not isinstance(data, list):
                print(f"Unexpected data structure at offset {current_offset}, skipping")
                continue

            beatmaps.extend(data)
            print(f"Fetched {len(data)} beatmaps at offset {current_offset}")

            # Sleep to avoid rate limit
            time.sleep(1)
        except Exception as e:
            print(f"Error fetching beatmaps at offset {current_offset}: {e}")
    return beatmaps

def main():
    print("osu! Beatmap Downloader by API")
    user_id = input("Enter your osu! user ID: ").strip()
    while not user_id.isdigit():
        user_id = input("Invalid input. Please enter numeric osu! user ID: ").strip()

    try:
        limit = int(input("How many beatmaps to download? (e.g. 100): ").strip())
    except:
        limit = 10
        print("Invalid input. Defaulting to 10 beatmaps.")

    try:
        offset = int(input("Start from offset? (0 for beginning): ").strip())
    except:
        offset = 0
        print("Invalid input. Starting from offset 0.")

    print("\nSelect download options (y/n):")
    options = {}
    options['nohitsound'] = prompt_yes_no("NoHitsound", "n")
    options['nostoryboard'] = prompt_yes_no("NoStoryboard", "n")
    options['nobg'] = prompt_yes_no("noBg", "n")
    options['novideo'] = prompt_yes_no("noVideo", "y")

    beatmaps = retrieve_most_played_beatmaps(user_id, limit, offset)
    if not beatmaps:
        print("No beatmaps found. Exiting.")
        return

    download_beatmaps(beatmaps, options)

if __name__ == "__main__":
    main()
