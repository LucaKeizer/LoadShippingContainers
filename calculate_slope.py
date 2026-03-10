import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Read the Excel file
df = pd.read_excel("packing_performance_results_per_item.xlsx")

# Create a figure for the visualization
plt.figure(figsize=(12, 6))

# Use different colors and markers for each combination
colors = {'floor_loading': ['blue', 'lightblue'], 'vertical_loading': ['red', 'pink']}
markers = {'20ft': 'o', '40ft': 's'}

# For each method and container type combination, calculate growth rates and plot
for method in df['Method'].unique():
    for container in df['ContainerType'].unique():
        print(f"\nAnalyzing {method} with {container}:")
        
        # Get data for this combination, sorted by item count
        subset = df[
            (df['Method'] == method) & 
            (df['ContainerType'] == container)
        ].sort_values('ItemCount')
        
        # Calculate ratios between successive times
        times = subset['TimeSeconds'].values
        item_counts = subset['ItemCount'].values
        
        for i in range(len(times)-1):
            time_ratio = times[i+1] / times[i]
            count_ratio = item_counts[i+1] / item_counts[i]
            
            print(f"Items {item_counts[i]} → {item_counts[i+1]}:")
            print(f"  Time ratio: {time_ratio:.2f}x")
            print(f"  Count ratio: {count_ratio:.2f}x")
            print(f"  Growth factor: {time_ratio/count_ratio:.2f}x per doubling")
        
        # Plot this combination
        color = colors[method][0 if container == '20ft' else 1]
        plt.plot(item_counts, times, 
                marker=markers[container], 
                color=color,
                label=f"{method} - {container}",
                linewidth=2,
                markersize=8)

# Customize the plot
plt.xlabel('Number of Items')
plt.ylabel('Time (seconds)')
plt.title('Algorithm Performance Growth')
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend()

# Switch to linear scale
plt.yscale('linear')  # Changed from 'log' to 'linear'
plt.xscale('linear')  # Optional: Change to 'linear' if desired

# Optionally, set y-axis limits to fit your data
# plt.ylim(bottom=min(df['TimeSeconds']) * 0.9, top=max(df['TimeSeconds']) * 1.1)

# Ensure full numbers on both axes
plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0f}'))

# Add gridlines
plt.grid(True, which="both", ls="-", alpha=0.2)

# Adjust layout to prevent label clipping
plt.tight_layout()

# Save the plot
plt.savefig('performance_growth.png', dpi=300, bbox_inches='tight')
plt.close()
print("\nVisualization saved as 'performance_growth.png'")
