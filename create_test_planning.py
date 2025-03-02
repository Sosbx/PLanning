#!/usr/bin/env python3
# Script to create a test planning file with proper pre_attributions format

import os
import json
from datetime import datetime, date, timedelta

# Create a simple planning structure
planning_data = {
    "start_date": date.today().isoformat(),
    "end_date": (date.today() + timedelta(days=30)).isoformat(),
    "weekend_validated": False,
    "nl_distributed": True,
    "nl_validated": True,
    "nam_distributed": True,
    "nam_validated": True,
    "combinations_distributed": True,
    "generation_phase": "combinations",
    "pre_attributions": {
        "DOCTOR1": {
            f"{date.today().isoformat()}|1": "ML",
            f"{(date.today() + timedelta(days=1)).isoformat()}|2": "AC"
        },
        "DOCTOR2": {
            f"{date.today().isoformat()}|3": "NL",
            f"{(date.today() + timedelta(days=2)).isoformat()}|1": "MC"
        }
    },
    "days": [
        {
            "date": date.today().isoformat(),
            "slots": [
                {
                    "start_time": datetime.now().replace(hour=8, minute=0).isoformat(),
                    "end_time": datetime.now().replace(hour=18, minute=0).isoformat(),
                    "site": "Site A",
                    "slot_type": "Regular",
                    "abbreviation": "ML",
                    "assignee": "DOCTOR1"
                }
            ]
        }
    ]
}

# Save the planning to a test file
test_filename = "test_planning.json"
with open(test_filename, 'w') as f:
    json.dump(planning_data, f, indent=2)

print(f"Test planning saved to {test_filename}")

# Now test loading the file
with open(test_filename, 'r') as f:
    loaded_data = json.load(f)

print("\nLoaded planning data:")
print(f"Start date: {loaded_data['start_date']}")
print(f"End date: {loaded_data['end_date']}")
print(f"Weekend validated: {loaded_data['weekend_validated']}")

# Check pre_attributions
if 'pre_attributions' in loaded_data:
    print("\nPre-attributions:")
    if isinstance(loaded_data['pre_attributions'], dict):
        print("pre_attributions is a dictionary (correct format)")
        for doctor, attributions in loaded_data['pre_attributions'].items():
            print(f"Doctor: {doctor}")
            for key, post in attributions.items():
                print(f"  {key}: {post}")
                # Test parsing the key
                date_str, period_str = key.split('|')
                date_obj = datetime.fromisoformat(date_str).date()
                period = int(period_str)
                print(f"    Parsed as: Date={date_obj}, Period={period}")
    else:
        print(f"pre_attributions is not a dictionary, it's a {type(loaded_data['pre_attributions'])}")
        print(f"Value: {loaded_data['pre_attributions']}")
else:
    print("pre_attributions not found in data")
