import os
import time
import pandas as pd
from tqdm import tqdm

from src.algorithms.packing_algorithm import run_packing_algorithm
from src.data_io.data_manager import DataManager
from src.models.models import Item, Container

def create_mock_item(index):
    """
    Creates a single mock item for the performance test.
    """
    return Item(
        sku=f"SKU_{index}",
        length=70.0,    # cm
        width=70.0,     # cm
        height=70.0,    # cm
        weight=5.0,     # kg
        quantity=1,
        stackable=1,
        rotatable=0
    )

def create_mock_container(container_type):
    """
    Creates a single container of the specified type.
    """
    if container_type == "40ft":
        return Container(
            length=1202.9,   # cm
            width=235.0,     # cm
            height=239.2,    # cm
            max_weight=30480, 
            container_type="40ft"
        )
    else:  # 20ft
        return Container(
            length=589.5,    
            width=235.0,     
            height=239.2,    
            max_weight=28200, 
            container_type="20ft"
        )

def measure_per_item_packing_time(total_items, packing_method, container_type):
    """
    Measures the time taken to pack each individual item as they're added.
    Returns a list of (item_count, elapsed_time) tuples.
    """
    data_manager = DataManager()
    container = create_mock_container(container_type)
    containers = [container]
    
    timing_results = []
    current_items = []
    
    # Create progress bar
    with tqdm(total=total_items, desc=f"Packing items ({packing_method}, {container_type})", unit="item") as pbar:
        for i in range(total_items):
            # Add new item
            new_item = create_mock_item(i)
            current_items.append(new_item)
            
            # Measure packing time for current set of items
            start_time = time.perf_counter()
            packed_containers = run_packing_algorithm(
                current_items, 
                containers, 
                packing_method=packing_method
            )
            end_time = time.perf_counter()
            
            # Record time for this item count
            elapsed_time = end_time - start_time
            timing_results.append((i + 1, elapsed_time))
            
            # Update progress bar
            pbar.update(1)
            
    return timing_results

def run_performance_test(total_items):
    """
    Runs performance test measuring time for each individual item addition.
    """
    PACKING_METHODS = ["vertical_loading", "floor_loading"]
    CONTAINER_TYPES = ["40ft"]
    
    all_results = []
    
    for method in PACKING_METHODS:
        for container_type in CONTAINER_TYPES:
            print(f"\nTesting {method} with {container_type} container:")
            results = measure_per_item_packing_time(total_items, method, container_type)
            
            # Add method and container type to results
            for item_count, time_taken in results:
                all_results.append({
                    "ItemCount": item_count,
                    "Method": method,
                    "ContainerType": container_type,
                    "TimeSeconds": time_taken
                })
    
    # Convert results to DataFrame
    results_df = pd.DataFrame(all_results)
    
    # Create analysis views
    pivot_by_method = pd.pivot_table(
        results_df, 
        values='TimeSeconds',
        index=['ItemCount', 'Method'],
        columns=['ContainerType'],
        aggfunc='mean'
    )

    pivot_by_container = pd.pivot_table(
        results_df, 
        values='TimeSeconds',
        index=['ItemCount', 'ContainerType'],
        columns=['Method'],
        aggfunc='mean'
    )
    
    # Save results
    with pd.ExcelWriter("packing_performance_results_per_item.xlsx", engine="openpyxl") as writer:
        results_df.to_excel(writer, sheet_name="Raw Data", index=False)
        pivot_by_method.to_excel(writer, sheet_name="Analysis by Method")
        pivot_by_container.to_excel(writer, sheet_name="Analysis by Container")
    
    print("\nPerformance results saved to 'packing_performance_results_per_item.xlsx'")

if __name__ == "__main__":
    TOTAL_ITEMS = 300  # Set your desired total number of items
    run_performance_test(TOTAL_ITEMS)


