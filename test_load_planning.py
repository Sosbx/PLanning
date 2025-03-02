#!/usr/bin/env python3
# Test script to verify planning loading functionality

import os
import json
from datetime import datetime, date

def test_load_planning(filename):
    """Test loading a planning file and check if pre_attributions can be properly accessed."""
    print(f"Testing loading of planning file: {filename}")
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        print("Successfully loaded JSON data")
        
        # Check if pre_attributions exists and is properly formatted
        if 'pre_attributions' in data:
            print("pre_attributions found in data")
            
            # Check if pre_attributions is a dictionary
            if isinstance(data['pre_attributions'], dict):
                print("pre_attributions is a dictionary")
                
                # Try to iterate through pre_attributions
                try:
                    for person_name, attributions in data['pre_attributions'].items():
                        print(f"Person: {person_name}, Attributions count: {len(attributions)}")
                        
                        # Check a few attributions
                        count = 0
                        for key, post in attributions.items():
                            if count < 3:  # Just show a few examples
                                print(f"  Key: {key}, Post: {post}")
                            count += 1
                            
                            # Try to parse the key
                            try:
                                date_str, period_str = key.split('|')
                                date_obj = datetime.fromisoformat(date_str).date()
                                period = int(period_str)
                                print(f"    Parsed as: Date={date_obj}, Period={period}")
                            except Exception as e:
                                print(f"    Error parsing key: {e}")
                                
                        if count > 3:
                            print(f"  ... and {count-3} more attributions")
                    
                    print("Successfully iterated through pre_attributions")
                except Exception as e:
                    print(f"Error iterating through pre_attributions: {e}")
            else:
                print(f"pre_attributions is not a dictionary, it's a {type(data['pre_attributions'])}")
                print(f"Value: {data['pre_attributions']}")
        else:
            print("pre_attributions not found in data")
            
        # Check other important fields
        print("\nOther important fields:")
        for field in ['start_date', 'end_date', 'weekend_validated', 'nl_distributed', 
                     'nl_validated', 'nam_distributed', 'nam_validated', 
                     'combinations_distributed', 'generation_phase']:
            if field in data:
                print(f"{field}: {data[field]}")
            else:
                print(f"{field}: Not found")
                
        return True
    except Exception as e:
        print(f"Error loading planning: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    # If a filename is provided as an argument, test that file
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        print(f"\n=== Testing specified file: {filename} ===")
        if not os.path.exists(filename):
            print(f"Error: File {filename} does not exist")
        else:
            print(f"File {filename} exists, testing...")
            test_load_planning(filename)
    else:
        # Test with auto-save file
        auto_save_file = "auto_save_planning.json"
        if os.path.exists(auto_save_file):
            print("\n=== Testing auto-save file ===")
            test_load_planning(auto_save_file)
        
        # Test with any P*.json files in the current directory
        planning_files = [f for f in os.listdir() if f.startswith("P ") and f.endswith(".json")]
        for planning_file in planning_files:
            print(f"\n=== Testing planning file: {planning_file} ===")
            test_load_planning(planning_file)
