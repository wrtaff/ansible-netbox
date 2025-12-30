import json
import sys

input_file = "tmp/wikitext_raw.json"
output_file = "tmp/wikitext.txt"

with open(input_file, "r") as f:
    data = json.load(f)

page_id = list(data["query"]["pages"].keys())[0]
wikitext = data["query"]["pages"][page_id]["revisions"][0]["*"]

with open(output_file, "w") as f:
    f.write(wikitext)

print(f"Wikitext extracted to {output_file}")