import pandas as pd
import numpy as np
import csv
from collections import deque
import time
from tqdm import tqdm

# --- CONFIGURATION ---
TRACE_FILE = 'azure_trace_events_2hrs_scaled.csv'
OUTPUT_DATASET_FILE = 'edge_node_simulation_from_trace_scaled.csv'
TIME_STEP = 0.1

# --- <<< NEW: Processor Speed Scaling Factor >>> ---
# A factor of 100 means a 0.5s task takes 0.005s. Tune this to get "hills and valleys".
# Start with a high value like 200 and adjust down if the queue is always empty.
PROCESSOR_SPEED_FACTOR = 200 

# --- REUSABLE SIMULATION COMPONENTS ---

class Task:
    def __init__(self, task_id, duration, speed_factor):
        self.id = task_id
        # --- MODIFIED: The task's duration is scaled at creation ---
        self.base_duration = duration # Keep original for profiling
        self.duration = duration / speed_factor
    def get_load(self): return 0.8

class TaskProcessor:
    def __init__(self, time_step):
        self.current_task = None; self.time_on_task = 0
        self.time_step = time_step; self.cpu_load = 0.0
    def is_idle(self): return self.current_task is None
    def start_new_task(self, task):
        self.current_task = task; self.time_on_task = 0
    def process_tick(self):
        if self.current_task:
            self.time_on_task += self.time_step
            self.cpu_load = self.current_task.get_load()
            if self.time_on_task >= self.current_task.duration - (self.time_step / 2):
                finished_task_id = self.current_task.id
                # --- MODIFIED: We profile the ORIGINAL duration, not the scaled one ---
                original_duration = self.current_task.base_duration
                self.current_task = None; self.cpu_load = 0.0
                return finished_task_id, original_duration
        else: self.cpu_load = 0.0
        return None, None

class TraceTaskGenerator:
    # ... (This class is unchanged) ...
    def __init__(self, trace_filepath, speed_factor):
        print(f"Loading event trace from '{trace_filepath}'..."); self.trace_df = pd.read_csv(trace_filepath)
        self.event_index = 0; self.speed_factor = speed_factor; print("Trace loaded.")
    def generate_tasks(self, current_time):
        arrived_tasks = []
        while (self.event_index < len(self.trace_df) and 
               self.trace_df.iloc[self.event_index]['arrival_time'] <= current_time):
            event = self.trace_df.iloc[self.event_index]
            new_task = Task(task_id=event['task_type'], duration=event['duration'], speed_factor=self.speed_factor)
            arrived_tasks.append(new_task); self.event_index += 1
        return arrived_tasks

# --- The Main Simulation Orchestrator ---
class Simulation:
    def __init__(self, trace_filepath, output_filepath, time_step, speed_factor):
        self.output_filename = output_filepath; self.time_step = time_step
        self.generator = TraceTaskGenerator(trace_filepath, speed_factor)
        self.task_queue = deque(); self.processor = TaskProcessor(self.time_step)
        self.all_task_types = self.generator.trace_df['task_type'].unique()
        self.task_profiler = {task_id: [1.0, 1] for task_id in self.all_task_types}
        self.duration = self.generator.trace_df['arrival_time'].max() + 60
        print(f"Initialized a single-core processor with a speed factor of {speed_factor}x.")

    def get_current_avg_exec_time(self, task_id):
        total_time, count = self.task_profiler.get(task_id, (1.0, 1)); return total_time / count

    def run(self):
        print(f"\nStarting trace-driven simulation for {self.duration:.2f} seconds...")
        print(f"Logging structured data to '{self.output_filename}'")
        with open(self.output_filename, 'w', newline='') as csvfile:
            # ... (CSV header code is the same) ...
            base_fieldnames = ['timestamp', 'queue_length', 'cpu_load', 'last_task_id_arrived']
            profiler_fieldnames = [f'avg_exec_{task_id}' for task_id in self.all_task_types]
            fieldnames = base_fieldnames + profiler_fieldnames
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames); writer.writeheader()

            for i in tqdm(range(int(self.duration / self.time_step))):
                current_time = i * self.time_step
                new_tasks = self.generator.generate_tasks(current_time)
                task_id_arrived = 'None'
                if new_tasks:
                    self.task_queue.extend(new_tasks); task_id_arrived = new_tasks[-1].id

                finished_task_id, original_duration = self.processor.process_tick()
                if finished_task_id:
                    self.task_profiler[finished_task_id][0] += original_duration
                    self.task_profiler[finished_task_id][1] += 1

                if self.processor.is_idle() and self.task_queue:
                    task_to_process = self.task_queue.popleft()
                    self.processor.start_new_task(task_to_process)
                
                log_row = {'timestamp': round(current_time, 2), 'queue_length': len(self.task_queue),
                           'cpu_load': round(self.processor.cpu_load, 4), 'last_task_id_arrived': task_id_arrived}
                for task_id in self.all_task_types:
                    log_row[f'avg_exec_{task_id}'] = round(self.get_current_avg_exec_time(task_id), 6)
                writer.writerow(log_row)
        
        print("\n--- Trace-driven simulation finished! ---")
        print(f"Structured dataset is ready in '{self.output_filename}'.")

if __name__ == "__main__":
    sim = Simulation(trace_filepath=TRACE_FILE, output_filepath=OUTPUT_DATASET_FILE, 
                     time_step=TIME_STEP, speed_factor=PROCESSOR_SPEED_FACTOR)
    sim.run()