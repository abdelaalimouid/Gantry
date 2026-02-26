import json
import sys
import google.generativeai as genai

# --- 1. UTILITY FUNCTIONS ---

def generate_snake_order(total_width, total_height, tile_w, tile_h):
    """Generates a zig-zag traversal order to maximize row/column reuse."""
    cols = total_width // tile_w
    rows = total_height // tile_h
    order = []
    for r in range(rows):
        row_indices = [r * cols + c for c in range(cols)]
        if r % 2 == 1:  # Flip every other row
            row_indices.reverse()
        order.extend(row_indices)
    return order

def find_best_tiling(problem, nodes):
    """Greedily finds the largest [w, h, k] that fits memory."""
    capacity = problem['fast_memory_capacity']
    native_w, native_h = problem['native_granularity']
    
    # Candidates for searching (powers of 2 usually work best)
    for tile_size in [128, 64, 32, 16]:
        w = h = k = tile_size
        
        # Calculate working set for this tile
        # Simple heuristic: sum of tiles for all unique inputs and outputs in the group
        working_set = 0
        unique_tensors = set()
        for node_idx in nodes:
            unique_tensors.update(problem['inputs'][node_idx])
            unique_tensors.update(problem['outputs'][node_idx])
        
        # Approximate: most tiles will be w*h, MatMul LHS is h*k, RHS is w*k
        for t_idx in unique_tensors:
            working_set += (w * h) # Conservative estimate
            
        if working_set <= capacity:
            # We must account for native granularity padding in latency
            compute_penalty = (native_w / w) * (native_h / h) if w < native_w else 1
            return [w, h, k], compute_penalty
            
    return [16, 16, 16], 64 # Emergency fallback

# --- 2. THE AGENT LOGIC ---

def get_subgraphs_from_gemini(problem):
    """Ask Gemini to group nodes based on the DAG structure."""
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are a compiler optimization expert. 
    Partition the following operations into subgraphs to minimize memory spills.
    Rules:
    1. A subgraph is a list of node indices.
    2. Nodes in a subgraph should be connected to maximize ephemeral data usage.
    3. Return ONLY a JSON list of lists.
    
    Graph Inputs: {problem['inputs']}
    Op Types: {problem['op_types']}
    """
    
    response = model.generate_content(prompt)
    try:
        # Extract JSON from response
        text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(text)
    except:
        # Fallback: Each node its own subgraph
        return [[i] for i in range(len(problem['op_types']))]

# --- 3. MAIN EXECUTION ---

def main():
    if len(sys.argv) < 3:
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, 'r') as f:
        problem = json.load(f)

    # Step 1: Grouping
    subgraphs = get_subgraphs_from_gemini(problem)
    
    granularities = []
    traversal_orders = []
    latencies = []
    tensors_to_retain = [[] for _ in subgraphs] # Start simple: no inter-subgraph retention

    # Step 2: Optimization Loop
    for nodes in subgraphs:
        gran, penalty = find_best_tiling(problem, nodes)
        granularities.append(gran + ([1] if len(gran)==2 else []))
        
        # Generate snake order if tiling is used
        order = generate_snake_order(problem['widths'][0], problem['heights'][0], gran[0], gran[1])
        traversal_orders.append(order if len(order) > 1 else None)
        
        # Simple Latency Calculation (max(Compute, Memory))
        # This is a placeholder; real math would iterate through all tiles
        base_compute = sum(problem['base_costs'][i] for i in nodes) * penalty
        latencies.append(float(base_compute)) 

    # Step 3: Format Output
    solution = {
        "subgraphs": subgraphs,
        "granularities": granularities,
        "tensors_to_retain": tensors_to_retain,
        "traversal_orders": traversal_orders,
        "subgraph_latencies": latencies
    }

    with open(output_file, 'w') as f:
        json.dump(solution, f)

if __name__ == "__main__":
    main()