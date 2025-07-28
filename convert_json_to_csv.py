import json
import csv

# Step 1: JSON फाइल पढ़ना
with open('full_instruments.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Step 2: CSV फाइल में लिखना
with open('instruments_output.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)

    # Column headers auto detect (first item से key निकालना)
    headers = list(data[0].keys())
    writer.writerow(headers)

    # Row data
    for item in data:
        row = [item.get(col, '') for col in headers]
        writer.writerow(row)

print("✅ CSV फाइल तैयार: instruments_output.csv")
