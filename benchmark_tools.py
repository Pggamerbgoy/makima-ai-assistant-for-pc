import time
import os
import psutil
from unittest.mock import MagicMock
from makima_tools.tool_registry import ToolRegistry

def run_benchmark():
    process = psutil.Process(os.getpid())
    
    # Baseline memory
    mem_before = process.memory_info().rss / 1024 / 1024
    
    print("--- Starting Benchmark ---")
    t0 = time.perf_counter()
    
    # Initialize tools
    makima = MagicMock()
    registry = ToolRegistry(makima)
    registry.initialize_all()
    
    t1 = time.perf_counter()
    mem_after = process.memory_info().rss / 1024 / 1024
    
    print("\n--- Benchmark Results ---")
    print(f"Load Time:     {(t1 - t0) * 1000:.2f} milliseconds")
    print(f"Memory Before: {mem_before:.2f} MB")
    print(f"Memory After:  {mem_after:.2f} MB")
    print(f"Added RAM:     {mem_after - mem_before:.2f} MB")
    
if __name__ == '__main__':
    run_benchmark()
