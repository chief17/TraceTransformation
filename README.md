# TraceTransformation
Step by Step Guide to Transform Azure Function Invocation trace to be used in Edge Computing Scenarios
Here is a tutorial formatted as a README file, based on the two Python scripts you provided.

-----

# Azure Function Trace to Simulation Dataset Pipeline

This document describes a two-step pipeline to convert raw Azure Functions invocation data into a high-resolution, time-series simulation dataset. This final dataset is ideal for training machine learning models for tasks like predictive autoscaling, workload forecasting, or anomaly detection.

The process works as follows:

1.  **Step 1: Event Trace Generation** (`azure_datagen_raw.py`): Converts the massive, minute-by-minute invocation counts from the original Azure CSV into a "thinned-out" event trace. An event trace is a simple list of individual task arrivals, each with a precise arrival time, task type, and duration.
2.  **Step 2: Node Simulation** (`azure_datagen_replay.py`): "Plays back" the event trace from Step 1 through a single-core processor simulation. This script records the state of the processor (CPU load, queue length) at small time steps, creating a detailed, structured dataset.

## Prerequisites

Before you begin, you will need:

1.  **Python 3.x**

2.  **Required Python libraries**. You can install them using pip:

    ```bash
    pip install pandas numpy tqdm
    ```

3.  **The original Azure dataset files**:

      * `invocations_per_function_md.anon.d01.csv`: The main file containing invocation counts per function per minute.
      * `duration_map.pkl`: A pre-processed pickle file mapping functions to their average duration.
      * `top_functions.pkl`: A pre-processed pickle file containing a set of functions to focus on.

    **Note:** The scripts provided assume `duration_map.pkl` and `top_functions.pkl` already exist.

## Step 1: Generate the Scaled Event Trace

This step reduces the scale of the original trace to create a manageable workload.

  * **Script:** `azure_datagen_raw.py`
  * **Purpose:** To read the millions of invocations in the raw CSV and probabilistically "thin" them based on a scaling factor. It then generates a new CSV file where each row is a single invocation event.
  * **Key Configuration:** Inside `azure_datagen_raw.py`, you can adjust the **`LOAD_SCALE_FACTOR`**.
      * `LOAD_SCALE_FACTOR = 0.000995` (as in the file) means the script will use approximately 0.1% of the original invocations.
      * Changing this to `0.01` would use 1% of the load, resulting in 10x more events. This directly controls the **volume of requests** in the simulation.

### How to Run Step 1

1.  Ensure `azure_datagen_raw.py`, `invocations_per_function_md.anon.d01.csv`, `duration_map.pkl`, and `top_functions.pkl` are in the same directory.
2.  Run the script from your terminal:
    ```bash
    python azure_datagen_raw.py
    ```

<!-- end list -->

  * **Output:** This will create a new file named **`azure_trace_events_2hrs_scaled.csv`**.

-----

## Step 2: Simulate the Edge Node

This step uses the event trace from Step 1 to simulate a single-node server and record its performance.

  * **Script:** `azure_datagen_gold.py`
  * **Purpose:** To read the `azure_trace_events_2hrs_scaled.csv` file and feed each event (task) into a simulated processor with a task queue. It logs the state of this processor (queue length, CPU load) at 0.1-second intervals.
  * **Key Configuration:** Inside `azure_datagen_replay.py`, you can adjust the **`PROCESSOR_SPEED_FACTOR`**.
      * `PROCESSOR_SPEED_FACTOR = 200` (as in the file) means the processor is 200x faster than the baseline. A task that originally took 1 second to run will now take `1 / 200 = 0.005` seconds.
      * This controls the **processing power** of the node. A *higher* value means tasks finish faster, leading to shorter queues and lower CPU load.

### How to Run Step 2

1.  Ensure `azure_datagen_replay.py` and the output from Step 1 (`azure_trace_events_2hrs_scaled.csv`) are in the same directory.
2.  Run the script from your terminal:
    ```bash
    python azure_datagen_replay.py
    ```

<!-- end list -->

  * **Output:** This will create the final file named **`edge_node_simulation_from_trace_scaled.csv`**.

-----

## Tuning the Simulation

The "realism" of your final dataset depends on the balance between **`LOAD_SCALE_FACTOR`** (from Step 1) and **`PROCESSOR_SPEED_FACTOR`** (from Step 2).

  * **Goal:** You want to find a balance that creates dynamic "hills and valleys" in the workload.
  * **If your queue is always 0:** Your processor is too fast, or your load is too low.
      * **Fix:** *Decrease* `PROCESSOR_SPEED_FACTOR` (e.g., from 200 to 100) or *increase* `LOAD_SCALE_FACTOR` (e.g., from 0.001 to 0.005).
  * **If your queue length grows forever:** Your processor is too slow, or your load is too high.
      * **Fix:** *Increase* `PROCESSOR_SPEED_FACTOR` (e.g., from 200 to 300) or *decrease* `LOAD_SCALE_FACTOR`.

-----

## Understanding the Final Dataset

The final output, **`edge_node_simulation_from_trace_scaled.csv`**, will have the following columns:

  * **`timestamp`**: The simulation time, in seconds (e.g., `0.0`, `0.1`, `0.2`...).
  * **`queue_length`**: The number of tasks waiting in the queue at this exact timestamp.
  * **`cpu_load`**: The state of the CPU. Based on the `Task` class, this will be `0.0` (idle) or `0.8` (busy).
  * **`last_task_id_arrived`**: The `task_type` ID of the *last* task that arrived in this time step, or `None` if no task arrived.
  * **`avg_exec_[task_id]`** (many columns): A set of columns, one for each unique `task_type`. These columns show the *running average* of the task's *original* (unscaled) duration, as profiled by the simulation. This can be used to see if the average execution time of functions is changing.
