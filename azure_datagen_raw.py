import pandas as pd
import numpy as np
import pickle
from tqdm import tqdm

# --- CONFIGURATION ---
INVOCATIONS_FILE = 'invocations_per_function_md.anon.d01.csv'
OUTPUT_TRACE_FILE = 'azure_trace_events_2hrs_scaled.csv' # New filename
DURATION_IN_MINUTES = 120

# --- <<< NEW: Workload Scaling Factor >>> ---
# We will only use 5% of the invocations from the original trace.
# You can tune this value (e.g., 0.1 for 10%, 0.02 for 2%).
LOAD_SCALE_FACTOR = 0.000995

def generate_event_trace(invocations_file):
    print("Step 1: Loading pre-processed duration map and top functions set...")
    # ... (loading code is the same) ...
    try:
        with open('duration_map.pkl', 'rb') as f: duration_map = pickle.load(f)
        with open('top_functions.pkl', 'rb') as f: top_functions_set = pickle.load(f)
    except FileNotFoundError:
        print("Error: 'duration_map.pkl' or 'top_functions.pkl' not found. Please run script 1 first."); return

    print(f"Loaded data for {len(top_functions_set)} top functions.")
    print(f"--- Applying a load scale factor of {LOAD_SCALE_FACTOR*100:.1f}% ---")

    print(f"\nStep 2: Reading invocations data from '{invocations_file}'...")
    df_invocations = pd.read_csv(invocations_file)

    all_events = []
    print(f"\nStep 3: Generating events for the first {DURATION_IN_MINUTES} minutes...")
    for index, row in tqdm(df_invocations.iterrows(), total=df_invocations.shape[0]):
        func_tuple = (row['HashApp'], row['HashFunction'])
        if func_tuple not in top_functions_set: continue
        duration = duration_map.get(func_tuple)
        if duration is None: continue
        task_type_id = f"{func_tuple[0]}_{func_tuple[1]}"

        for minute_col in range(1, DURATION_IN_MINUTES + 1):
            original_invocation_count = row[str(minute_col)]
            
            if original_invocation_count > 0:
                # --- <<< MODIFIED: Apply the scaling factor >>> ---
                # We use np.random.binomial to probabilistically thin the count.
                # This is more robust than just multiplying, especially for small counts.
                scaled_invocation_count = np.random.binomial(original_invocation_count, LOAD_SCALE_FACTOR)

                if scaled_invocation_count > 0:
                    interval_start_sec = (minute_col - 1) * 60
                    random_offsets = np.random.uniform(0, 60, size=scaled_invocation_count)
                    arrival_times = interval_start_sec + random_offsets
                    for t_arrival in arrival_times:
                        all_events.append((t_arrival, task_type_id, duration))

    print(f"\nGenerated a total of {len(all_events)} scaled events.")

    # ... (Sorting and saving code is the same) ...
    print("\nStep 4: Sorting all events by arrival time..."); all_events.sort(key=lambda x: x[0])
    print(f"\nStep 5: Saving the final scaled trace to '{OUTPUT_TRACE_FILE}'...")
    pd.DataFrame(all_events, columns=['arrival_time', 'task_type', 'duration']).to_csv(OUTPUT_TRACE_FILE, index=False)
    print("\n--- Scaled Event Trace Generation Complete ---")


if __name__ == "__main__":
    generate_event_trace(INVOCATIONS_FILE)